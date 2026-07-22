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

The output `.mbz` can then be imported into Moodle via **Site Administration → Restore Course → Restore as a new course**.

### Options

| Flag                    | Default | Description                                                                              |
| ----------------------- | ------- | ---------------------------------------------------------------------------------------- |
| `--sequential-sections` | off     | one Moodle section per sequential instead of per chapter, named `"Chapter - Sequential"` |
| `--debug`               | off     | verbose logging to stderr and `ocw.log`                                                  |

Example with sequential sections:

```bash
poetry run python main.py path/to/olx_course/ -o output.mbz --sequential-sections
```

### Warnings

During conversion the parser emits warnings to stderr (and `ocw.log` with `--debug`) when the OLX references a static file that doesn't exist in the `static/` directory:

```
WARNING  Parser: Missing static file logo.png referenced in unit_abc123
```

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

---

## Requirements

| Id  | Title                            | Description                                                                      | Status |
| --- | -------------------------------- | -------------------------------------------------------------------------------- | ------ |
| CC1 | Copy and map structure           | Full course structure (sections, subsections, units) mapped with matching titles | MVP    |
| CC2 | Copy basic page contents         | Static HTML content copied and correctly visible in Moodle                       | MVP    |
| CC3 | Copy images                      | Images copied, stored, and visible at the right place in the page                | MVP    |
| CC4 | Copy video page contents         | Embedded video with download/subtitles                                           | Future |
| CC5 | Copy advanced page contents      | JavaScript components                                                            | Future |
| CC6 | Copy welcome page contents       | General chapter / welcome page handling                                          | Future |
| SK1 | Skip unsupported content         | Multiple choice, problem bank, open response, drag and drop — skipped silently   | MVP    |
| C1  | Warn if content missing          | If content referenced in OLX is not available, warn the user                     | MVP    |
| C2  | Warn if external content missing | Checks against external platforms                                                | Future |
| C3  | Warn if OpenEdX-only resource    | Resources on OpenEdX not present in OLX export                                   | Future |
