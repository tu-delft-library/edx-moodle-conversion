import argparse
import logging
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

from ocw._version import __version__
from ocw.converter import MBZBuilder
from ocw.fetcher import AssetFetcher
from ocw.hybrid_checks import log_hybrid_checks
from ocw.logging_setup import setup_cli_logging
from ocw.parser.olx import Course
from ocw.utils import versioned_output_path


def main() -> None:
    """CLI entry point: parse an OLX export and write a Moodle MBZ archive."""
    ap = argparse.ArgumentParser(description="Convert OLX course to Moodle MBZ")
    ap.add_argument("--version", action="version", version=f"ocw {__version__}")
    ap.add_argument("olx_path", type=Path)
    ap.add_argument("--output", "-o", type=Path, default=Path("course.mbz"))
    ap.add_argument("--debug", action="store_true")
    ap.add_argument(
        "--sequential-sections",
        action="store_true",
        help="one Moodle section per sequential instead of per chapter",
    )
    ap.add_argument(
        "--authora",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Apply Authora layout changes: empty General section 0, Overview in section 1 (default: on)",
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
        help="Download PDFs still hosted on edX instead of just warning (default: on)",
    )
    args = ap.parse_args()
    setup_cli_logging(args.debug, Path("ocw.log"))
    log = logging.getLogger("ocw")
    log.info("ocw %s", __version__)

    tmp = None
    fetch_tmp = None
    try:
        olx_path = args.olx_path
        if olx_path.suffix == ".gz":
            tmp = Path(tempfile.mkdtemp())
            with tarfile.open(olx_path) as tar:
                tar.extractall(tmp)
            olx_path = next(p for p in tmp.iterdir() if p.is_dir())

        fetcher = None
        if args.fetch_external_assets:
            fetch_tmp = Path(tempfile.mkdtemp())
            fetcher = AssetFetcher(fetch_tmp)

        course = Course(olx_path, fetcher=fetcher)
        course.parse()
        output = versioned_output_path(args.output)
        MBZBuilder(
            course,
            sequential_sections=args.sequential_sections,
            disable_custom_fields=args.disable_custom_fields,
            authora=args.authora,
        ).build(output)
        log_hybrid_checks(olx_path, output, log, authora=args.authora)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        if fetch_tmp:
            shutil.rmtree(fetch_tmp, ignore_errors=True)
