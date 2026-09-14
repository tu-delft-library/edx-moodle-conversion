"""Fake WordPress OCW site builder for integration-level WPCourse tests.

Mirrors tests/builders.py's OLXFixtureBuilder, but WPCourse crawls HTTP pages instead of
reading a directory tree, so this builds a `url -> HTML` map and monkeypatches
`WPCourse._fetch_page` to serve it without any real network calls.
"""

import tempfile
from pathlib import Path

from bs4 import BeautifulSoup

from ocw.parser.wp import WPCourse
from ocw.utils import resolve_asset_name

ROOT = "https://ocw.tudelft.nl/courses/example/"


class _FakeFetcher:
    """Serve fixed file bytes for a URL, matching AssetFetcher.fetch's interface."""

    def __init__(self, files: dict[str, bytes]):
        self._files = files

    def fetch(self, url: str) -> Path | None:
        name = resolve_asset_name(url)
        if name not in self._files:
            return None
        dest = Path(tempfile.mkdtemp()) / name
        dest.write_bytes(self._files[name])
        return dest


class WPFixtureSite:
    """Build a fake WordPress OCW site as a URL -> HTML page map.

    `course()` returns a `WPCourse` that crawls the map instead of making real HTTP requests.
    """

    def __init__(self, root: str = ROOT):
        self.root = root
        self.pages: dict[str, str] = {}
        self.pdf_files: dict[str, bytes] = {}

    def add_home(self, subjects: list[tuple[str, str]], banner_url: str | None = None) -> None:
        """subjects: list of (url, title) pairs shown in the sidebar nav."""
        links = "\n".join(f'<li><a href="{url}">{title}</a></li>' for url, title in subjects)
        banner = (
            f'<section class="banner" style="background-image: url(\'{banner_url}\');"></section>'
            if banner_url
            else ""
        )
        self.pages[self.root] = f"""
        {banner}
        <h1>Example Course</h1>
        <ul class="activities activities--bordered">
        <li><h4>Subjects</h4><ul>{links}</ul></li>
        </ul>
        """

    def add_subject_page(self, url: str, activities_html: str, intro_html: str = "") -> None:
        self.pages[url] = f"<article>{intro_html}{activities_html}</article>"

    def add_lecture_page(self, url: str, body_html: str) -> None:
        self.pages[url] = f"<article>{body_html}</article>"

    def add_static_file(self, name: str, content: bytes = b"%PDF-1.4 fake") -> None:
        """Register a file so the fake fetcher can resolve any URL whose basename matches
        `name` (lecture-page `vc_download` links, bundled webfonts, etc.)."""
        self.pdf_files[name] = content

    def add_reading_page(
        self,
        url: str,
        body_html: str,
        pdf_name: str | None = None,
        pdf_bytes: bytes = b"%PDF-1.4 fake",
    ) -> None:
        self.pages[url] = f"<article>{body_html}</article>"
        if pdf_name:
            self.pdf_files[pdf_name] = pdf_bytes

    def course(self, include_license_banner: bool = False) -> WPCourse:
        fetcher = _FakeFetcher(self.pdf_files) if self.pdf_files else None
        course = WPCourse(
            self.root, fetcher=fetcher, include_license_banner=include_license_banner
        )
        course._fetch_page = lambda url: BeautifulSoup(self.pages[url], "lxml")
        return course
