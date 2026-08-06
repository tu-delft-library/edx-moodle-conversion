import json
import logging
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from ocw.utils import static_file_kind

log = logging.getLogger("ocw.parser")

_VIDKEY_UNSAFE_RE = re.compile(r"[^A-Za-z0-9_-]")


def _safe_vidkey(raw: str) -> str:
    log.debug("hi")
    return _VIDKEY_UNSAFE_RE.sub("_", raw)


def _find_dframe_downloadids(html: str) -> list[str]:
    ids = []
    for tag_match in Course._DFRAME_RE.finditer(html):
        id_match = Course._DOWNLOADID_RE.search(tag_match.group(0))
        if id_match:
            ids.append(id_match.group(1))
    return ids


class Course:
    """Parses an OpenEdX OLX course export into a structured representation."""

    _DFRAME_RE = re.compile(
        r'<iframe\b[^>]*class="[^"]*\bdframe\b[^"]*"[^>]*>', re.IGNORECASE
    )
    _DOWNLOADID_RE = re.compile(r'data-downloadid="([^"]*)"')

    # Tags the parser actively converts into page content.
    _WHITELISTED_TAGS = frozenset({"html", "video"})

    # Known tags with no sane Moodle equivalent — dropped silently (debug only).
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
        self.syllabus_html: str | None = None
        self.syllabus_title: str = "Syllabus"
        self.readings: list[dict] = []
        self.videos: list[dict] = []
        self.org: str = ""
        self.language: str = ""
        self.license: str = ""
        self.summary_html: str | None = None
        self.instructors: list[dict] = []
        self._b64_tmp_dir: Path | None = None

    def parse(self) -> None:
        """Populate course metadata, chapters, and static_files from the OLX tree.
        General flow takes the url-links from the parent xml file, and searches for child elements.
        These are saved in this intermediate class as dictionaries roughly matching the original structure of the OLX format.
        """
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

        # Record all static content: images
        if static_dir.is_dir():
            for f in static_dir.iterdir():
                if f.is_file():
                    self.static_files[f.name] = f
                    self.static_files[re.sub(r"[^-\w.]", "_", f.name)] = f

        # Record all chapters, which contain the XML linking to all sequences (sub sections)
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
        """Populate summary_html from about/short_description.html, falling back to overview.html."""
        for name in ("short_description.html", "overview.html"):
            path = self.root / "about" / name
            if path.exists() and path.read_text(encoding="utf-8").strip():
                self.summary_html = path.read_text(encoding="utf-8")
                return

    def _parse_syllabus(self, url_name: str) -> None:
        """Populate syllabus_html/syllabus_title from policy.json's static_tab
        entry, if one is configured, and instructors from instructor_info.
        """
        policy_path = self.root / "policies" / url_name / "policy.json"
        if not policy_path.exists():
            return
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        course_policy = policy.get(f"course/{url_name}", {})
        self.instructors = course_policy.get("instructor_info", {}).get("instructors", [])
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
        self.syllabus_html = tab_path.read_text(encoding="utf-8")
        self.syllabus_title = tab.get("name") or "Syllabus"

    def _parse_readings(self, course: ET.Element) -> None:
        """Populate self.readings by flattening every pdf_textbooks[].chapters[]
        entry on the course run XML root (the same element course_name/course_id
        are already read from in parse()). Not policy.json-resident — see
        findings_overview_policies.md §1, Pattern A. Missing attribute is a
        silent no-op, same as syllabus: Readings is optional course chrome, not
        required structure. A chapter entry whose PDF isn't found in
        static_files is dropped (warned, not raised) rather than emitted with a
        dangling reference — unlike prose HTML links, a Readings entry becomes
        a whole mod_resource activity 1:1, so there's no sensible degraded
        output for a resource with nothing to attach.
        """
        raw = course.get("pdf_textbooks")
        if not raw:
            return
        for textbook in json.loads(raw):
            for chapter in textbook.get("chapters", []):
                url = chapter.get("url", "")
                name = url.removeprefix("/static/")
                if name not in self.static_files:
                    log.warning(
                        "Parsing OLX: Missing %s '%s' for Readings entry '%s'",
                        static_file_kind(name),
                        name,
                        chapter.get("title", ""),
                    )
                    continue
                self.readings.append({"title": chapter.get("title", ""), "name": name})

    def _parse_chapter(self, root: Path, url_name: str) -> dict:
        path = root / "chapter" / f"{url_name}.xml"
        if not path.exists():
            raise FileNotFoundError(f"Missing Chapter XML: {url_name}")
        el = ET.parse(path).getroot()
        sequentials = []
        chapter_name = el.get("display_name", url_name)
        # So this finds all sequential keys in the XML element, records them
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
        path = root / "sequential" / f"{url_name}.xml"
        if not path.exists():
            raise FileNotFoundError(f"Missing Sequential XML: {url_name}")
        el = ET.parse(path).getroot()
        verticals = []
        sequential_name = el.get("display_name", url_name)
        # This finds all the verticles, which are wrappers around the html content that each sub section links to
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
        return {
            "url_name": url_name,
            "display_name": display_name,
            "components": components,
        }

    def _attach_video_download_ids(
        self, components: list[dict], vertical_name: str = ""
    ) -> None:
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
            case tag if tag in self._BLACKLISTED_TAGS:
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
        path = root / "html" / f"{url_name}.xml"
        if not path.exists():
            raise FileNotFoundError(f"Missing HTML XML: {url_name}")
        el = ET.parse(path).getroot()
        filename = el.get("filename", url_name)
        html_path = root / "html" / f"{filename}.html"
        content = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
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
            "vidkey": _safe_vidkey(edx_video_id or url_name),
            "youtubeid": youtubeid,
            "edxvideoid": edx_video_id,
            "stlbaseid": edx_video_id,  
            "tuddownloadid": None,  # filled in by _attach_video_download_ids
            "urlname": url_name,
            "videopagepath": f"{chapter_name} > {sequential_name} > {vertical_name}",
        }
