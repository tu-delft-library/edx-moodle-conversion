"""Check structural parity between an OLX export and its converted MBZ archive.

The checks compare chapter/section, sequential/subsection, and page counts after a build.
"""

import logging
import tarfile
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from ocw.parser.olx import Course


@dataclass
class CheckResult:
    """One expected-versus-actual structural count from a hybrid check."""

    name: str
    expected: int
    actual: int

    @property
    def passed(self) -> bool:
        """Whether the observed count matches the parsed source export."""
        return self.expected == self.actual


def _expected_counts(olx_path: Path) -> tuple[int, int, int]:
    """Return the section, subsection, and page counts the OLX export should produce.

    Includes the synthetic Overview section (always present) and Readings subsection (nested
    under Overview when the course has readings) created by the MBZ builder.
    """
    course = Course(olx_path)
    course.parse()
    pages = sum(
        1
        for ch in course.chapters
        for seq in ch["sequentials"]
        for vert in seq["verticals"]
        if any(c["type"] == "html" for c in vert["components"])
    )
    seqs = sum(len(ch["sequentials"]) for ch in course.chapters)
    has_syllabus_page = course.syllabus_html is not None
    has_readings = bool(course.readings)
    readings_subsection = 1 if has_readings else 0
    return (
        len(course.chapters) + 1,  # +1 for Overview, always present
        seqs + readings_subsection,
        pages + (1 if has_syllabus_page else 0),
    )


def _iter_section_xmls(tar: tarfile.TarFile) -> Iterator[ET.Element]:
    """Yield the root element of every section XML file in an MBZ archive."""
    for m in tar.getmembers():
        if m.name.startswith("sections/") and m.name.endswith("section.xml"):
            yield ET.parse(tar.extractfile(m)).getroot()


def run_hybrid_checks(olx_path: Path, mbz_path: Path) -> list[CheckResult]:
    """Compare the OLX-derived structural counts with the converted MBZ archive.

    Returns one result each for sections, subsections, and pages.
    """
    expected_chapters, expected_seqs, expected_pages = _expected_counts(olx_path)
    with tarfile.open(mbz_path) as tar:
        section_roots = list(_iter_section_xmls(tar))
        actual_chapters = sum(1 for r in section_roots if r.findtext("component") != "mod_subsection")
        actual_seqs = sum(1 for r in section_roots if r.findtext("component") == "mod_subsection")
        actual_pages = sum(1 for m in tar.getmembers() if m.name.endswith("page.xml"))
    return [
        CheckResult("chapter/section count parity", expected_chapters, actual_chapters),
        CheckResult("sequential/subsection count parity", expected_seqs, actual_seqs),
        CheckResult("page count parity", expected_pages, actual_pages),
    ]


def log_hybrid_checks(olx_path: Path, mbz_path: Path, log: logging.Logger) -> None:
    """Run the parity checks and log every result.

    All results use INFO when every check passes, otherwise WARNING so a failed check is visible
    in normal conversion output.
    """
    results = run_hybrid_checks(olx_path, mbz_path)
    level = logging.INFO if all(r.passed for r in results) else logging.WARNING
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        log.log(level, "%s: %s (expected %d, got %d)", status, r.name, r.expected, r.actual)
