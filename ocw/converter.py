import logging
from pathlib import Path

from ocw.parser import OLXCourse

log = logging.getLogger("ocw.converter")

#INFO: Cross refrence to docker image
MOODLE_VERSION = "2025100601"


class MBZBuilder:
    """Converts a parsed OLXCourse into a Moodle MBZ backup archive."""

    def __init__(self, course: OLXCourse) -> None:
        """
        Args:
            course: A parsed OLXCourse instance.
        """
        self.course = course

    def build(self, out: Path) -> None:
        """Write the MBZ archive to out."""
        raise NotImplementedError("Sprint 2")
