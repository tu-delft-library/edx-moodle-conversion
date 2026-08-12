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

    def _convert_expandable_widgets(self, article) -> None:
        """Rewrite WP's vc_expandable_text 'Read more/Read less' accordion (JS-driven,
        no JS ships with the converted page) into a native, always-closed
        <details>/<summary> disclosure widget, in place."""
        for widget in article.select("div.vc_expandable_text"):
            text_div = widget.select_one("div.vc_expandable_text__text")
            if text_div is None:
                widget.decompose()
                continue
            if "style" in text_div.attrs:
                del text_div["style"]
            toggle = widget.select_one("span.vc_expandable_text__more")
            label = (toggle.get("data-label-more") if toggle else None) or "Read more"
            if toggle is not None:
                toggle.decompose()
            widget.name = "details"
            del widget["class"]
            summary = widget.new_tag("summary")
            summary.string = label
            text_div.insert_before(summary)

    def _parse_subject_page(self, url: str, title: str) -> dict:
        """One chapter page. Everything before ul.activities is treated as the
        chapter's intro text; each <li> under ul.activities is a sequential,
        and the links inside it become verticals."""
        soup = self._fetch_page(url)
        article = soup.select_one("article")
        if article is not None:
            self._convert_expandable_widgets(article)
        intro_rows = []
        activities = None
        if article is not None:
            for child in article.find_all(recursive=False):
                if child.name == "ul" and "activities" in (child.get("class") or []):
                    activities = child
                    break
                if child.name == "div" and "vc_row" in (child.get("class") or []):
                    intro_rows.append(child)
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
        chapter = {"display_name": title, "sequentials": sequentials}
        if intro_rows:
            chapter["summary_html"] = "".join(str(row) for row in intro_rows)
        return chapter

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
        """A lecture page: descriptive text, a video (YouTube or Collegerama
        iframe), and more descriptive text and/or an attached PDF, in whatever
        order they appear on the page."""
        soup = self._fetch_page(url)
        article = soup.select_one("article")
        if article is not None:
            self._convert_expandable_widgets(article)
        components = []
        pdf_url = None
        for child in (article.find_all(recursive=False) if article else []):
            if child.name == "h1":
                continue
            if child.name == "section" and "license" in (child.get("class") or []):
                continue

            iframe = child if child.name == "iframe" else child.select_one("iframe")
            if iframe is not None and iframe.get("src"):
                src = iframe["src"]
                if "youtube.com" in src:
                    youtubeid = src.rstrip("/").split("/")[-1].split("?")[0]
                    components.append(
                        self._video_component(
                            url, title, chapter_name, sequential_name, youtubeid=youtubeid
                        )
                    )
                elif "collegerama.tudelft.nl" in src:
                    tuddownloadid = src.rstrip("/").split("/")[-1]
                    components.append(
                        self._video_component(
                            url, title, chapter_name, sequential_name,
                            tuddownloadid=tuddownloadid,
                        )
                    )
                continue

            dl_url = self._find_download_link(child)
            if dl_url is not None:
                pdf_url = dl_url
                continue

            if child.get_text(strip=True):
                components.append({"type": "html", "content": str(child)})

        if pdf_url:
            name = self._resolve_and_fetch(pdf_url)
            if name:
                components.append(
                    {"type": "html", "content": f'<p><a href="/static/{name}">{title}</a></p>'}
                )
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
        """A reading page. If it has a PDF download block, that PDF becomes a
        Readings entry; whatever body text is on the page (with or without a
        PDF) becomes a vertical."""
        soup = self._fetch_page(url)
        pdf_url = self._find_download_link(soup)
        if pdf_url is not None:
            name = self._resolve_and_fetch(pdf_url)
            if name is None:
                log.warning("Parsing WP: Missing pdf for Readings entry '%s' at %s", title, url)
            else:
                self.readings.append({"title": title, "name": name})

        text_html = self._reading_body_html(soup)
        if not text_html:
            return None
        return {"display_name": title, "components": [{"type": "html", "content": text_html}]}

    def _reading_body_html(self, soup: BeautifulSoup) -> str:
        """Article content minus the title, download block, and license footer."""
        article = soup.select_one("article")
        if article is None:
            return ""
        self._convert_expandable_widgets(article)
        parts = []
        for child in article.find_all(recursive=False):
            if child.name == "h1":
                continue
            if child.name == "section" and "license" in (child.get("class") or []):
                continue
            if self._find_download_link(child) is not None:
                continue
            if child.get_text(strip=True):
                parts.append(str(child))
        return "".join(parts)

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

    def _find_download_link(self, node) -> str | None:
        """href of the PDF download link in node, whether node itself is the
        vc_download block or merely contains one."""
        classes = node.get("class") or []
        container = node if "vc_download" in classes else node.select_one("div.vc_download")
        if container is None:
            return None
        link = container.select_one("a.icon.fa-file")
        return link["href"] if link else None

    def _fetch_page(self, url: str) -> BeautifulSoup:
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")