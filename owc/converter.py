import logging
from pathlib import Path

from owc.parser import OLXCourse

log = logging.getLogger("owc.converter")

MOODLE_VERSION = "2025100601"


class MBZBuilder:
    def __init__(self, course: OLXCourse):
        self.course = course

    def build(self, out: Path) -> None:
        raise NotImplementedError("Sprint 2")
