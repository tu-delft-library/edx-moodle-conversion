import logging
import mimetypes
import os
import re
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
MOODLE_VERSION = os.getenv("MOODLE_VERSION", "2024042212")


class MBZBuilder:
    """Converts a parsed Course into a Moodle MBZ backup archive."""

    def __init__(self, course: Course, *, sequential_sections: bool = False) -> None:
        self.course = course
        self.sequential_sections = sequential_sections
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

    #TODO: Getting too big; refactor, id prefer if this was broken down into a proper chain of sequences, such that if one fails its very obvious where and why, maybe an observer pattern but i might be overcomplicating it
    def _populate(self, tmp: Path) -> None:
        """Build the full MBZ directory tree in tmp."""
        ids = _Counter()
        ts = int(time.time())
        c = self.course

        if self.sequential_sections:
            sections, sec_idx_for = [], {}
            for ch in c.chapters:
                for seq in ch["sequentials"]:
                    sec_idx_for[id(seq)] = len(sections)
                    sections.append({"id": ids.next(), "name": f"{ch['display_name']} - {seq['display_name']}", "modules": []})
        else:
            sections, sec_idx_for = [], {}
            for i, ch in enumerate(c.chapters):
                sections.append({"id": ids.next(), "name": ch["display_name"], "modules": []})
                for seq in ch["sequentials"]:
                    sec_idx_for[id(seq)] = i

        pages = []
        for ch in c.chapters:
            for seq in ch["sequentials"]:
                si = sec_idx_for[id(seq)]
                for vert in seq["verticals"]:
                    html_parts = [
                        self._fix_unsized_base64_imgs(rewrite_static_urls(comp["content"]))
                        for comp in vert["components"]
                        if comp["type"] == "html"
                    ]
                    if not html_parts:
                        continue
                    mod_id, ctx_id = ids.next(), ids.next()
                    combined = "".join(html_parts)
                    file_refs = re.findall(r'@@PLUGINFILE@@/([^"\'>\s]+)', combined)
                    pages.append({"id": mod_id, "ctx": ctx_id, "sec_id": sections[si]["id"], "sec_num": si + 1, "name": vert["display_name"], "content": combined, "file_refs": file_refs, "file_ids": []})
                    sections[si]["modules"].append(mod_id)

        # sha1 + mime metadata for files.xml — one entry per (page, filename) with correct ctx
        file_entries = []
        for page in pages:
            for name in page["file_refs"]:
                path = c.static_files.get(name)
                if path is None:
                    continue
                sha1 = sha1_of(path)
                mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
                fid = ids.next()
                file_entries.append({"id": fid, "sha1": sha1, "name": name, "size": path.stat().st_size, "mime": mime, "path": path, "ctx": page["ctx"]})
                page["file_ids"].append(fid)

        self._write_moodle_backup(tmp, c, sections, pages, ts)
        self._write_static_manifests(tmp)
        self._write_course_xml(tmp, c, ts)
        for idx, sec in enumerate(sections):
            self._write_section(tmp, sec, idx + 1, ts)
        for page in pages:
            self._write_page(tmp, page, ts)
        self._write_files_xml(tmp, file_entries, ts)
        self._copy_static(tmp, file_entries)

    def _fix_unsized_base64_imgs(self, html: str) -> str:
        # base64 imgs with no width/height render at native pixel size in Moodle;
        # constrain them to the page container width
        def _inject(m: re.Match) -> str:
            tag = m.group(0)
            if 'width=' in tag or 'height=' in tag:
                # already explicitly sized — leave alone
                return tag
            if 'style=' in tag:
                # prepend to existing style block
                return re.sub(r'style="', 'style="max-width:100%;', tag, count=1)
            # no style attr at all — add one
            return tag.replace('<img ', '<img style="max-width:100%" ', 1)
        return re.sub(r'<img\b[^>]*\bsrc="data:image/[^>]*>', _inject, html)

    def _write_moodle_backup(self, tmp: Path, c: Course, sections: list, pages: list, ts: int) -> None:
        """Write moodle_backup.xml with activity and section manifests."""
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
        root_settings = [
            ("filename", esc(c.course_name)),
            ("imscc11", "0"), ("users", "0"), ("anonymize", "0"),
            ("role_assignments", "0"), ("activities", "1"), ("blocks", "1"),
            ("filters", "1"), ("comments", "0"), ("badges", "0"),
            ("calendarevents", "0"), ("userscompletion", "0"), ("logs", "0"),
            ("grade_histories", "0"), ("questionbank", "1"), ("groups", "1"),
            ("competencies", "0"), ("customfield", "1"),
        ]
        setting_lines = [
            f'      <setting><level>root</level><name>{k}</name><value>{v}</value></setting>'
            for k, v in root_settings
        ]
        for sec in sections:
            sid = f"section_{sec['id']}"
            setting_lines += [
                f'      <setting><level>section</level><section>{sid}</section><name>{sid}_included</name><value>1</value></setting>',
                f'      <setting><level>section</level><section>{sid}</section><name>{sid}_userinfo</name><value>0</value></setting>',
            ]
        for page in pages:
            aid = f"page_{page['id']}"
            setting_lines += [
                f'      <setting><level>activity</level><activity>{aid}</activity><name>{aid}_included</name><value>1</value></setting>',
                f'      <setting><level>activity</level><activity>{aid}</activity><name>{aid}_userinfo</name><value>0</value></setting>',
            ]
        xml = templates.MOODLE_BACKUP.format(
            course_name=esc(c.course_name),
            course_id=esc(c.course_id),
            moodle_version=MOODLE_VERSION,
            ts=ts,
            acts=acts,
            secs=secs,
            settings="\n".join(setting_lines),
        )
        (tmp / "moodle_backup.xml").write_text(xml, encoding="utf-8")

    def _write_static_manifests(self, tmp: Path) -> None:
        """Write required root-level XML stubs that have no OLX equivalent."""
        for name, content in (
            ("roles.xml", templates.ROLES_XML),
            ("gradebook.xml", templates.GRADEBOOK_XML),
            ("grade_history.xml", templates.GRADE_HISTORY_XML),
            ("groups.xml", templates.GROUPS_XML),
            ("outcomes.xml", templates.OUTCOMES_XML),
            ("questions.xml", templates.QUESTIONS_XML),
            ("scales.xml", templates.SCALES_XML),
        ):
            (tmp / name).write_text(content, encoding="utf-8")

    def _write_course_xml(self, tmp: Path, c: Course, ts: int) -> None:
        d = tmp / "course"
        d.mkdir(exist_ok=True)
        (d / "course.xml").write_text(
            templates.COURSE_XML.format(course_id=esc(c.course_id), course_name=esc(c.course_name), ts=ts),
            encoding="utf-8",
        )
        (d / "roles.xml").write_text(templates.COURSE_ROLES_XML, encoding="utf-8")
        (d / "filters.xml").write_text(templates.COURSE_FILTERS_XML, encoding="utf-8")
        (d / "inforef.xml").write_text(templates.COURSE_INFOREF_XML, encoding="utf-8")
        (d / "completiondefaults.xml").write_text(templates.COURSE_COMPLETION_DEFAULTS_XML, encoding="utf-8")
        (d / "enrolments.xml").write_text(templates.COURSE_ENROLMENTS_XML.format(ts=ts), encoding="utf-8")

    def _write_section(self, tmp: Path, sec: dict, idx: int, ts: int) -> None:
        """Write sections/section_{id}/section.xml and inforef.xml."""
        d = tmp / "sections" / f"section_{sec['id']}"
        d.mkdir(parents=True, exist_ok=True)
        xml = templates.SECTION_XML.format(
            id=sec["id"],
            number=idx,
            name=esc(sec["name"]),
            sequence=",".join(str(m) for m in sec["modules"]),
            ts=ts,
        )
        (d / "section.xml").write_text(xml, encoding="utf-8")
        (d / "inforef.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<inforef/>', encoding="utf-8")

    #TODO: Too many conditionals can make it hard to enforce XML count parity, so think of a better way to handle different sub structures for the same XML tag
    # OpenEdx is very incosistent 
    def _write_page(self, tmp: Path, page: dict, ts: int) -> None:
        """Write activities/page_{id}/page.xml and inforef.xml."""
        d = tmp / "activities" / f"page_{page['id']}"
        d.mkdir(parents=True, exist_ok=True)
        xml = templates.PAGE_XML.format(id=page["id"], ctx=page["ctx"], name=esc(page["name"]), content=esc(page["content"]), ts=ts)
        (d / "page.xml").write_text(xml, encoding="utf-8")
        if page["file_ids"]:
            file_lines = "\n".join(f"    <file><id>{fid}</id></file>" for fid in page["file_ids"])
            inforef = f'<?xml version="1.0" encoding="UTF-8"?>\n<inforef>\n  <fileref>\n{file_lines}\n  </fileref>\n</inforef>'
        else:
            inforef = '<?xml version="1.0" encoding="UTF-8"?>\n<inforef/>'
        (d / "inforef.xml").write_text(inforef, encoding="utf-8")
        (d / "grades.xml").write_text(templates.ACTIVITY_GRADES_XML, encoding="utf-8")
        (d / "grade_history.xml").write_text(templates.ACTIVITY_GRADE_HISTORY_XML, encoding="utf-8")
        (d / "roles.xml").write_text(templates.ACTIVITY_ROLES_XML, encoding="utf-8")
        (d / "filters.xml").write_text(templates.ACTIVITY_FILTERS_XML, encoding="utf-8")
        module_xml = templates.MODULE_XML.format(
            id=page["id"], moodle_version=MOODLE_VERSION,
            sec_id=page["sec_id"], sec_num=page["sec_num"], ts=ts,
        )
        (d / "module.xml").write_text(module_xml, encoding="utf-8")

    def _write_files_xml(self, tmp: Path, file_entries: list, ts: int) -> None:
        """Write files.xml listing all static asset metadata."""
        entries = "\n".join(
            templates.FILE_ENTRY.format(id=f["id"], sha1=f["sha1"], name=esc(f["name"]), size=f["size"], mime=esc(f["mime"]), ctx=f["ctx"], ts=ts)
            for f in file_entries
        )
        (tmp / "files.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<files>\n{entries}\n</files>',
            encoding="utf-8"
        )

    def _copy_static(self, tmp: Path, file_entries: list) -> None:
        """Copy static assets into files/{sha1[:2]}/{sha1}."""
        files_dir = tmp / "files"
        for f in file_entries:
            dest = files_dir / f["sha1"][:2]
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f["path"], dest / f["sha1"])
