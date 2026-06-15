import argparse
import logging
import sys
from pathlib import Path

from ocw.converter import MBZBuilder
from ocw.parser import OLXCourse


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


# FIX: Move out to ../main.py
def main() -> None:
    """CLI entry point: parse an OLX export and write a Moodle MBZ archive."""
    ap = argparse.ArgumentParser(description="Convert OLX course to Moodle MBZ")
    ap.add_argument("olx_path", type=Path)
    ap.add_argument("--output", "-o", type=Path, default=Path("course.mbz"))
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    _setup_logging(args.debug, Path("ocw.log"))

    # The course in question
    course = OLXCourse(args.olx_path)
    course.parse()

    # MBZ output
    MBZBuilder(course).build(args.output)
