import logging
import zipfile
from pathlib import Path, PurePosixPath

from ocw.hybrid_checks import CheckResult
from ocw.parser.base import BaseParser

_INDEX = "index.html"


def _expected_pages(course: BaseParser) -> int:
    """Count the pages `ZipBuilder` writes: any planned page with components."""
    verticals = [
        vert
        for chapter in course.chapters
        for seq in chapter["sequentials"]
        for vert in seq["verticals"]
    ]
    return sum(1 for page in [*verticals, *course.reading_pages, *course.dedup_pages] if page["components"])


def run_zip_checks(course: BaseParser, zip_path: Path) -> list[CheckResult]:
    """Compare the planned page count with the content pages inside the zip.

    Chapter and root `index.html` files are navigation, so they are excluded from the actual count.
    """
    with zipfile.ZipFile(zip_path) as zf:
        actual = sum(
            1
            for name in zf.namelist()
            if name.endswith(".html") and PurePosixPath(name).name != _INDEX
        )
    return [CheckResult("page count parity", _expected_pages(course), actual)]


def log_zip_checks(course: BaseParser, zip_path: Path, log: logging.Logger) -> None:
    """Run the zip parity checks and log every result."""
    results = run_zip_checks(course, zip_path)
    level = logging.INFO if all(r.passed for r in results) else logging.WARNING
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        log.log(level, "%s: %s (expected %d, got %d)", status, r.name, r.expected, r.actual)
