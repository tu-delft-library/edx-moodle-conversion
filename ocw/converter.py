import logging
import mimetypes
import os
import shutil
import tarfile
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

from ocw import templates
from ocw.parser import Course
from ocw.utils import _Counter, esc, rewrite_static_urls, sha1_of

load_dotenv()
MOODLE_VERSION = os.getenv("MOODLE_VERSION", "2025100601")

#TODO: Pydocs for all and proper hinting for all

class MBZBuilder:
    """Converts a parsed Course into a Moodle MBZ backup archive."""

    def __init__(self, course: Course) -> None:
        self.course = course
        self.log = logging.getLogger("ocw.converter")

    def build(self, out: Path) -> None:
        """Write the MBZ archive to out."""
        tmp = Path(tempfile.mkdtemp())
        try:
            self._populate(tmp)
            with tarfile.open(out, "w:gz") as tar:
                for item in sorted(tmp.rglob("*")):
                    tar.add(item, arcname=str(item.relative_to(tmp)), recursive=False)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _populate(self, tmp: Path) -> None:
        ids = _Counter()
        ts = int(time.time())
        c = self.course

        sections = [{"id": ids.next(), "name": ch["display_name"], "modules": []} for ch in c.chapters]

        pages = []
        for i, ch in enumerate(c.chapters):
            for seq in ch["sequentials"]:
                for vert in seq["verticals"]:
                    for comp in vert["components"]:
                        mod_id, ctx_id = ids.next(), ids.next()
                        if comp["type"] == "html":
                            content = rewrite_static_urls(comp["content"])
                        elif comp["type"] == "video":
                            yt = esc(comp["youtube_id"])
                            content = f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{yt}" allowfullscreen></iframe>'
                        else:
                            raise ValueError(f"unsupported component type: {comp['type']}")
                        pages.append({"id": mod_id, "ctx": ctx_id, "sec_id": sections[i]["id"], "name": comp["display_name"], "content": content})
                        sections[i]["modules"].append(mod_id)

        #TODO: Descriptive comment
        file_entries = []
        for name, path in c.static_files.items():
            sha1 = sha1_of(path)
            mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
            file_entries.append({"id": ids.next(), "sha1": sha1, "name": name, "size": path.stat().st_size, "mime": mime, "path": path})

        #TODO: Descriptive comment
        self._write_moodle_backup(tmp, c, sections, pages, ts)
        self._write_course_xml(tmp, c, ts)
        for idx, sec in enumerate(sections):
            self._write_section(tmp, sec, idx + 1)
        for page in pages:
            self._write_page(tmp, page, ts)
        self._write_files_xml(tmp, file_entries, ts)
        self._copy_static(tmp, file_entries)

    def _write_moodle_backup(self, tmp: Path, c: Course, sections: list, pages: list, ts: int) -> None:
        acts = "\n".join(
            f'      <activity><moduleid>{p["id"]}</moduleid><sectionid>{p["sec_id"]}</sectionid>'
            f'<modulename>page</modulename><title>{esc(p["name"])}</title>'
            f'<directory>activities/page_{p["id"]}</directory></activity>'
            for p in pages
        )
        secs = "\n".join(
            f'      <section><sectionid>{s["id"]}</sectionid><title>{esc(s["name"])}</title>'
            f'<directory>sections/section_{s["id"]}</directory></section>'
            for s in sections
        )
        xml = templates.MOODLE_BACKUP.format(
            course_name=esc(c.course_name),
            course_id=esc(c.course_id),
            moodle_version=MOODLE_VERSION,
            ts=ts,
            acts=acts,
            secs=secs,
        )
        (tmp / "moodle_backup.xml").write_text(xml, encoding="utf-8")

    def _write_course_xml(self, tmp: Path, c: Course, ts: int) -> None:
        (tmp / "course").mkdir(exist_ok=True)
        xml = templates.COURSE_XML.format(course_id=esc(c.course_id), course_name=esc(c.course_name), ts=ts)
        (tmp / "course" / "course.xml").write_text(xml, encoding="utf-8")

    def _write_section(self, tmp: Path, sec: dict, idx: int) -> None:
        d = tmp / "sections" / f"section_{sec['id']}"
        d.mkdir(parents=True, exist_ok=True)
        xml = templates.SECTION_XML.format(
            id=sec["id"],
            number=idx,
            name=esc(sec["name"]),
            sequence=",".join(str(m) for m in sec["modules"]),
        )
        (d / "section.xml").write_text(xml, encoding="utf-8")

    def _write_page(self, tmp: Path, page: dict, ts: int) -> None:
        d = tmp / "activities" / f"page_{page['id']}"
        d.mkdir(parents=True, exist_ok=True)
        xml = templates.PAGE_XML.format(id=page["id"], ctx=page["ctx"], name=esc(page["name"]), content=esc(page["content"]), ts=ts)
        (d / "page.xml").write_text(xml, encoding="utf-8")
        (d / "inforef.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<inforef/>', encoding="utf-8")

    def _write_files_xml(self, tmp: Path, file_entries: list, ts: int) -> None:
        entries = "\n".join(
            templates.FILE_ENTRY.format(id=f["id"], sha1=f["sha1"], name=esc(f["name"]), size=f["size"], mime=esc(f["mime"]), ts=ts)
            for f in file_entries
        )
        (tmp / "files.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<files>\n{entries}\n</files>',
            encoding="utf-8"
        )

    def _copy_static(self, tmp: Path, file_entries: list) -> None:
        files_dir = tmp / "files"
        for f in file_entries:
            dest = files_dir / f["sha1"][:2]
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f["path"], dest / f["sha1"])
