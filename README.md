# Edx (OLX) to Moodle (MBZ) conversion

Converts OpenEdX OLX course exports to Moodle MBZ backup archives.

# Usage

## 1. Using the Tool

From an extracted OLX directory:

```bash
poetry run python main.py path/to/olx_course/ -o output.mbz
```

From a `.tar.gz` archive:

```bash
poetry run python main.py path/to/course.tar.gz -o output.mbz
```

Or via the installed entry point (same thing, no `main.py` needed):

```bash
poetry run ocw path/to/olx_course/ -o output.mbz
```

### From a WordPress course site

```bash
poetry run ocw-wp https://example.edu/course-home-page/ -o output.mbz
```

The output `.mbz` can then be imported into Moodle via **Site Administration → Restore Course → Restore as a new course**.

### GUI

Desktop app, same conversion logic as the CLI, no flags to remember:

```bash
poetry run python -m ocw.gui.olx   # OLX GUI
poetry run python -m ocw.gui.wp    # WordPress GUI
```

Packaged binaries (`ocw-gui`, `ocw-gui-wp`) are also built per release — see the GitHub Releases page.

### Options

| Flag                                            | Default | Description                                                                              |
| ------------------------------------------------ | ------- | ---------------------------------------------------------------------------------------- |
| `--sequential-sections`                         | off     | one Moodle section per sequential instead of per chapter, named `"Chapter - Sequential"` |
| `--disable-custom-fields`                       | off     | skip populating Edusources custom fields                                                 |
| `--fetch-external-assets` / `--no-fetch-...`    | on      | download PDFs still hosted on edX instead of just warning (`ocw-wp`: PDFs linked from the site) |
| `--debug`                                       | off     | verbose logging to stderr and `ocw.log`                                                  |

Example with sequential sections:

```bash
poetry run python main.py path/to/olx_course/ -o output.mbz --sequential-sections
```

### Warnings

During conversion the parser emits warnings to stderr (and `ocw.log` with `--debug`) when the OLX references a static file that doesn't exist in the `static/` directory:

```
WARNING  Parser: Missing static file logo.png referenced in unit_abc123
```

### Heuristics

Assumption-based extraction, for debugging empty fields:

- **`tuddownloadid` sibling-scan.** dframe/video paired positionally within a vertical: exactly one of each →
  paired; 0 or 2+ of either → logged ambiguous, left unpaired.

### Custom styling

Go to Themes > Boost (click cog) -> Advanced Settings -> Paste under Initial SCSS.

```css
#resourceobject { height: 90vh !important; }
```

Forces PDF readers to take up the screen height for better readability.

---

## 2. Running Checks

```
# post-hoc parity checks against a specific export
poetry run pytest tests/integration/test_hybrid_checks.py \
  --olx-path <path/to/olx> \
  --mbz-path <path/to/output.mbz> -v
```

# Development

```
poetry run python main.py path/to/olx_course/ -o output.mbz --debug
```

# Running Tests

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

### Test files

**`tests/unit/`** — pure unit tests, no filesystem or Moodle needed

- `test_utils.py` — `esc`, `rewrite_static_urls`, `sha1_of`, `_Counter`
- `test_parser.py` — parser raises correctly on missing XML files
- `test_moodle_schema.py` — individual XML template strings validate against MBZ schema
- `test_moodle_backup.py` — full MBZ output: required files present, all XML fields populated, semantic values correct, `files.xml` completeness

**`tests/integration/`** — build real MBZ archives from fixtures, inspect output

- `test_pipeline.py` — builder constructor/lifecycle + cross-file structural integrity (section sequences → activity dirs, module `sectionid` → real section, backup manifest → real dirs)
- `test_requirements.py` — acceptance tests for CC1, CC2, CC3, SK1, C1
- `test_hybrid_checks.py` — post-hoc parity checks against a real OLX+MBZ pair; requires `--olx-path` and `--mbz-path` flags
- `test_real_courses.py` — smoke-tests parsing and building the bundled real-course fixtures; skipped if absent

**`tests/live_moodle/`** — end-to-end against a live Moodle instance; requires `MOODLE_URL`, `MOODLE_TOKEN`, and Docker

- `test_restore.py` — course exists after restore, fullname/section count/names/page count/titles all match, multi-html vertical aggregates into one page

> **Note:** all tests run against the default mode (one section per chapter). `--sequential-sections` behaviour is not covered by any tests.

