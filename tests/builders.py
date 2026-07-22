import html
import json
import shutil
import tarfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HtmlComponent:
    """An OLX html component referencing an external .html file."""
    url_name: str
    display_name: str
    content: str = "<p>Test content</p>"


@dataclass
class VideoComponent:
    """An OLX video component with a YouTube ID."""
    url_name: str
    display_name: str
    youtube_id: str = "dQw4w9WgXcQ"


@dataclass
class Vertical:
    """An OLX vertical (unit) containing html/video components."""
    url_name: str
    display_name: str
    components: list[HtmlComponent | VideoComponent] = field(default_factory=list)


@dataclass
class Sequential:
    """An OLX sequential (subsection) containing verticals."""
    url_name: str
    display_name: str
    verticals: list[Vertical] = field(default_factory=list)


@dataclass
class Chapter:
    """An OLX chapter (section) containing sequentials."""
    url_name: str
    display_name: str
    sequentials: list[Sequential] = field(default_factory=list)


@dataclass
class StaticTab:
    """A policy.json static_tab entry (e.g. Syllabus)."""
    name: str
    url_slug: str


@dataclass
class PdfTextbook:
    """A pdf_textbooks[] entry on the course run XML root (findings_overview_policies.md §1, Pattern A)."""
    tab_title: str
    chapters: list[dict]  # [{"title": ..., "url": "/static/..."}]
    id: str = "9Readings"


class OLXFixtureBuilder:
    """Writes a valid OLX directory tree from a dataclass course description."""

    def __init__(self, root: Path) -> None:
        """
        Args:
            root: Directory to write the OLX tree into. Wiped on each build().
        """
        self.root = root
        self.course_id: str = "TEST101"
        self.course_name: str = "Test Course"
        self.run_name: str = "run"
        self.chapters: list[Chapter] = []
        self.static_files: dict[str, bytes] = {}
        self.static_tabs: list[StaticTab] = []
        self.tabs_files: dict[str, str] = {}
        self.pdf_textbooks: list[PdfTextbook] = []

    def build(self) -> Path:
        """Write the OLX tree to self.root and return it."""
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)
        self._write_course_xml()
        for ch in self.chapters:
            self._write_chapter(ch)
        for name, data in self.static_files.items():
            static = self.root / "static"
            static.mkdir(exist_ok=True)
            (static / name).write_bytes(data)
        self._write_policy()
        self._write_tabs()
        return self.root

    def as_tar(self, out: Path | None = None) -> Path:
        """Package self.root as a .tar.gz. Defaults to alongside self.root."""
        if out is None:
            out = self.root.parent / f"{self.root.name}.tar.gz"
        with tarfile.open(out, "w:gz") as tar:
            tar.add(self.root, arcname=self.root.name)
        return out

    def _write_course_xml(self) -> None:
        d = self.root / "course"
        d.mkdir(exist_ok=True)
        (d / "course.xml").write_text(
            f'<course url_name="{self.run_name}" course="{self.course_id}" display_name="{self.course_name}"/>'
        )
        chapter_tags = "\n  ".join(f'<chapter url_name="{ch.url_name}"/>' for ch in self.chapters)
        pdf_textbooks_attr = ""
        if self.pdf_textbooks:
            payload = [
                {"tab_title": t.tab_title, "chapters": t.chapters, "id": t.id}
                for t in self.pdf_textbooks
            ]
            pdf_textbooks_attr = f' pdf_textbooks="{html.escape(json.dumps(payload), quote=True)}"'
        (d / f"{self.run_name}.xml").write_text(
            f'<course display_name="{self.course_name}" course="{self.course_id}"{pdf_textbooks_attr}>\n  {chapter_tags}\n</course>'
        )

    def _write_policy(self) -> None:
        if not self.static_tabs:
            return
        d = self.root / "policies" / self.run_name
        d.mkdir(parents=True, exist_ok=True)
        tabs = [
            {"type": "static_tab", "name": tab.name, "url_slug": tab.url_slug}
            for tab in self.static_tabs
        ]
        policy = {f"course/{self.run_name}": {"tabs": tabs}}
        (d / "policy.json").write_text(json.dumps(policy))

    def _write_tabs(self) -> None:
        if not self.tabs_files:
            return
        d = self.root / "tabs"
        d.mkdir(exist_ok=True)
        for slug, content in self.tabs_files.items():
            (d / f"{slug}.html").write_text(content)

    def _write_chapter(self, ch: Chapter) -> None:
        d = self.root / "chapter"
        d.mkdir(exist_ok=True)
        seq_tags = "\n  ".join(f'<sequential url_name="{s.url_name}"/>' for s in ch.sequentials)
        (d / f"{ch.url_name}.xml").write_text(
            f'<chapter display_name="{ch.display_name}">\n  {seq_tags}\n</chapter>'
        )
        for seq in ch.sequentials:
            self._write_sequential(seq)

    def _write_sequential(self, seq: Sequential) -> None:
        d = self.root / "sequential"
        d.mkdir(exist_ok=True)
        vert_tags = "\n  ".join(f'<vertical url_name="{v.url_name}"/>' for v in seq.verticals)
        (d / f"{seq.url_name}.xml").write_text(
            f'<sequential display_name="{seq.display_name}">\n  {vert_tags}\n</sequential>'
        )
        for vert in seq.verticals:
            self._write_vertical(vert)

    def _write_vertical(self, vert: Vertical) -> None:
        d = self.root / "vertical"
        d.mkdir(exist_ok=True)
        comp_tags = []
        for c in vert.components:
            if isinstance(c, HtmlComponent):
                comp_tags.append(f'<html url_name="{c.url_name}"/>')
                self._write_html(c)
            elif isinstance(c, VideoComponent):
                comp_tags.append(f'<video url_name="{c.url_name}"/>')
                self._write_video(c)
        (d / f"{vert.url_name}.xml").write_text(
            f'<vertical display_name="{vert.display_name}">\n  '
            + "\n  ".join(comp_tags)
            + "\n</vertical>"
        )

    def _write_html(self, c: HtmlComponent) -> None:
        d = self.root / "html"
        d.mkdir(exist_ok=True)
        (d / f"{c.url_name}.xml").write_text(
            f'<html display_name="{c.display_name}" filename="{c.url_name}"/>'
        )
        (d / f"{c.url_name}.html").write_text(c.content)

    def _write_video(self, c: VideoComponent) -> None:
        d = self.root / "video"
        d.mkdir(exist_ok=True)
        (d / f"{c.url_name}.xml").write_text(
            f'<video display_name="{c.display_name}" youtube_id_1_0="{c.youtube_id}"/>'
        )
