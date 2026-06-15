import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("ocw.parser")


class OLXCourse:
    """Parses an OpenEdX OLX course export into a structured representation."""

    def __init__(self, root: Path) -> None:
        """
        Args:
            root: Path to the extracted OLX directory or a .tar.gz archive.
        """
        self.root = root
        self.course_name: str = ""
        self.course_id: str = ""
        self.chapters: list[dict] = []
        self.static_files: dict[str, Path] = {}
        self._b64_tmp_dir: Optional[Path] = None

    def parse(self) -> None:
        """Populate course metadata, chapters, and static_files from the OLX tree."""
        raise NotImplementedError("Sprint 2")
