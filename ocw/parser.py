import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("ocw.parser")


class OLXCourse:
    def __init__(self, root: Path):
        self.root = root
        self.course_name = ""
        self.course_id = ""
        self.chapters: list[dict] = []
        self.static_files: dict[str, Path] = {}
        self._b64_tmp_dir: Optional[Path] = None

    def parse(self) -> None:
        raise NotImplementedError("Sprint 2")
