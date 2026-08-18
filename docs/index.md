# Implementation Documentation

This site documents how the converter turns OpenEdx OLX exports and public WordPress course sites into Moodle MBZ
archives.

It separates implementation explanations from generated API reference:

* **Implementation** pages describe data flow, supported content, decisions, and operational requirements.
* **Python API** is generated from source docstrings and signatures whenever MkDocs builds the site.
* **PHP API** is generated from Moodle plugin PHPDoc blocks during the full documentation build.

## Build documentation

Install the Python development dependencies:

```bash
poetry install --with dev
```

Preview authored documentation and the Python API reference:

```bash
poetry run mkdocs serve
```

Build the full site, including generated PHP API reference:

```bash
composer install --working-dir=tools/phpdoc
./scripts/build-docs.sh
```

Generated PHP output is written to `docs/api/php/` and ignored by Git. Do not edit it manually.
