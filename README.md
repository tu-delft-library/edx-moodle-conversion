# OpenEdx and WordPress to Moodle Converter

Converts OpenEdx OLX course exports and WordPress course sites into Moodle MBZ backup archives.

# 1. Usage

## General

Run either converter with an input and destination path:

```bash
poetry run <command> <input> -o <output.mbz>
```

Or with a .venv active in your shell:

```bash
python [command] [path] -o [output_path]
```

## OLX Conversion

```bash
poetry run ocw path/to/olx_course/ -o output.mbz
```

## WordPress Conversion

```bash
poetry run ocw-wp https://example.edu/course-home-page/ -o output.mbz
```

## Flags

| Flag                         | Default | Description                                                           |
| ---------------------------- | ------- | --------------------------------------------------------------------- |
| `--sequential-sections`      | off     | One Moodle section per sequential, named `"Chapter - Sequential"`.    |
| `--disable-custom-fields`    | off     | Skip populating eduSources custom fields.                             |
| `--fetch-external-assets`    | on      | Download externally hosted PDFs and files instead of only warning.    |
| `--no-fetch-external-assets` | off     | Leave external assets as links and report them in the conversion log. |
| `--debug`                    | off     | Write verbose logging to stderr and `ocw.log`.                        |

Example with sequential sections:

```bash
poetry run ocw path/to/olx_course/ -o output.mbz --sequential-sections
```

## GUI

Desktop app, same conversion logic as the CLI:

```bash
poetry run python -m ocw.gui.olx   # OLX GUI
poetry run python -m ocw.gui.wp    # WordPress GUI
```

Packaged binaries (`ocw-gui`, `ocw-gui-wp`) are also built per release.

## Warnings

During conversion, the tool emits warnings to stderr and `ocw.log` with `--debug`.

```
WARNING  Parser: Missing static file logo.png referenced in unit_abc123
```

| Log-message prefix                             | Meaning                                                       | Action                                           |
| ---------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------ |
| `Parsing OLX: Missing ...`                     | File absent from the OLX `static/` directory.                 | Check the export or enable fetching.             |
| `Content still hosted on edX ...`              | Page links to edX infrastructure.                             | Replace or download the asset.                   |
| `Failed to fetch external asset ...`           | Converter could not download a linked file.                   | Check access, then attach it manually if needed. |
| `External asset ... returned content-type ...` | URL returned an unexpected type, often a login or error page. | Download and attach the original file manually.  |
| `Ambiguous dframe/video pairing ...`           | Converter could not safely assign a video download ID.        | Review the video mapping after restore.          |
| `Skipping unsupported component type ...`      | Unsupported OpenEdx component skipped. Debug logging only.    | Recreate required Moodle content manually.       |
| `Unhandled OLX component tag ...`              | Converter does not recognise an OLX component.                | Review and recreate required content manually.   |

### Post-build Checks

The converter runs these checks after building the MBZ. A failed check needs review before restore.

| Result                                     | Meaning                                          | Action                                              |
| ------------------------------------------ | ------------------------------------------------ | --------------------------------------------------- |
| `PASS: chapter/section count parity`       | Source chapters match top-level Moodle sections. | No action.                                          |
| `PASS: sequential/subsection count parity` | Source subsections match Moodle subsections.     | No action.                                          |
| `PASS: page count parity`                  | Source HTML units match Moodle pages.            | No action.                                          |
| `FAIL: ... parity`                         | The source and MBZ counts differ.                | Review the log and course structure before restore. |

# 2. Heuristics

We make the following assumptions for video ID extraction:

- **`tuddownloadid` pairing:** dframe/video paired positionally to a TuDownload block within a vertical: exactly one of each →
  paired; 0 or 2+ of either → logged ambiguous, left unpaired. `tudownloadid` is within the TuDownload block.

# 3. Styling

Go to Site administration > Appearance > Themes > Boost > Advanced settings > Raw initial SCSS.

```css
#resourceobject {
  height: 90vh !important;
}
```

Forces PDF readers to take up the screen height for better readability.

# 4. Running Checks

The pytest command below manually checks an existing OLX export and MBZ archive.

```
# post-hoc parity checks against a specific export
poetry run pytest tests/integration/test_hybrid_checks.py \
  --olx-path <path/to/olx> \
  --mbz-path <path/to/output.mbz> -v
```

