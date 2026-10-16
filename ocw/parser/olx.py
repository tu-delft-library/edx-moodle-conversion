import json
import logging
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from ocw.fetcher import AssetFetcher
from ocw.parser import download_tool
from ocw.parser.base import BaseParser
from ocw.utils import (
    _ABSOLUTE_ASSET_RE,
    _DFRAME_RE,
    _DOWNLOADID_RE,
    resolve_asset_name,
    safe_vidkey,
    static_file_kind,
)

log = logging.getLogger("ocw.parser")

# Tags the parser actively converts into page content.
# _WHITELISTED_TAGS = frozenset({"html", "video"})

# Component tags deliberately dropped because the converter has no Moodle equivalent.
# delftxtools' Discussion and Collaboration Guidelines, an extensionless PDF linked by `#page=`.
_DACG_URL = "https://delftxtools.tudelft.nl/DaCG"
_DACG_NAME = "DaCG.pdf"
_DACG_RE = re.compile(r"https?://delftxtools\.tudelft\.nl/DaCG(?=[#\"'\s]|$)")

_BLACKLISTED_TAGS = frozenset(
    {
        "problem",
        "discussion",
        "drag-and-drop",
        "drag-and-drop-v2",
        "advanced",
        "lti_consumer",
        "word_cloud",
        "openassessment",
        "poll",
        "survey",
        "freetextresponse",
    }
)


def _find_dframe_downloadids(html: str) -> list[str]:
    """Return every download ID on a dframe iframe in `html`."""
    ids = []
    for tag_match in _DFRAME_RE.finditer(html):
        id_match = _DOWNLOADID_RE.search(tag_match.group(0))
        if id_match:
            ids.append(id_match.group(1))
    return ids


