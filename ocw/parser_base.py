from abc import ABC, abstractmethod
from pathlib import Path

from ocw.fetcher import AssetFetcher


class BaseParser(ABC):
    """Contract every source-format parser fills in. Converter/MBZBuilder only ever
    reads these attributes — never anything format-specific — so a new parser is a
    self-contained addition that doesn't touch conversion logic."""

    def __init__(self, root: Path | str, fetcher: AssetFetcher | None = None) -> None:
        self.root = root
        self.fetcher = fetcher
        self.course_name: str = ""
        self.course_id: str = ""
        self.chapters: list[dict] = []
        self.static_files: dict[str, Path] = {}
        self.syllabus_html: str | None = None
        self.syllabus_title: str = "Syllabus"
        self.readings: list[dict] = []
        self.videos: list[dict] = []
        self.org: str = ""
        self.language: str = ""
        self.license: str = ""
        self.summary_html: str | None = None
        self.instructors: list[dict] = []

    @abstractmethod
    def parse(self) -> None:
        """Populate every attribute above from the source export/site."""