# 5. Running Tests

```bash
# all (unit + integration)
poetry run python run_tests.py

# unit only
poetry run python run_tests.py unit

# integration only
poetry run python run_tests.py integration

# live moodle (requires .env + docker)
poetry run python run_tests.py live
```

## Test files

**`tests/unit/`**: pure unit tests, no filesystem or Moodle needed

- `test_utils.py`: `esc`, `rewrite_static_urls`, `sha1_of`, `_Counter`
- `test_parser.py`: parser raises correctly on missing XML files
- `test_moodle_schema.py`: individual XML template strings validate against MBZ schema
- `test_moodle_backup.py`: full MBZ output: required files present, all XML fields populated, semantic values
  correct, `files.xml` completeness

**`tests/integration/`**: build real MBZ archives from fixtures, inspect output

- `test_pipeline.py`: builder constructor/lifecycle + cross file structural integrity (section sequences → activity
  dirs, module `sectionid` → real section, backup manifest → real dirs)
- `test_requirements.py`: acceptance tests for CC1, CC2, CC3, SK1, C1
- `test_hybrid_checks.py`: post hoc parity checks against a real OLX+MBZ pair: requires `--olx-path` and
  `--mbz-path` flags
- `test_real_courses.py`: smoke tests parsing and building bundled real-course fixtures: skipped if absent

**`tests/live_moodle/`**: end to end against a live Moodle instance: requires `MOODLE_URL`, `MOODLE_TOKEN`, and Docker

- `test_restore.py`: course exists after restore, fullname/section count/names/page count/titles all match,
  multi HTML vertical aggregates into one page

> **Note:** all tests run against the default mode (one section per chapter). `--sequential-sections` behaviour is
> not covered by any tests.

# 6. Moodle Video Router Plugins

Install `filter_vidrouter.zip` and `local_vidrouter.zip` before restoring a converted course with videos.
Release downloads already contain both archives.

Moodle plugin ZIP files must contain the plugin's short directory name at their root. Both archives therefore
contain `vidrouter/`, while their `version.php` files identify them as `filter_vidrouter` and `local_vidrouter`.

Build local install archives from the repository root:

```bash
./export_plugins.sh
```

```bash
./export_plugins.sh <output-directory>
```

## Required Moodle configuration

Install both archives through Moodle's plugin installer. Then enable **Video Router Filter** at:

`Site administration > Plugins > Filters > Manage filters`

Place **Video Router Filter** above **Multimedia plugins**. Video Router resolves `[[vid:KEY]]` into a video
link or embed. Multimedia plugins must run afterwards to process that output.

If a video renders as a link in one course only, open:

`Course administration > Filters`

Set **Multimedia plugins** to **On** or **Inherit**. A course-specific **Off** setting overrides the site-wide
filter setting.

## How the plugins work

`local_vidrouter` imports each new video mapping while Moodle restores the MBZ.

`filter_vidrouter` replaces `[[vid:KEY]]` whenever Moodle displays a page. It uses YouTube first, then
Collegerama, then shows an unavailable-video message when neither source is available.

When Moodle duplicates or restores an existing Moodle course, `local_vidrouter` _should_ preserve the resolved video
HTML in the course backup.

## Running the PHP tests

The plugin tests run inside a Moodle install (e.g. via [moodle-docker](https://github.com/moodlehq/moodle-docker)),
not from this repo directly. Symlink or copy `moodle-plugin/filter/vidrouter` and `moodle-plugin/local/vidrouter`
into that Moodle checkout's `filter/` and `local/` directories, run PHPUnit init once, then run the plugin's tests
with an explicit test suffix (a bare directory path does not inherit the suffix from the generated `phpunit.xml`):

```bash
php public/admin/tool/phpunit/cli/init.php
vendor/bin/phpunit --test-suffix=_test.php public/filter/vidrouter/tests
```

# 7. Documentation

The implementation documentation includes Markdown pages and generated Python and PHP API reference.

Install the documentation dependencies:

```bash
poetry install --with dev
composer install --working-dir=tools/phpdoc
```

Build all documentation, including the PHP API reference:

```bash
./scripts/build-docs.sh
```

Start a local preview:

```bash
poetry run mkdocs serve
```

Re-run `./scripts/build-docs.sh` after changing PHP code or PHPDoc blocks.
