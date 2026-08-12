import logging

import requests
from bs4 import BeautifulSoup

from ocw.fetcher import AssetFetcher
from ocw.parser_base import BaseParser
from ocw.utils import resolve_asset_name, safe_vidkey

log = logging.getLogger("ocw.wp_parser")


class WPCourse(BaseParser):
    """Scrapes a WordPress-hosted course site (HTML only, no API) into the same
    chapter/sequential/vertical/component structure the Converter builds an MBZ
    from."""

    # Sidebar/link types that don't map to any component we build.
    _SKIPPED_ICON_TYPES = frozenset({"icon--exercise", "icon--exam", "icon--mooc"})

    def __init__(self, root: str, fetcher: AssetFetcher | None = None) -> None:
        """
        Args:
            root: Course home page URL.
            fetcher: Optional AssetFetcher for downloading linked PDFs.
        """
        super().__init__(root, fetcher)
        self._session = requests.Session()

    def parse(self) -> None:
        home = self._fetch_page(self.root)
        self.course_name = home.select_one("h1").get_text(strip=True)
        for subject_url, subject_title in self._parse_subjects_sidebar(home):
            self.chapters.append(self._parse_subject_page(subject_url, subject_title))
        self.videos = [
            comp
            for chapter in self.chapters
            for sequential in chapter["sequentials"]
            for vertical in sequential["verticals"]
            for comp in vertical["components"]
            if comp["type"] == "video"
        ]

    def _parse_subjects_sidebar(self, home: BeautifulSoup) -> list[tuple[str, str]]:
        """(url, title) for each top-level chapter link on the course home page.
        The heading text above these links isn't stable across courses ("Subjects",
        "Weeks", ...), so this matches on the surrounding ul.activities wrapper
        instead of the heading itself."""
        activities = home.select_one("ul.activities")
        if activities is None:
            log.warning("No chapter list found on %s", self.root)
            return []
        return [(a["href"], a.get_text(strip=True)) for a in activities.find_all("a")]

    def _parse_subject_page(self, url: str, title: str) -> dict:
        """One chapter page. Each <li> under ul.activities is a sequential; the
        links inside it become verticals."""
        soup = self._fetch_page(url)
        activities = soup.select_one("ul.activities")
        if activities is None:
            log.warning("No activities list found on subject page '%s'", url)
            return {"display_name": title, "sequentials": []}
        sequentials = []
        for group in activities.find_all("li", recursive=False):
            seq_title_el = group.select_one("span.course-title")
            seq_title = seq_title_el.get_text(strip=True) if seq_title_el else title
            verticals = [
                v
                for a in group.select("ul a.icon")
                if (v := self._parse_item(a, title, seq_title)) is not None
            ]
            sequentials.append({"display_name": seq_title, "verticals": verticals})
        return {"display_name": title, "sequentials": sequentials}

    def _parse_item(self, link, chapter_name: str, sequential_name: str) -> dict | None:
        """Dispatch a single activities-list link by its icon--TYPE class."""
        icon_type = next((c for c in link.get("class", []) if c.startswith("icon--")), "")
        if icon_type in self._SKIPPED_ICON_TYPES:
            return None
        title = link.get_text(strip=True)
        if icon_type == "icon--lecture":
            return self._parse_lecture(link["href"], title, chapter_name, sequential_name)
        if icon_type == "icon--reading":
            return self._parse_reading(link["href"], title)
        log.warning("Unhandled WP item type '%s' at %s", icon_type or "<none>", link["href"])
        return None

    def _parse_lecture(
        self, url: str, title: str, chapter_name: str, sequential_name: str
    ) -> dict:
        """A lecture page: a video (YouTube or Collegerama iframe), optionally
        with an attached PDF alongside it."""
        soup = self._fetch_page(url)
        components = []
        iframe = soup.select_one("article iframe")
        src = iframe["src"] if iframe else ""
        if "youtube.com" in src:
            youtubeid = src.rstrip("/").split("/")[-1].split("?")[0]
            components.append(
                self._video_component(url, title, chapter_name, sequential_name, youtubeid=youtubeid)
            )
        elif "collegerama.tudelft.nl" in src:
            tuddownloadid = src.rstrip("/").split("/")[-1]
            components.append(
                self._video_component(
                    url, title, chapter_name, sequential_name, tuddownloadid=tuddownloadid
                )
            )
        pdf_url = self._parse_download_block(soup)
        if pdf_url:
            name = self._resolve_and_fetch(pdf_url)
            if name:
                components.append(
                    {"type": "html", "content": f'<p><a href="/static/{name}">{title}</a></p>'}
                )
        if not components:
            article = soup.select_one("article")
            components.append({"type": "html", "content": str(article) if article else ""})
        return {"display_name": title, "components": components}

    def _video_component(
        self,
        url: str,
        title: str,
        chapter_name: str,
        sequential_name: str,
        *,
        youtubeid: str | None = None,
        tuddownloadid: str | None = None,
    ) -> dict:
        """Build a video component in the shape the vidrouter block/[[vid:{key}]]
        placeholder scheme expects (see ocw.parser.Course._parse_video). WP has no
        edX video id, so edxvideoid/stlbaseid are always empty here; vidkey is
        derived from the lecture page's URL slug instead."""
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        return {
            "type": "video",
            "display_name": title,
            "vidkey": safe_vidkey(slug),
            "youtubeid": youtubeid,
            "edxvideoid": None,
            "stlbaseid": None,
            "tuddownloadid": tuddownloadid,
            "urlname": slug,
            "videopagepath": f"{chapter_name} > {sequential_name} > {title}",
        }

    def _parse_reading(self, url: str, title: str) -> dict | None:
        """A reading page becomes a Readings entry only if it has a PDF download
        block; otherwise it's just inline text, so it's returned as a plain html
        component instead."""
        soup = self._fetch_page(url)
        pdf_url = self._parse_download_block(soup)
        if pdf_url is None:
            article = soup.select_one("article")
            return {
                "display_name": title,
                "components": [{"type": "html", "content": str(article) if article else ""}],
            }
        name = self._resolve_and_fetch(pdf_url)
        if name is None:
            log.warning("Parsing WP: Missing pdf for Readings entry '%s' at %s", title, url)
            return None
        self.readings.append({"title": title, "name": name})
        return None  # lives in self.readings, not in a vertical

    def _resolve_and_fetch(self, pdf_url: str) -> str | None:
        """Download pdf_url via self.fetcher if not already resolved locally,
        returning its static_files key, or None if it couldn't be fetched."""
        name = resolve_asset_name(pdf_url)
        if name in self.static_files:
            return name
        if self.fetcher is None:
            return None
        fetched = self.fetcher.fetch(pdf_url)
        if fetched is None:
            return None
        self.static_files[fetched.name] = fetched
        return fetched.name

    def _parse_download_block(self, soup: BeautifulSoup) -> str | None:
        link = soup.select_one("div.vc_download a.icon.fa-file")
        return link["href"] if link else None

    def _fetch_page(self, url: str) -> BeautifulSoup:
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")