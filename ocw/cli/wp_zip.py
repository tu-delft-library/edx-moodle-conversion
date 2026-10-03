import argparse
import logging
import shutil
import sys
import tempfile
from pathlib import Path

from ocw._version import __version__
from ocw.converter.zip_builder import ZipBuilder
from ocw.fetcher import AssetFetcher
from ocw.logging_setup import setup_cli_logging
from ocw.parser.wp import WPCourse
from ocw.utils import versioned_output_path
from ocw.zip_checks import log_zip_checks


def main() -> None:
    """CLI entry point: back a WordPress course site up to a zip archive."""
    ap = argparse.ArgumentParser(description="Back up a WordPress OCW course site to a zip")
    ap.add_argument("--version", action="version", version=f"ocw-wp-zip {__version__}")
    ap.add_argument("site_url", type=str)
    ap.add_argument("--output", "-o", type=Path, default=Path("course.zip"))
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--fetch-external-assets", action=argparse.BooleanOptionalAction, default=True)
    args = ap.parse_args()
    setup_cli_logging(args.debug, Path("ocw.log"))
    logging.getLogger("ocw").info("ocw-wp-zip %s", __version__)

    fetch_tmp = Path(tempfile.mkdtemp())
    try:
        fetcher = AssetFetcher(fetch_tmp) if args.fetch_external_assets else None
        course = WPCourse(args.site_url, fetcher=fetcher, keep_all_content=True)
        course.parse()
        out = versioned_output_path(args.output)
        ZipBuilder(course).build(out)
        log_zip_checks(course, out, logging.getLogger("ocw.zip_checks"))
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        shutil.rmtree(fetch_tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
