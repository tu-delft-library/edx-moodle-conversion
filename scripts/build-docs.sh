#!/usr/bin/env bash

set -euo pipefail

phpdoc="tools/phpdoc/vendor/bin/phpdoc"

if [[ ! -x "$phpdoc" ]]; then
    echo "Install PHP documentation tooling: composer install --working-dir=tools/phpdoc" >&2
    exit 1
fi

rm -rf docs/api/php
"$phpdoc" run --config=phpdoc.dist.xml
poetry run mkdocs build --strict
