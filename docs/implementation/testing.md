# Testing

Python tests use pytest and are split by scope.

| Path | Purpose |
| --- | --- |
| `tests/unit/` | Parser, builder, schema, utility, and WordPress HTML fixture tests. |
| `tests/integration/` | Real MBZ generation and parity checks. |
| `tests/live_moodle/` | Restore checks against a running Moodle instance. |

Run the standard suites:

```bash
poetry run python scripts/run_tests.py
poetry run python scripts/run_tests.py unit
poetry run python scripts/run_tests.py integration
```

Moodle plugin PHPUnit tests live under `moodle-plugin/filter/vidrouter/tests/`. The Moodle Plugin CI workflow installs
Moodle with both plugins before running the filter plugin suite.

## Conversion warnings

Warnings identify content that needs review but do not stop conversion. A missing required OLX XML file is different:
it raises an error and stops the conversion because the source structure cannot be resolved.

| Source | Warning | Conversion behaviour |
| --- | --- | --- |
| OLX | Referenced static file or reading PDF is missing. | Logs source location. Missing reading entries are omitted. |
| OLX | External asset fetch fails or returns the wrong content type. | Logs the failure and does not embed that file. |
| OLX | HTML still references edX hosted content. | Logs the URL because it remains external after restore. |
| OLX | A component tag is unknown. | Logs the component type and skips it. Known unsupported types use debug logging. |
| OLX | A vertical has ambiguous dframe and video pairing. | Leaves the TU Delft download ID unset. |
| WP | The course home page has no subject sidebar. | Logs the URL and produces no source chapters. |
| WP | A subject page has no activities list. | Logs the subject URL and produces an empty chapter. |
| WP | An activity icon type is unknown. | Logs the type and skips that item. Exercises, exams, and MOOCs are skipped. |
| WP | A linked reading PDF cannot be fetched. | Logs the reading title and URL. The PDF resource is omitted. |

## Runtime checks

The OLX CLI and packaged OLX GUI call
[`log_hybrid_checks()`](../reference/python.md#ocw.hybrid_checks.log_hybrid_checks) after every completed archive.
It reparses the source and compares its expected structure with the MBZ XML.

| Check | Source count | MBZ count |
| --- | --- | --- |
| Chapter and section parity | OLX chapters plus generated Overview, and the empty General section with `--authora`. | Moodle top level sections. |
| Sequential and subsection parity | OLX sequentials plus generated Readings subsection. | Moodle subsection sections. |
| Page parity | OLX HTML verticals plus generated syllabus page. | `page.xml` activity records. |

A failed parity check is logged as `WARNING`. It does not delete the archive or change its contents. The same
non pytest implementation is used by the CLI and packaged GUI. The pytest integration tests call it directly.

Run parity checks for an existing source and archive:

```bash
poetry run pytest tests/integration/test_hybrid_checks.py \
  --olx-path <path/to/olx> \
  --mbz-path <path/to/output.mbz> -v
```

## Python test coverage

| Path | Coverage |
| --- | --- |
| `tests/unit/test_parser.py` | OLX hierarchy traversal, metadata, readings, videos, missing XML, and warnings. |
| `tests/unit/test_wp_parser.py` | WordPress navigation, readings, widgets, YouTube, and Collegerama. |
| `tests/unit/test_moodle_backup.py` | MBZ layout, XML fields, ordering, files, metadata, and edX URL warnings. |
| `tests/unit/test_moodle_schema.py` | Required Moodle XML schema fragments and cross references. |
| `tests/unit/test_utils.py` | XML escaping, URL rewriting, hashes, ID allocation, and external edX URL detection. |
| `tests/unit/test_hybrid_checks_unit.py` | The parity checker against a matching generated archive. |
| `tests/integration/test_pipeline.py` | Parser to builder pipeline and generated manifest references. |
| `tests/integration/test_requirements.py` | Functional requirements, unsupported content, and warning behaviour. |
| `tests/integration/test_hybrid_checks.py` | The three post hoc parity counts. |
| `tests/integration/test_real_courses.py` | Parse and build smoke tests for optional real OLX fixtures. |
| `tests/live_moodle/test_restore.py` | Live Moodle restore with course, section, and page comparisons. |

`test_moodle_schema.py` contains four strict expected failures for optional activity stubs: roles, filters, gradebook,
and grade history. Optional real course fixtures are skipped when their tarballs are not present. Live Moodle tests are
skipped until `MOODLE_URL` and `MOODLE_TOKEN` are configured and the target Moodle Docker container is available.

## Moodle plugin PHPUnit tests

| File | Coverage |
| --- | --- |
| `bulk_import_test.php` | CSV parsing, matching, validation, updates, and cache invalidation. |
| `edit_form_test.php` | Video key form validation. |
| `video_renderer_test.php` | YouTube and Collegerama selection, fallback, missing videos, and export rendering. |

The `moodle-plugin-ci.yml` workflow installs Moodle and both plugins, then runs the filter plugin PHPUnit suite with
warnings treated as failures. It also publishes PHP coverage.

## Continuous checks

| Workflow | Trigger | Checks |
| --- | --- | --- |
| Python CI | Pull requests to `main`: manual runs. | Unit and integration tests with coverage. |
| Plugin CI | Plugin PRs to `main`: manual runs. | Moodle install, PHPUnit, and PHP coverage. |
| Documentation CI | Documentation and implementation changes. | PHPDoc and strict MkDocs build. |

Workflow definitions are `.github/workflows/ci.yml`, `.github/workflows/moodle-plugin-ci.yml`, and
`.github/workflows/docs.yml`.
