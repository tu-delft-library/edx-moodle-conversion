"""Parse WordPress course sites into the normalised data consumed by `MBZBuilder`."""

import logging

import requests
from bs4 import BeautifulSoup

from ocw.fetcher import AssetFetcher
from ocw.parser.base import BaseParser
from ocw.utils import resolve_asset_name, safe_vidkey

log = logging.getLogger("ocw.wp_parser")


class WPCourse(BaseParser):
    """Parse a WordPress course site's HTML navigation and content into course records.

    The parser follows the site's chapter and activity navigation rather than using a WordPress
    API.
    """

    _SKIPPED_ICON_TYPES = frozenset({"icon--exercise", "icon--exam", "icon--mooc"})

    _ALIGN_STYLES = {
        "alignleft": "float:left;margin:0 1em 1em 0;",
        "alignright": "float:right;margin:0 0 1em 1em;",
        "aligncenter": "display:block;margin:0 auto 1em;",
    }

    def __init__(self, root: str, fetcher: AssetFetcher | None = None) -> None:
        super().__init__(root, fetcher)
        self._session = requests.Session()

    def parse(self) -> None:
        """Parse the course home page, its subject pages, and all video components."""
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
        """Return top-level chapter URLs and titles from the course navigation.

        Matches the stable `ul.activities` wrapper because the heading above it varies between
        sites.
        """
        activities = home.select_one("ul.activities")
        if activities is None:
            log.warning("No chapter list found on %s", self.root)
            return []
        return [(a["href"], a.get_text(strip=True)) for a in activities.find_all("a")]

    def _convert_expandable_widgets(self, article) -> None:
        """Replace JavaScript-driven WordPress expandable widgets with native `details` elements.

        Widgets without content are removed.
        """
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

    def _apply_wp_image_alignment(self, article) -> None:
        """Translate WordPress `alignleft`/`alignright`/`aligncenter` image classes into inline
        float styles, since Moodle's theme has no CSS for WordPress's align classes.
        """
        for img in article.select("img"):
            classes = img.get("class") or []
            align = next((c for c in classes if c in self._ALIGN_STYLES), None)
            if align is None:
                continue
            img["style"] = self._ALIGN_STYLES[align] + img.get("style", "")

    def _replace_separators(self, article) -> None:
        """Replace WPBakery `vc_separator` dividers with `<hr>`; the original markup depends on
        Visual Composer CSS Moodle doesn't ship, so it renders as invisible empty elements.
        """
        for sep in article.select("div.vc_separator"):
            sep.replace_with(article.new_tag("hr"))

    def _clean_article(self, article) -> None:
        """Apply all WordPress-widget-to-Moodle-safe-HTML conversions to `article`."""
        self._convert_expandable_widgets(article)
        self._apply_wp_image_alignment(article)
        self._replace_separators(article)

    def _parse_subject_page(self, url: str, title: str) -> dict:
        """Parse one subject page into a chapter record.

        Content before the activity list becomes the chapter summary. Activity groups become
        sequentials and their links become verticals.
        """
        soup = self._fetch_page(url)
        article = soup.select_one("article")
        if article is not None:
            self._clean_article(article)
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
        """Dispatch one activity link according to its `icon--...` class.

        Configured unsupported icon types are skipped. Unknown types produce a warning.
        """
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
        """Parse one lecture page into a vertical record.

        Preserves descriptive HTML in source order, extracts YouTube or Collegerama videos, and
        turns a linked PDF into a local file link when it can be resolved.
        """
        soup = self._fetch_page(url)
        article = soup.select_one("article")
        if article is not None:
            self._clean_article(article)
        components = []
        pdf_url = None
        for child in (article.find_all(recursive=False) if article else []):
            kind, value = self._classify_lecture_child(child, url, title, chapter_name, sequential_name)
            if kind == "component":
                components.append(value)
            elif kind == "pdf_url":
                pdf_url = value

        if pdf_url:
            name = self._resolve_and_fetch(pdf_url)
            if name:
                components.append(
                    {"type": "html", "content": f'<p><a href="/static/{name}">{title}</a></p>'}
                )
        return {"display_name": title, "components": components}

    def _classify_lecture_child(
        self, child, url: str, title: str, chapter_name: str, sequential_name: str
    ) -> tuple[str | None, object]:
        """Classify one top-level lecture element as a component, a PDF download URL, or nothing.

        Returns `("component", dict)`, `("pdf_url", str)`, or `(None, None)` to skip the element.
        """
        if child.name == "h1":
            return None, None
        if child.name == "section" and "license" in (child.get("class") or []):
            return None, None

        iframe = child if child.name == "iframe" else child.select_one("iframe")
        if iframe is not None and iframe.get("src"):
            src = iframe["src"]
            if "youtube.com" in src:
                youtubeid = src.rstrip("/").split("/")[-1].split("?")[0]
                return "component", self._video_component(
                    url, title, chapter_name, sequential_name, youtubeid=youtubeid
                )
            if "collegerama.tudelft.nl" in src:
                collegeramaid = src.rstrip("/").split("/")[-1]
                return "component", self._video_component(
                    url, title, chapter_name, sequential_name, collegeramaid=collegeramaid
                )
            return None, None

        dl_url = self._find_download_link(child)
        if dl_url is not None:
            return "pdf_url", dl_url

        if child.get_text(strip=True):
            return "component", {"type": "html", "content": str(child)}
        return None, None

    def _video_component(
        self,
        url: str,
        title: str,
        chapter_name: str,
        sequential_name: str,
        *,
        youtubeid: str | None = None,
        collegeramaid: str | None = None,
    ) -> dict:
        """Build a video-routing record for a WordPress lecture page.

        The routing key derives from the page URL slug. WordPress supplies YouTube or Collegerama
        IDs, while edX, SRT, and TUD download identifiers remain unset.
        """
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        return {
            "type": "video",
            "display_name": title,
            "vidkey": safe_vidkey(slug),
            "youtubeid": youtubeid,
            "edxvideoid": None,
            "srtbaseid": None,
            "tuddownloadid": None,
            "collegeramaid": collegeramaid,
            "urlname": slug,
            "videopagepath": f"{chapter_name} > {sequential_name} > {title}",
        }

    def _parse_reading(self, url: str, title: str) -> dict | None:
        """Parse one reading page into an optional PDF resource and an HTML vertical.

        A resolved PDF is added to `readings`. Returns `None` when no reading body remains after
        removing source-only elements.
        """
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
        """Extract reading-body HTML without the title, PDF download control, or licence footer."""
        article = soup.select_one("article")
        if article is None:
            return ""
        self._clean_article(article)
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
        """Return the local static-file name for a PDF, fetching it when configured.

        Successfully fetched PDFs are registered in `static_files`.
        """
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
        """Return the PDF URL from a WordPress `vc_download` block in or below `node`."""
        classes = node.get("class") or []
        container = node if "vc_download" in classes else node.select_one("div.vc_download")
        if container is None:
            return None
        link = container.select_one("a.icon.fa-file")
        return link["href"] if link else None

    def _fetch_page(self, url: str) -> BeautifulSoup:
        """Fetch `url` and parse its HTML with lxml.

        HTTP failures propagate to the conversion workflow.
        """
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
