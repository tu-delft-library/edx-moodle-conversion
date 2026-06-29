# edx-moodle-conversion

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

---

## Requirements

| Id  | Title                        | Description                                                                          | Status      |
| --- | ---------------------------- | ------------------------------------------------------------------------------------ | ----------- |
| CC1 | Copy and map structure       | Full course structure (sections, subsections, units) mapped with matching titles     | MVP         |
| CC2 | Copy basic page contents     | Static HTML content copied and correctly visible in Moodle                           | MVP         |
| CC3 | Copy images                  | Images copied, stored, and visible at the right place in the page                    | MVP         |
| CC4 | Copy video page contents     | Embedded video with download/subtitles                                               | Future      |
| CC5 | Copy advanced page contents  | JavaScript components                                                                | Future      |
| CC6 | Copy welcome page contents   | General chapter / welcome page handling                                              | Future      |
| SK1 | Skip unsupported content     | Multiple choice, problem bank, open response, drag and drop — skipped silently       | MVP         |
| C1  | Warn if content missing      | If content referenced in OLX is not available, warn the user                         | MVP         |
| C2  | Warn if external content missing | Checks against external platforms                                                | Future      |
| C3  | Warn if OpenEdX-only resource | Resources on OpenEdX not present in OLX export                                      | Future      |
