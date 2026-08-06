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
from ocw.parser import Course
from ocw.utils import run_hybrid_checks, versioned_output_path


class _ColourFormatter(logging.Formatter):
    _YELLOW = "\033[33m"
    _BLUE = "\033[34m"
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        if record.levelno == logging.WARNING:
            record = logging.makeLogRecord(record.__dict__)
            record.levelname = f"{self._YELLOW}WARNING{self._RESET}"
            if record.args:
                record.args = tuple(
                    f"{self._YELLOW}{a}{self._RESET}" for a in record.args
                )
        msg = super().format(record)
        msg = msg.replace("Parsing OLX:", f"{self._BLUE}Parsing OLX:{self._RESET}")
        return msg.replace("DOWNLOAD:", f"{self._BLUE}DOWNLOAD:{self._RESET}")


def _setup_logging(debug: bool, log_path: Path) -> None:
    """Attach stderr and file handlers to the root ocw logger."""
    log = logging.getLogger("ocw")
    log.setLevel(logging.DEBUG if debug else logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%H:%M:%S"
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(_ColourFormatter(fmt, datefmt=datefmt))
    log.addHandler(sh)
    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    log.addHandler(fh)


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
    _setup_logging(args.debug, Path("ocw.log"))
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
        ).build(output)
        run_hybrid_checks(olx_path, output)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        if fetch_tmp:
            shutil.rmtree(fetch_tmp, ignore_errors=True)
