import argparse
import logging
import sys
from pathlib import Path

from ocw.converter import MBZBuilder
from ocw.parser import OLXCourse


def _setup_logging(debug: bool, log_path: Path) -> None:
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
    ap = argparse.ArgumentParser(description="Convert OLX course to Moodle MBZ")
    ap.add_argument("olx_path", type=Path)
    ap.add_argument("--output", "-o", type=Path, default=Path("course.mbz"))
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    _setup_logging(args.debug, Path("ocw.log"))
    course = OLXCourse(args.olx_path)
    course.parse()
    MBZBuilder(course).build(args.output)
