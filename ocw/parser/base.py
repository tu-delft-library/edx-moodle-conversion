from abc import ABC, abstractmethod
from pathlib import Path

from ocw.fetcher import AssetFetcher


class BaseParser(ABC):
    """Define the normalised course data required by `MBZBuilder`.

    Source-specific subclasses populate these shared attributes from their own export or site
    format. The builder depends only on this contract, not on a source-specific parser.
    """

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
        """Populate the normalised course data from the configured source."""
