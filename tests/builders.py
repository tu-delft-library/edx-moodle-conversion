import shutil
import tarfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HtmlComponent:
    url_name: str
    display_name: str
    content: str = "<p>Test content</p>"


@dataclass
class VideoComponent:
    url_name: str
    display_name: str
    youtube_id: str = "dQw4w9WgXcQ"


@dataclass
class Vertical:
    url_name: str
    display_name: str
    components: list = field(default_factory=list)


@dataclass
class Sequential:
    url_name: str
    display_name: str
    verticals: list[Vertical] = field(default_factory=list)


@dataclass
class Chapter:
    url_name: str
    display_name: str
    sequentials: list[Sequential] = field(default_factory=list)


class OLXFixtureBuilder:
    def __init__(self, root: Path):
        self.root = root
        self.course_id = "TEST101"
        self.course_name = "Test Course"
        self.chapters: list[Chapter] = []
        self.static_files: dict[str, bytes] = {}

    def build(self) -> Path:
        shutil.rmtree(self.root, ignore_errors=True)
        self.root.mkdir(parents=True, exist_ok=True)
        self._write_course_xml()
        for ch in self.chapters:
            self._write_chapter(ch)
        for name, data in self.static_files.items():
            static = self.root / "static"
            static.mkdir(exist_ok=True)
            (static / name).write_bytes(data)
        return self.root

    def as_tar(self, out: Path) -> Path:
        with tarfile.open(out, "w:gz") as tar:
            tar.add(self.root, arcname=self.root.name)
        return out

    def _write_course_xml(self):
        d = self.root / "course"
        d.mkdir(exist_ok=True)
        (d / "course.xml").write_text(
            f'<course url_name="run" course="{self.course_id}" display_name="{self.course_name}"/>'
        )
        chapter_tags = "\n  ".join(f'<chapter url_name="{ch.url_name}"/>' for ch in self.chapters)
        (d / "run.xml").write_text(
            f'<course display_name="{self.course_name}" course="{self.course_id}">\n  {chapter_tags}\n</course>'
        )

    def _write_chapter(self, ch: Chapter):
        d = self.root / "chapter"
        d.mkdir(exist_ok=True)
        seq_tags = "\n  ".join(f'<sequential url_name="{s.url_name}"/>' for s in ch.sequentials)
        (d / f"{ch.url_name}.xml").write_text(
            f'<chapter display_name="{ch.display_name}">\n  {seq_tags}\n</chapter>'
        )
        for seq in ch.sequentials:
            self._write_sequential(seq)

    def _write_sequential(self, seq: Sequential):
        d = self.root / "sequential"
        d.mkdir(exist_ok=True)
        vert_tags = "\n  ".join(f'<vertical url_name="{v.url_name}"/>' for v in seq.verticals)
        (d / f"{seq.url_name}.xml").write_text(
            f'<sequential display_name="{seq.display_name}">\n  {vert_tags}\n</sequential>'
        )
        for vert in seq.verticals:
            self._write_vertical(vert)

    def _write_vertical(self, vert: Vertical):
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

    def _write_html(self, c: HtmlComponent):
        d = self.root / "html"
        d.mkdir(exist_ok=True)
        (d / f"{c.url_name}.xml").write_text(
            f'<html display_name="{c.display_name}" filename="{c.url_name}"/>'
        )
        (d / f"{c.url_name}.html").write_text(c.content)

    def _write_video(self, c: VideoComponent):
        d = self.root / "video"
        d.mkdir(exist_ok=True)
        (d / f"{c.url_name}.xml").write_text(
            f'<video display_name="{c.display_name}" youtube_id_1_0="{c.youtube_id}"/>'
        )
