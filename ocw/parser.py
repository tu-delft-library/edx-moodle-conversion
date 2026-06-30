import logging
import re
from pathlib import Path
from xml.etree import ElementTree as ET

from ocw.utils import static_file_kind

log = logging.getLogger("ocw.parser")


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

        static_dir = self.root / "static"

        # Record all static content: images
        if static_dir.is_dir():
            for f in static_dir.iterdir():
                if f.is_file():
                    self.static_files[f.name] = f
                    self.static_files[f.name.replace(" ", "_")] = f

        # Record all chapters, which contain the XML linking to all sequences (sub sections)
        for ref in course.findall("chapter"):
            self.chapters.append(self._parse_chapter(self.root, ref.get("url_name", "")))


    def _parse_chapter(self, root: Path, url_name: str) -> dict:
        path = root / "chapter" / f"{url_name}.xml"
        if not path.exists():
            raise FileNotFoundError(f"Missing Chapter XML: {url_name}")
        el = ET.parse(path).getroot()
        sequentials = []
        chapter_name = el.get("display_name", url_name)
        # So this finds all sequential keys in the XML element, records them
        for ref in el.findall("sequential"):
            sequentials.append(self._parse_sequential(root, ref.get("url_name", ""), chapter_name))
        return {
            "url_name": url_name,
            "display_name": el.get("display_name", ""),
            "sequentials": sequentials,
        }

    def _parse_sequential(self, root: Path, url_name: str, chapter_name: str = "") -> dict:
        path = root / "sequential" / f"{url_name}.xml"
        if not path.exists():
            raise FileNotFoundError(f"Missing Sequential XML: {url_name}")
        el = ET.parse(path).getroot()
        verticals = []
        sequential_name = el.get("display_name", url_name)
        # This finds all the verticles, which are wrappers around the html content that each sub section links to
        for ref in el.findall("vertical"):
            verticals.append(self._parse_vertical(root, ref.get("url_name", ""), chapter_name, sequential_name))
        return {
            "url_name": url_name,
            "display_name": el.get("display_name", ""),
            "verticals": verticals,
        }

    def _parse_vertical(self, root: Path, url_name: str, chapter_name: str = "", sequential_name: str = "") -> dict:
        path = root / "vertical" / f"{url_name}.xml"
        if not path.exists():
            raise FileNotFoundError(f"Missing Vertical XML: {url_name}")
        el = ET.parse(path).getroot()
        display_name = el.get("display_name", "")
        components = []
        for child in el:
            if child.tag == "html":
                components.append(self._parse_html(root, child.get("url_name", ""), display_name, sequential_name, chapter_name))
            elif child.tag == "video":
                # TODO: For future this is more complicated
                pass
                # c = self._parse_video(root, child.get("url_name", ""))
                # if c is not None:
                #     components.append(c)

            # SK1: problem, discussion, drag-and-drop, advanced — silently skipped
        return {
            "url_name": url_name,
            "display_name": display_name,
            "components": components,
        }

    def _parse_html(self, root: Path, url_name: str, vertical_name: str = "", sequential_name: str = "", chapter_name: str = "") -> dict:
        path = root / "html" / f"{url_name}.xml"
        if not path.exists():
            raise FileNotFoundError(f"Missing HTML XML: {url_name}")
        el = ET.parse(path).getroot()
        filename = el.get("filename", url_name)
        html_path = root / "html" / f"{filename}.html"
        content = html_path.read_text(encoding="utf-8") if html_path.exists() else ""
        for match in re.findall(r'/static/([^"\'>\s]+)', content):
            if match not in self.static_files:
                log.warning(
                    "Parsing OLX: Missing %s '%s' at chapter '%s', sequential '%s', on page '%s'",
                    static_file_kind(match), match,
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