class Course(BaseParser):
    """Parse an Open edX OLX export into source-normalised course data.

    Follows the `course -> chapter -> sequential -> vertical -> component` reference graph,
    resolves packaged assets, and records supported HTML and video components for MBZ construction.
    """

    def __init__(self, root: Path, fetcher: AssetFetcher | None = None) -> None:
        super().__init__(root, fetcher)
        self.root: Path = root
        self._b64_tmp_dir: Path | None = None

    def parse(self) -> None:
        """Populate course metadata, source hierarchy, static assets, readings, and videos."""
        stub_path = self.root / "course.xml"
        if not stub_path.exists():
            stub_path = self.root / "course" / "course.xml"

        stub = ET.parse(stub_path).getroot()
        url_name = stub.get("url_name", "course")
        self.course_id = stub.get("course", "")

        course = ET.parse(self.root / "course" / f"{url_name}.xml").getroot()
        self.course_name = course.get("display_name", "")
        self.org = stub.get("org", "")
        self.language = course.get("language", "")
        self.license = course.get("license", "")
        self._parse_summary()

        static_dir = self.root / "static"

        if static_dir.is_dir():
            for f in static_dir.iterdir():
                if f.is_file():
                    self.static_files[f.name] = f
                    self.static_files[re.sub(r"[^-\w.]", "_", f.name)] = f

        self.course_image_path = self._resolve_static_attr(course, "course_image")
        self.banner_image_path = self._resolve_static_attr(course, "banner_image")

        for ref in course.findall("chapter"):
            self.chapters.append(
                self._parse_chapter(self.root, ref.get("url_name", ""))
            )

        self._parse_syllabus(url_name)
        self._parse_readings(course)

        self.videos = [
            comp
            for chapter in self.chapters
            for sequential in chapter["sequentials"]
            for vertical in sequential["verticals"]
            for comp in vertical["components"]
            if comp["type"] == "video"
        ]

    def _parse_summary(self) -> None:
        """Populate the course summary from `about/short_description.html`."""
        path = self.root / "about" / "short_description.html"
        if path.exists() and path.read_text(encoding="utf-8").strip():
            self.summary_html = path.read_text(encoding="utf-8")

    def _resolve_static_attr(self, course: ET.Element, attr: str) -> Path | None:
        """Resolve an OLX course-root attribute naming a `static/` asset to its local path."""
        raw = course.get(attr)
        if not raw:
            return None
        name = raw.removeprefix("/static/")
        path = self.static_files.get(name)
        if path is None:
            log.warning(
                "Parsing OLX: course declares %s=%r but no such static file exists", attr, raw
            )
        return path

    def _parse_syllabus(self, url_name: str) -> None:
        """Populate optional instructor and syllabus data from the course policy."""
        policy_path = self.root / "policies" / url_name / "policy.json"
        if not policy_path.exists():
            return
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        course_policy = policy.get(f"course/{url_name}", {})
        self.instructors = course_policy.get("instructor_info", {}).get(
            "instructors", []
        )
        tab = next(
            (t for t in course_policy.get("tabs", []) if t.get("type") == "static_tab"),
            None,
        )
        if tab is None:
            return
        url_slug = tab.get("url_slug")
        if not url_slug:
            return
        tab_path = self.root / "tabs" / f"{url_slug}.html"
        if not tab_path.exists():
            return
        self.syllabus_html = self._bundle_dacg(tab_path.read_text(encoding="utf-8"))
        self.syllabus_title = tab.get("name") or "Syllabus"

    def _parse_readings(self, course: ET.Element) -> None:
        """Build reading records from the course's optional `pdf_textbooks` metadata."""
        raw = course.get("pdf_textbooks")
        if not raw:
            return
        for textbook in json.loads(raw):
            for chapter in textbook.get("chapters", []):
                url = chapter.get("url", "")
                name = resolve_asset_name(url)
                if name not in self.static_files:
                    fetched = None
                    if self.fetcher and _ABSOLUTE_ASSET_RE.search(url):
                        fetched = self.fetcher.fetch(url)
                    if fetched is not None:
                        self.static_files[name] = fetched
                    else:
                        log.warning(
                            "Parsing OLX: Missing %s '%s' for Readings entry '%s'",
                            static_file_kind(name),
                            name,
                            chapter.get("title", ""),
                        )
                        continue
                self.readings.append({"title": chapter.get("title", ""), "name": name})

    def _parse_chapter(self, root: Path, url_name: str) -> dict:
        """Resolve one chapter reference into its sequential records."""
        path = root / "chapter" / f"{url_name}.xml"
        if not path.exists():
            raise FileNotFoundError(f"Missing Chapter XML: {url_name}")
        el = ET.parse(path).getroot()
        sequentials = []
        chapter_name = el.get("display_name", url_name)
        for ref in el.findall("sequential"):
            sequentials.append(
                self._parse_sequential(root, ref.get("url_name", ""), chapter_name)
            )
        return {
            "url_name": url_name,
            "display_name": el.get("display_name", ""),
            "sequentials": sequentials,
        }

    def _parse_sequential(
        self, root: Path, url_name: str, chapter_name: str = ""
    ) -> dict:
        """Resolve one sequential reference into its vertical records.

        Passes the chapter name onward so later warnings can identify the source location.
        """
        path = root / "sequential" / f"{url_name}.xml"
        if not path.exists():
            raise FileNotFoundError(f"Missing Sequential XML: {url_name}")
        el = ET.parse(path).getroot()
        verticals = []
        sequential_name = el.get("display_name", url_name)
        for ref in el.findall("vertical"):
            verticals.append(
                self._parse_vertical(
                    root, ref.get("url_name", ""), chapter_name, sequential_name
                )
            )
        return {
            "url_name": url_name,
            "display_name": el.get("display_name", ""),
            "verticals": verticals,
        }

    def _parse_vertical(
        self,
        root: Path,
        url_name: str,
        chapter_name: str = "",
        sequential_name: str = "",
    ) -> dict:
        """Resolve one vertical reference into supported component records.

        Attaches a download ID only when the vertical contains one matching dframe and one video.
        """
        path = root / "vertical" / f"{url_name}.xml"
        if not path.exists():
            raise FileNotFoundError(f"Missing Vertical XML: {url_name}")
        el = ET.parse(path).getroot()
        display_name = el.get("display_name", "")
        components = [
            c
            for child in el
            if (
                c := self._parse_component(
                    root, child, display_name, sequential_name, chapter_name
                )
            )
            is not None
        ]
        self._attach_video_download_ids(components, display_name)
        self._inline_download_tools(components)
        return {
            "url_name": url_name,
            "display_name": display_name,
            "components": components,
        }

    def _inline_download_tools(self, components: list[dict]) -> None:
        """Replace each dframe (plus its builder.js loader) with the inlined DelftxDownloads
        widget; see `ocw.parser.download_tool`. Left untouched when fetching is disabled."""
        if self.fetcher is None:
            return
        for comp in components:
            if comp["type"] != "html" or not _find_dframe_downloadids(comp["content"]):
                continue
            soup = BeautifulSoup(comp["content"], "html.parser")
            for frame in soup.select("iframe.dframe"):
                url = download_tool.tool_url(
                    frame.get("data-downloadid", ""),
                    "edx",
                    lang=frame.get("data-lang") or "en",
                    filetype=frame.get("data-filetype") or "mp4",
                    cc_sa=frame.get("data-ccsa") or "y",
                    cc_nc=frame.get("data-ccnc") or "y",
                )
                page = self.fetcher.fetch_text(url)
                if page is None:
                    continue
                frame.replace_with(
                    download_tool.inline_widget(
                        BeautifulSoup(page, "html.parser"), url, self._fetch_static
                    )
                )
            for script in soup.select('script[src$="builder.js"]'):
                script.decompose()
            comp["content"] = str(soup)

    def _bundle_dacg(self, html: str) -> str:
        """Point DaCG links at a bundled copy, keeping any `#page=` fragment. Left untouched
        when it can't be fetched."""
        if self.fetcher is None or not _DACG_RE.search(html):
            return html
        fetched = self.fetcher.fetch(_DACG_URL, name=_DACG_NAME)
        if fetched is None:
            return html
        self.static_files[_DACG_NAME] = fetched
        return _DACG_RE.sub(f"/static/{_DACG_NAME}", html)

    def _fetch_static(self, url: str) -> str | None:
        """Bundle `url` as a static file and return its name, or `None` when unavailable."""
        name = resolve_asset_name(url)
        if name in self.static_files:
            return name
        fetched = self.fetcher.fetch(url)
        if fetched is None:
            return None
        self.static_files[fetched.name] = fetched
        return fetched.name

    def _attach_video_download_ids(
        self, components: list[dict], vertical_name: str = ""
    ) -> None:
        """Attach a dframe download ID to a video only when the vertical has one of each.

        Ambiguous pairings are warned about and left unset.
        """
        downloadids = [
            did
            for comp in components
            if comp["type"] == "html"
            for did in _find_dframe_downloadids(comp["content"])
        ]
        videos = [c for c in components if c["type"] == "video"]
        if not downloadids or not videos:
            return
        if len(downloadids) != 1 or len(videos) != 1:
            log.warning(
                "Ambiguous dframe/video pairing in vertical '%s': %d dframe(s), %d video(s) — skipping tuddownloadid",
                vertical_name,
                len(downloadids),
                len(videos),
            )
            return
        videos[0]["tuddownloadid"] = downloadids[0]

    def _parse_component(
        self,
        root: Path,
        child: ET.Element,
        vertical_name: str = "",
        sequential_name: str = "",
        chapter_name: str = "",
    ) -> dict | None:
        """Dispatch one OLX component to its supported parser."""
        url_name = child.get("url_name", "")
        match child.tag:
            case "html":
                return self._parse_html(
                    root, url_name, vertical_name, sequential_name, chapter_name
                )
            case "video":
                return self._parse_video(
                    root, url_name, vertical_name, sequential_name, chapter_name
                )
            case tag if tag in _BLACKLISTED_TAGS:
                log.debug(
                    "Skipping unsupported component type '%s' (url_name='%s') in vertical '%s'",
                    child.tag,
                    url_name,
                    vertical_name,
                )
                return None
            case _:
                log.warning(
                    "Unhandled OLX component tag '<%s>' in vertical '%s'",
                    child.tag,
                    vertical_name,
                )
                return None

    def _parse_html(
        self,
        root: Path,
        url_name: str,
        vertical_name: str = "",
        sequential_name: str = "",
        chapter_name: str = "",
    ) -> dict:
        """Read one HTML component and resolve its referenced assets."""
        path = root / "html" / f"{url_name}.xml"
        if not path.exists():
            raise FileNotFoundError(f"Missing HTML XML: {url_name}")
        el = ET.parse(path).getroot()
        filename = el.get("filename", url_name)
        html_path = root / "html" / f"{filename}.html"
        content = self._bundle_dacg(
            html_path.read_text(encoding="utf-8") if html_path.exists() else ""
        )

        for match in _ABSOLUTE_ASSET_RE.finditer(content):
            absolute_url, name = match.group(0), match.group(1)
            if name in self.static_files:
                continue
            fetched = self.fetcher.fetch(absolute_url) if self.fetcher else None
            if fetched is not None:
                self.static_files[name] = fetched
                continue
            log.warning(
                "Parsing OLX: Missing %s '%s' at chapter '%s', sequential '%s', on page '%s'",
                static_file_kind(name),
                name,
                chapter_name,
                sequential_name or url_name,
                vertical_name or url_name,
            )

        asset_ref_re = r'(?:/static/|asset-v1:[^"\'>\s]*?type@asset\+block@|/c4x/[^"\'>\s]*/asset/)([^"\'>\s]+)'
        for match in re.findall(asset_ref_re, content):
            if match not in self.static_files:
                log.warning(
                    "Parsing OLX: Missing %s '%s' at chapter '%s', sequential '%s', on page '%s'",
                    static_file_kind(match),
                    match,
                    chapter_name,
                    sequential_name or url_name,
                    vertical_name or url_name,
                )
        return {
            "type": "html",
            "url_name": url_name,
            "display_name": el.get("display_name", ""),
            "content": content,
        }

    def _parse_video(
        self,
        root: Path,
        url_name: str,
        vertical_name: str = "",
        sequential_name: str = "",
        chapter_name: str = "",
    ) -> dict:
        """Read one OLX video component and construct its video-routing record."""
        path = root / "video" / f"{url_name}.xml"
        if not path.exists():
            raise FileNotFoundError(f"Missing Video XML: {url_name}")
        el = ET.parse(path).getroot()

        edx_video_id = el.get("edx_video_id") or None
        youtubeid = el.get("youtube_id_1_0") or None
        if not youtubeid:
            # Format: youtube="1.00:_tX7iFAJvZY"
            youtube_attr = el.get("youtube", "")
            if ":" in youtube_attr:
                youtubeid = youtube_attr.rsplit(":", 1)[1] or None

        return {
            "type": "video",
            "url_name": url_name,
            "display_name": el.get("display_name", ""),
            "vidkey": safe_vidkey(edx_video_id or url_name),
            "youtubeid": youtubeid,
            "edxvideoid": edx_video_id,
            "srtbaseid": edx_video_id,
            "tuddownloadid": None,
            "collegeramaid": None,
            "urlname": url_name,
            "videopagepath": f"{chapter_name} > {sequential_name} > {vertical_name}",
        }
