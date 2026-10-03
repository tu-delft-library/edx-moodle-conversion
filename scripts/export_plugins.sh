#!/bin/bash
# Builds install-ready zips for filter_vidrouter and local_vidrouter.
#
# Moodle's zip installer expects the top-level folder inside the zip to be the
# plugin's short name (e.g. "vidrouter"), not its full frankenstyle component
# name — so this stages each plugin under that short name before zipping,
# even though the repo itself keeps the full component name as the directory.
#
# Usage: ./scripts/export_plugins.sh [output_dir]
# Default output_dir: current working directory

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$SCRIPT_DIR/../moodle-plugin"
OUTDIR="${1:-$(pwd)}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$OUTDIR"

build_zip() {
    local src="$1" shortname="$2" zipname="$3"

    rm -rf "$STAGE/$shortname"
    cp -r "$src" "$STAGE/$shortname"
    (cd "$STAGE" && zip -rq "$OUTDIR/$zipname" "$shortname")
    rm -rf "$STAGE/$shortname"

    echo "$zipname:"
    unzip -l "$OUTDIR/$zipname" | tail -3
}

build_zip "$PLUGIN_DIR/filter/vidrouter" "vidrouter" "filter_vidrouter.zip"
build_zip "$PLUGIN_DIR/local/vidrouter" "vidrouter" "local_vidrouter.zip"

echo "Done: $OUTDIR/filter_vidrouter.zip, $OUTDIR/local_vidrouter.zip"
