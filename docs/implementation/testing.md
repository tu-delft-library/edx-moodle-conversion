# Testing

Python tests use pytest and are split by scope.

| Path | Purpose |
| --- | --- |
| `tests/unit/` | Parser, builder, schema, utility, and WordPress HTML fixture tests. |
| `tests/integration/` | Real MBZ generation and parity checks. |
| `tests/live_moodle/` | Restore checks against a running Moodle instance. |

Run the standard suites:

```bash
poetry run python run_tests.py
poetry run python run_tests.py unit
poetry run python run_tests.py integration
```

Moodle plugin PHPUnit tests live under `moodle-plugin/filter/vidrouter/tests/`. The Moodle Plugin CI workflow installs
Moodle with both plugins before running the filter plugin suite.
