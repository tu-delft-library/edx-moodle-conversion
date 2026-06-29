import argparse
import logging
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

from ocw.converter import MBZBuilder
from ocw.parser import Course


def _setup_logging(debug: bool, log_path: Path) -> None:
    """Attach stderr and file handlers to the root ocw logger."""
    log = logging.getLogger("ocw")
    log.setLevel(logging.DEBUG if debug else logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    )
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    log.addHandler(sh)
    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)


def main() -> None:
    """CLI entry point: parse an OLX export and write a Moodle MBZ archive."""
    ap = argparse.ArgumentParser(description="Convert OLX course to Moodle MBZ")
    ap.add_argument("olx_path", type=Path)
    ap.add_argument("--output", "-o", type=Path, default=Path("course.mbz"))
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    _setup_logging(args.debug, Path("ocw.log"))

    tmp = None
    try:
        olx_path = args.olx_path
        if olx_path.suffix == ".gz":
            tmp = Path(tempfile.mkdtemp())
            with tarfile.open(olx_path) as tar:
                tar.extractall(tmp)
            olx_path = next(p for p in tmp.iterdir() if p.is_dir())

        course = Course(olx_path)
        course.parse()
        MBZBuilder(course).build(args.output)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    # TODO: In the case of an exception calmly notify the user
