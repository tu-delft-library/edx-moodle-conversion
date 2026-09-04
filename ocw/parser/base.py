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
        # OLX: bare {title, name} entries, rendered as mod_resource in a standalone Readings
        # section. WP: real vertical dicts (own body text + download box), rendered as mod_page
        # in that same section; every course occurrence links to the one canonical page.
        self.readings: list[dict] = []
        self.reading_pages: list[dict] = []
        # Canonical pages for any other content type that can be linked from more than one place
        # (currently: WP lectures). Each occurrence links in, but the page itself is built once
        # and placed in one hidden, unlisted section rather than duplicated per occurrence.
        self.dedup_pages: list[dict] = []
        self.videos: list[dict] = []
        self.org: str = ""
        self.language: str = ""
        self.license: str = ""
        self.summary_html: str | None = None
        # WP only: the home page's course description, shown directly in the Overview section's
        # own body text. Distinct from `summary_html` (a short course.xml-level blurb -- for OLX,
        # deliberately not the same content as its Syllabus tab) and from `syllabus_html` (a
        # separate page inside Overview).
        self.overview_summary_html: str | None = None
        self.instructors: list[dict] = []

    @abstractmethod
    def parse(self) -> None:
        """Populate the normalised course data from the configured source."""
