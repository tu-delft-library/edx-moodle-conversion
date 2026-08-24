import argparse
import logging
import shutil
import sys
import tempfile
from pathlib import Path

from ocw._version import __version__
from ocw.converter import MBZBuilder
from ocw.fetcher import AssetFetcher
from ocw.logging_setup import setup_cli_logging
from ocw.utils import versioned_output_path
from ocw.parser.wp import WPCourse


def main() -> None:
    """CLI entry point: scrape a WordPress course site and write a Moodle MBZ archive."""
    ap = argparse.ArgumentParser(description="Convert a WordPress course site to Moodle MBZ")
    ap.add_argument("--version", action="version", version=f"ocw-wp {__version__}")
    ap.add_argument("site_url", type=str)
    ap.add_argument("--output", "-o", type=Path, default=Path("course.mbz"))
    ap.add_argument("--debug", action="store_true")
    ap.add_argument(
        "--sequential-sections",
        action="store_true",
        help="one Moodle section per sequential instead of per chapter",
    )
    ap.add_argument(
        "--disable-custom-fields",
        action="store_true",
        help="Skip populating custom fields",
    )
    ap.add_argument(
        "--fetch-external-assets",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Download PDFs linked from the site (default: on)",
    )
    args = ap.parse_args()
    setup_cli_logging(args.debug, Path("ocw.log"))
    log = logging.getLogger("ocw")
    log.info("ocw-wp %s", __version__)

    fetch_tmp = None
    try:
        fetcher = None
        if args.fetch_external_assets:
            fetch_tmp = Path(tempfile.mkdtemp())
            fetcher = AssetFetcher(fetch_tmp)

        course = WPCourse(args.site_url, fetcher=fetcher)
        course.parse()
        output = versioned_output_path(args.output)
        MBZBuilder(
            course,
            sequential_sections=args.sequential_sections,
            disable_custom_fields=args.disable_custom_fields,
        ).build(output)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if fetch_tmp:
            shutil.rmtree(fetch_tmp, ignore_errors=True)


if __name__ == "__main__":
    main()