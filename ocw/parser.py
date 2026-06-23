import logging
import re
import tarfile
import tempfile
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

log = logging.getLogger("ocw.parser")
# TODO: Throw an exception for all cases that return None for a url link


class Course:
    """Parses an OpenEdX OLX course export into a structured representation."""

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
        self._b64_tmp_dir: Optional[Path] = None

    def parse(self) -> None:
        """Populate course metadata, chapters, and static_files from the OLX tree.
        General flow takes the url-links from the parent xml file, and searches for child elements.
        These are saved in this intermediate class as dictionaries roughly matching the original structure of the OLX format.
        """
        # base_path = #self._resolve_root()

        stub_path = self.root / "course.xml"
        if not stub_path.exists():
            stub_path = base_path / "course" / "course.xml"

        stub = ET.parse(stub_path).getroot()
        url_name = stub.get("course", "")

        course = ET.parse(stub_path / "course" / f"{url_name}.xml").getroot()
        self.course_name = course.get("display_name", "")

        static_dir = base_path / "static"
        # Record all static content: images
        if static_dir.is_dir():
            for f in static_dir.iterdir():
                if f.is_file():
                    self.static_files[f.name] = f

        # Record all chapters, which contain the XML linking to all sequences (sub sections)
        for ref in course.findall("chapter"):
            ch = self._parse_chapter(olx, ref.get("url_name", ""))
            if ch is not None:
                self.chapters.append(ch)

    # def _resolve_root(self) -> Path:
    #     """Figures out the root path of the import OLX file"""
    #
    def _parse_chapter(self, root: Path, url_name: str) -> Optional[dict]:
        path = root / "chapter" / f"{url_name}.xml"
        if not path.exists():
            # NOTE: For future errors: This is specifically an error within the OLX export not the conversion
            log.warning("Missing Chapter %s", url_name)
            return None
        el = ET.parse(path).getroot()
        sequentials = []
        # So this finds all sequential keys in the XML element, records them
        for ref in el.findall("sequential"):
            s = self._parse_sequential(root, ref.get("url_name", ""))
            if s is not None:
                sequentials.append(s)
        return {
            "url_name": url_name,
            "display_name": el.get("display_name", ""),
            "sequentials": sequentials,
        }

    def _parse_sequential(self, root: Path, url_name: str) -> Optional[dict]:
        path = root / "sequential" / f"{url_name}.xml"
        if not path.exists():
            # NOTE: For future errors: This is specifically an error within the OLX export not the conversion
            log.warning("Missing sequential %s", url_name)
            return None
        el = ET.parse(path).getroot()
        verticals = []
        # This finds all the verticles, which are wrappers around the html content that each sub section links to
        for ref in el.findall("vertical"):
            v = self._parse_vertical(root, ref.get("url_name", ""))
            if v is not None:
                verticals.append(v)
        return {
            "url_name": url_name,
            "display_name": el.get("display_name", ""),
            "verticals": verticals,
        }

    def _parse_vertical(self, root: Path, url_name: str) -> Optional[dict]:
        path = root / "vertical" / f"{url_name}.xml"
        if not path.exists():
            log.warning("Missing vertical %s", url_name)
            return None
        el = ET.parse(path).getroot()
        components = []
        for child in el:
            if child.tag == "html":
                c = self._parse_html(root, child.get("url_name", ""))
                if c is not None:
                    components.append(c)
            elif child.tag == "video":
                # TODO: For future this is more complicated
                pass
                # c = self._parse_video(root, child.get("url_name", ""))
                # if c is not None:
                #     components.append(c)

            # SK1: problem, discussion, drag-and-drop, advanced — silently skipped
        return {
            "url_name": url_name,
            "display_name": el.get("display_name", ""),
            "components": components,
        }

    def _parse_html(self, root: Path, url_name: str) -> Optional[dict]:
        path = root / "html" / f"{url_name}.xml"
        if not path.exists():
            log.warning("missing html %s", url_name)
            return None
        el = ET.parse(path).getroot()
        filename = el.get("filename", url_name)
        html_path = root / "html" / f"{filename}.html"
        content = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
        for match in re.findall(r'/static/([^"\'>\s]+)', content):
            if match not in self.static_files:
                log.warning(
                    "C1: missing static file %s referenced in %s", match, url_name
                )
        return {
            "type": "html",
            "url_name": url_name,
            "display_name": el.get("display_name", ""),
            "content": content,
        }
