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
from ocw._version import __version__
from ocw.converter.html import (
    constrain_img_size,
    constrain_table_size,
    strip_blacklisted_classes,
    strip_templated_iframes,
    style_figcaption,
)
from ocw.converter.strategies import FlatSectionStrategy, NestedSectionStrategy
from ocw.parser_base import BaseParser
from ocw.utils import (
    _Counter,
    esc,
    normalise_license,
    rewrite_static_urls,
    sha1_of,
    warn_external_edx_urls,
)

load_dotenv()
MOODLE_VERSION = os.getenv("MOODLE_VERSION", "2024042212")
MOODLE_BACKUP_RELEASE = os.getenv("MOODLE_BACKUP_RELEASE", "5.1")
MOODLE_RELEASE = os.getenv("MOODLE_RELEASE", "5.1 (Build: 20251208)")


class MBZBuilder:
    """Converts a parsed Course into a Moodle MBZ backup archive."""

    def __init__(
        self, course: BaseParser, *, sequential_sections: bool = False, disable_custom_fields: bool = False
    ) -> None:
        self.course = course
        self.sequential_sections = sequential_sections
        self.disable_custom_fields = disable_custom_fields
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
        """Build the full MBZ directory tree in tmp."""
        ids = _Counter()
        ts = int(time.time())
        c = self.course

        overview = self._build_overview_section(c, ids)
        # at most one synthetic section now occupies the top slot: either
        # Overview (with Readings nested inside it), or standalone Readings
        # as the no-Overview fallback, or Overview alone
        section_offset = 1 if (overview is not None or c.readings) else 0

        strategy = (
            FlatSectionStrategy(c, ids, section_offset)
            if self.sequential_sections
            else NestedSectionStrategy(c, ids, section_offset)
        )
        all_sections, sub_mods, pages = strategy.build()
        strategy_section_count = len(all_sections)
        resources: list[dict] = []

        if overview is not None:
            overview_section, syllabus_page = overview
            all_sections.insert(0, overview_section)
            pages.insert(0, syllabus_page)

            if c.readings:
                subsection, readings_resources = self._build_readings_subsection(
                    c, ids, overview_section
                )
                child_sec = subsection["child_sec"]
                # nested child section must be numbered after every number the
                # strategy already used, to satisfy parent < child course-wide
                child_sec["number"] = section_offset + strategy_section_count
                for r in readings_resources:
                    r["sec_num"] = child_sec["number"]
                subsection["parent_sec_num"] = 0  # Overview is always number 0
                all_sections.append(child_sec)
                sub_mods.append(subsection)
                resources.extend(readings_resources)
        else:
            readings = self._build_readings_section(c, ids)
            if readings is not None:
                readings_section, readings_resources = readings
                readings_section["number"] = 0
                for r in readings_resources:
                    r["sec_num"] = 0
                all_sections.insert(0, readings_section)
                resources.extend(readings_resources)

        file_entries = self._build_file_entries(c, pages + resources, ids)
        self._write_all(
            tmp, c, all_sections, sub_mods, pages, resources, file_entries, ts, ids
        )

    def _build_overview_section(
        self, c: BaseParser, ids: _Counter
    ) -> tuple[dict, dict] | None:
        """Course-level "Overview" section holding the Syllabus page, prepended
        ahead of the chapter sections — or None if no static_tab Syllabus was
        configured in the OLX export."""
        if c.syllabus_html is None:
            return None
        warn_external_edx_urls(c.syllabus_html, context="Syllabus", static_files=c.static_files)
        content = style_figcaption(
            constrain_table_size(
                constrain_img_size(
                    strip_templated_iframes(
                        strip_blacklisted_classes(
                            rewrite_static_urls(c.syllabus_html, c.static_files)
                        )
                    )
                )
            )
        )
        sec_id, mod_id, ctx_id = ids.next(), ids.next(), ids.next()
        overview_section = {
            "id": sec_id,
            "name": "Overview",
            "number": 0,
            "modules": [mod_id],
        }
        syllabus_page = {
            "id": mod_id,
            "ctx": ctx_id,
            "sec_id": sec_id,
            "sec_num": 0,
            "name": c.syllabus_title,
            "content": content,
            "file_refs": re.findall(r'@@PLUGINFILE@@/([^"\'>\s]+)', content),
            "file_ids": [],
        }
        return overview_section, syllabus_page

    def _build_readings_section(
        self, c: BaseParser, ids: _Counter
    ) -> tuple[dict, list[dict]] | None:
        """Course-level "Readings" section holding one mod_resource per
        pdf_textbooks chapter, inserted right after Overview (or at the front
        if there's no Overview) — or None if c.readings is empty. Resources
        are returned separately from pages/sub_mods, not merged into either —
        _write_all/_activity_lines/_setting_lines all assume every "page" is
        literally a mod_page, so a resource needs its own list threaded the
        same way sub_mods already is."""
        if not c.readings:
            return None
        sec_id = ids.next()
        resources: list[dict] = []
        for reading in c.readings:
            mod_id, ctx_id = ids.next(), ids.next()
            resources.append(
                {
                    "id": mod_id,
                    "ctx": ctx_id,
                    "sec_id": sec_id,
                    "sec_num": 0,
                    "name": reading["title"],
                    "file_refs": [reading["name"]],
                    "file_ids": [],
                    "component": "mod_resource",
                }
            )
        readings_section = {
            "id": sec_id,
            "name": "Readings",
            "number": 0,
            "modules": [r["id"] for r in resources],
        }
        return readings_section, resources

    def _build_readings_subsection(
        self, c: BaseParser, ids: _Counter, overview_section: dict
    ) -> tuple[dict, list[dict]]:
        """Readings resources nested inside Overview as a mod_subsection — same
        sub_mods/child_sec shape NestedSectionStrategy uses for sequentials-
        under-chapters (strategies.py), reusing _write_subsection/
        _section_lines/_setting_lines unchanged since those already treat
        sub_mods generically. child_sec["number"]/resource["sec_num"] are left
        as 0 placeholders here — _populate finalizes them once strategy.build()
        is known, because Moodle requires every parent section number to sort
        below every child section number, course-wide
        (test_parent_sections_numbered_before_children).

        Caller owns the decision to invoke this at all — only called from
        _populate when c.readings is non-empty, so no guard here."""
        resources: list[dict] = []
        child_sec_id = ids.next()
        for reading in c.readings:
            mod_id, ctx_id = ids.next(), ids.next()
            resources.append(
                {
                    "id": mod_id,
                    "ctx": ctx_id,
                    "sec_id": child_sec_id,
                    "sec_num": 0,  # placeholder, set in _populate
                    "name": reading["title"],
                    "file_refs": [reading["name"]],
                    "file_ids": [],
                    "component": "mod_resource",
                }
            )
        sub_mod_id, sub_ctx_id, sub_int_id = ids.next(), ids.next(), ids.next()
        child_sec = {
            "id": child_sec_id,
            "name": "Readings",
            "modules": [r["id"] for r in resources],
            "itemid": sub_int_id,
            "parent_mod_id": sub_mod_id,
            "number": 0,  # placeholder, set in _populate
        }
        subsection = {
            "mod_id": sub_mod_id,
            "ctx": sub_ctx_id,
            "internal_id": sub_int_id,
            "name": "Readings",
            "parent_sec_id": overview_section["id"],
            "child_sec": child_sec,
        }
        overview_section["modules"].append(sub_mod_id)
        return subsection, resources

    def _build_file_entries(
        self, c: BaseParser, pages: list[dict], ids: _Counter
    ) -> list[dict]:
        """sha1 + mime metadata for files.xml — one entry per (page, filename) with correct ctx."""
        file_entries: list[dict] = []
        for page in pages:
            for name in page["file_refs"]:
                path = c.static_files.get(name)
                if path is None:
                    continue
                sha1 = sha1_of(path)
                mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
                fid = ids.next()
                file_entries.append(
                    {
                        "id": fid,
                        "sha1": sha1,
                        "name": name,
                        "size": path.stat().st_size,
                        "mime": mime,
                        "path": path,
                        "ctx": page["ctx"],
                        "component": page.get("component", "mod_page"),
                    }
                )
                page["file_ids"].append(fid)
        return file_entries

    def _write_all(
        self,
        tmp: Path,
        c: BaseParser,
        all_sections: list[dict],
        sub_mods: list[dict],
        pages: list[dict],
        resources: list[dict],
        file_entries: list[dict],
        ts: int,
        ids: _Counter,
    ) -> None:
        self._write_moodle_backup(tmp, c, all_sections, sub_mods, pages, resources, ts)
        self._write_static_manifests(tmp)
        self._write_course_xml(tmp, c, ts, ids)
        for idx, sec in enumerate(all_sections):
            self._write_section(tmp, sec, sec.get("number", idx + 1), ts)
        for sub in sub_mods:
            self._write_subsection(tmp, sub, ts)
        for page in pages:
            self._write_page(tmp, page, ts)
        for resource in resources:
            self._write_resource(tmp, resource, ts)
        self._write_files_xml(tmp, file_entries, ts)
        self._copy_static(tmp, file_entries)

    def _activity_lines(
        self,
        all_sections: list[dict],
        sub_mods: list[dict],
        pages: list[dict],
        resources: list[dict],
    ) -> list[str]:
        """
        Moodle rebuilds sequences based on moodle_backup section order. As such we need to reorder 
        sequences based on how we want it presented to the user.
        """ 
        child_sec_ids = {sub["child_sec"]["id"] for sub in sub_mods}
        subs_by_mod_id = {sub["mod_id"]: sub for sub in sub_mods}
        pages_by_id = {p["id"]: p for p in pages}
        resources_by_id = {r["id"]: r for r in resources}

        lines = []
        for sec in all_sections:
            for mod_id in sec["modules"]:
                if mod_id in subs_by_mod_id:
                    sub = subs_by_mod_id[mod_id]
                    lines.append(
                        f"      <activity><moduleid>{sub['mod_id']}</moduleid><sectionid>{sub['parent_sec_id']}</sectionid>"
                        f"<modulename>subsection</modulename><title>{esc(sub['name'])}</title>"
                        f"<directory>activities/subsection_{sub['mod_id']}</directory>"
                        f"<insubsection></insubsection></activity>"
                    )
                elif mod_id in pages_by_id:
                    p = pages_by_id[mod_id]
                    insub = "1" if p["sec_id"] in child_sec_ids else ""
                    lines.append(
                        f"      <activity><moduleid>{p['id']}</moduleid><sectionid>{p['sec_id']}</sectionid>"
                        f"<modulename>page</modulename><title>{esc(p['name'])}</title>"
                        f"<directory>activities/page_{p['id']}</directory>"
                        f"<insubsection>{insub}</insubsection></activity>"
                    )
                elif mod_id in resources_by_id:
                    r = resources_by_id[mod_id]
                    insub = "1" if r["sec_id"] in child_sec_ids else ""
                    lines.append(
                        f"      <activity><moduleid>{r['id']}</moduleid><sectionid>{r['sec_id']}</sectionid>"
                        f"<modulename>resource</modulename><title>{esc(r['name'])}</title>"
                        f"<directory>activities/resource_{r['id']}</directory>"
                        f"<insubsection>{insub}</insubsection></activity>"
                    )
        return lines

    def _section_lines(self, sections: list[dict], sub_mods: list[dict]) -> list[str]:
        child_sec_ids = {sub["child_sec"]["id"]: sub["mod_id"] for sub in sub_mods}
        return [
            f"      <section><sectionid>{s['id']}</sectionid><title>{esc(s['name'])}</title>"
            f"<directory>sections/section_{s['id']}</directory>"
            f"<parentcmid>{child_sec_ids.get(s['id'], '')}</parentcmid>"
            f"<modname>{'subsection' if s['id'] in child_sec_ids else ''}</modname></section>"
            for s in sections
        ]

    def _setting_lines(
        self,
        c: BaseParser,
        sections: list[dict],
        sub_mods: list[dict],
        pages: list[dict],
        resources: list[dict],
    ) -> list[str]:
        root_settings = [
            ("filename", esc(c.course_name)),
            ("imscc11", "0"),
            ("users", "0"),
            ("anonymize", "0"),
            ("role_assignments", "0"),
            ("activities", "1"),
            ("blocks", "1"),
            ("filters", "1"),
            ("comments", "0"),
            ("badges", "0"),
            ("calendarevents", "0"),
            ("userscompletion", "0"),
            ("logs", "0"),
            ("grade_histories", "0"),
            ("questionbank", "1"),
            ("groups", "1"),
            ("competencies", "0"),
            ("customfield", "1"),
        ]
        lines = [
            f"      <setting><level>root</level><name>{k}</name><value>{v}</value></setting>"
            for k, v in root_settings
        ]
        for sec in sections:
            sid = f"section_{sec['id']}"
            lines += [
                f"      <setting><level>section</level><section>{sid}</section><name>{sid}_included</name><value>1</value></setting>",
                f"      <setting><level>section</level><section>{sid}</section><name>{sid}_userinfo</name><value>0</value></setting>",
            ]
        for sub in sub_mods:
            aid = f"subsection_{sub['mod_id']}"
            lines += [
                f"      <setting><level>activity</level><activity>{aid}</activity><name>{aid}_included</name><value>1</value></setting>",
                f"      <setting><level>activity</level><activity>{aid}</activity><name>{aid}_userinfo</name><value>0</value></setting>",
            ]
        for page in pages:
            aid = f"page_{page['id']}"
            lines += [
                f"      <setting><level>activity</level><activity>{aid}</activity><name>{aid}_included</name><value>1</value></setting>",
                f"      <setting><level>activity</level><activity>{aid}</activity><name>{aid}_userinfo</name><value>0</value></setting>",
            ]
        for resource in resources:
            aid = f"resource_{resource['id']}"
            lines += [
                f"      <setting><level>activity</level><activity>{aid}</activity><name>{aid}_included</name><value>1</value></setting>",
                f"      <setting><level>activity</level><activity>{aid}</activity><name>{aid}_userinfo</name><value>0</value></setting>",
            ]
        return lines

    def _write_moodle_backup(
        self,
        tmp: Path,
        c: BaseParser,
        sections: list,
        sub_mods: list,
        pages: list,
        resources: list,
        ts: int,
    ) -> None:
        """Write moodle_backup.xml with activity and section manifests."""
        acts = "\n".join(self._activity_lines(sections, sub_mods, pages, resources))
        secs = "\n".join(self._section_lines(sections, sub_mods))
        settings = "\n".join(self._setting_lines(c, sections, sub_mods, pages, resources))
        xml = templates.MOODLE_BACKUP.format(
            course_name=esc(c.course_name),
            course_id=esc(c.course_id),
            moodle_version=MOODLE_VERSION,
            moodle_release=MOODLE_RELEASE,
            backup_release=MOODLE_BACKUP_RELEASE,
            ts=ts,
            acts=acts,
            secs=secs,
            settings=settings,
            ocw_version=__version__,
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

    def _build_vidrouter_block(self, c: BaseParser) -> str:
        """Fields match restore_local_vidrouter_plugin.class.php's
        process_plugin_local_vidrouter_video() exactly — no courseid, no html.
        Data row, not an HTML5 tag; filter_vidrouter renders at request time.

        Emitted as a 'local' plugin block (not 'filter') because Moodle's course-level
        restore only scans format/theme/report/coursereport/plagiarism/local/tool plugin
        types (restore_course_structure_step::define_structure()) — filter_ is never
        scanned, so local_vidrouter owns the course-level restore hook. See
        RESTORE_HOOK_FINDINGS.md.

        Fields are child elements, not XML attributes: Moodle's SAX restore parser
        only checks in at a path when it descends into a child, so an attribute-only
        <video/> leaf never gets its own dispatch chunk, and repeated attribute-only
        siblings get deduped down to one survivor before that. See findings.md #16.
        """
        if not c.videos:
            return ""
        videos_xml = "\n".join(
            "    <video>\n"
            "      <vidkey>{}</vidkey>\n"
            "      <title>{}</title>\n"
            "      <youtubeid>{}</youtubeid>\n"
            "      <edxvideoid>{}</edxvideoid>\n"
            "      <tuddownloadid>{}</tuddownloadid>\n"
            "      <collegeramaid>{}</collegeramaid>\n"
            "      <stlbaseid>{}</stlbaseid>\n"
            "      <urlname>{}</urlname>\n"
            "      <videopagepath>{}</videopagepath>\n"
            "    </video>".format(
                esc(v["vidkey"]),
                esc(v["display_name"]),
                esc(v["youtubeid"] or ""),
                esc(v["edxvideoid"] or ""),
                esc(v["tuddownloadid"] or ""),
                esc(v["collegeramaid"] or ""),
                esc(v["stlbaseid"] or ""),
                esc(v["urlname"]),
                esc(v["videopagepath"]),
            )
            for v in c.videos
        )
        return f"  <plugin_local_vidrouter_course>\n{videos_xml}\n  </plugin_local_vidrouter_course>\n"

    def _build_customfields_block(self, c: BaseParser, ids: _Counter) -> str:
        """Emits <customfield> elements for the 4 auto-fillable Wikiwijs fields
        (Uitgever/Taal/Toegang/Gebruiksrecht). Matched on restore by shortname+type
        (core_course\\customfield\\course_handler::restore_instance_data_from_backup) —
        a target site missing the one-off registration script (PLAN.md §5) just
        silently drops non-matching blocks, no error. type is 'text' for all four,
        not 'select' — see PLAN.md §9.2 for why (select's backed-up value is an
        option-list index, not the string we'd be writing here).
        """
        if self.disable_custom_fields:
            return ""
        fields = [
            ("publisher", c.org),
            ("language", c.language),
            ("access", "open access"),
            ("license", normalise_license(c.license)),
        ]
        lines = [
            (
                '    <customfield id="{}">\n'
                "      <shortname>{}</shortname>\n"
                "      <type>text</type>\n"
                "      <value>{}</value>\n"
                "      <valueformat>0</valueformat>\n"
                "      <valuetrust>1</valuetrust>\n"
                "    </customfield>"
            ).format(ids.next(), esc(shortname), esc(value))
            for shortname, value in fields
            if value
        ]
        return "\n".join(lines) + ("\n" if lines else "")

    def _write_course_xml(self, tmp: Path, c: BaseParser, ts: int, ids: _Counter) -> None:
        d = tmp / "course"
        d.mkdir(exist_ok=True)
        (d / "course.xml").write_text(
            templates.COURSE_XML.format(
                course_id=esc(c.course_id),
                course_name=esc(c.course_name),
                summary=esc(c.summary_html or ""),
                customfields_block=self._build_customfields_block(c, ids),
                ts=ts,
                plugin_vidrouter_block=self._build_vidrouter_block(c),
            ),
            encoding="utf-8",
        )
        (d / "roles.xml").write_text(templates.COURSE_ROLES_XML, encoding="utf-8")
        (d / "filters.xml").write_text(templates.COURSE_FILTERS_XML, encoding="utf-8")
        (d / "inforef.xml").write_text(templates.COURSE_INFOREF_XML, encoding="utf-8")
        (d / "completiondefaults.xml").write_text(
            templates.COURSE_COMPLETION_DEFAULTS_XML, encoding="utf-8"
        )
        (d / "enrolments.xml").write_text(
            templates.COURSE_ENROLMENTS_XML.format(ts=ts), encoding="utf-8"
        )

    def _write_section(self, tmp: Path, sec: dict, idx: int, ts: int) -> None:
        """Write sections/section_{id}/section.xml and inforef.xml."""
        d = tmp / "sections" / f"section_{sec['id']}"
        d.mkdir(parents=True, exist_ok=True)
        tmpl = templates.CHILD_SECTION_XML if "itemid" in sec else templates.SECTION_XML
        xml = tmpl.format(
            id=sec["id"],
            number=idx,
            name=esc(sec["name"]),
            summary=esc(sec.get("summary", "")),
            sequence=",".join(str(m) for m in sec["modules"]),
            itemid=sec.get("itemid", ""),
            ts=ts,
        )
        (d / "section.xml").write_text(xml, encoding="utf-8")
        (d / "inforef.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<inforef/>', encoding="utf-8"
        )

    # TODO: Too many conditionals can make it hard to enforce XML count parity, so think of a better way to handle different sub structures for the same XML tag
    # OpenEdx is very incosistent
    def _write_page(self, tmp: Path, page: dict, ts: int) -> None:
        """Write activities/page_{id}/page.xml and inforef.xml."""
        d = tmp / "activities" / f"page_{page['id']}"
        d.mkdir(parents=True, exist_ok=True)
        xml = templates.PAGE_XML.format(
            id=page["id"],
            ctx=page["ctx"],
            name=esc(page["name"]),
            content=esc(page["content"]),
            ts=ts,
        )
        (d / "page.xml").write_text(xml, encoding="utf-8")
        if page["file_ids"]:
            file_lines = "\n".join(
                f"    <file><id>{fid}</id></file>" for fid in page["file_ids"]
            )
            inforef = f'<?xml version="1.0" encoding="UTF-8"?>\n<inforef>\n  <fileref>\n{file_lines}\n  </fileref>\n</inforef>'
        else:
            inforef = '<?xml version="1.0" encoding="UTF-8"?>\n<inforef/>'
        (d / "inforef.xml").write_text(inforef, encoding="utf-8")
        (d / "grades.xml").write_text(templates.ACTIVITY_GRADES_XML, encoding="utf-8")
        (d / "grade_history.xml").write_text(
            templates.ACTIVITY_GRADE_HISTORY_XML, encoding="utf-8"
        )
        (d / "roles.xml").write_text(templates.ACTIVITY_ROLES_XML, encoding="utf-8")
        (d / "filters.xml").write_text(templates.ACTIVITY_FILTERS_XML, encoding="utf-8")
        module_xml = templates.MODULE_XML.format(
            id=page["id"],
            moodle_version=MOODLE_VERSION,
            sec_id=page["sec_id"],
            sec_num=page["sec_num"],
            ts=ts,
        )
        (d / "module.xml").write_text(module_xml, encoding="utf-8")

    def _write_resource(self, tmp: Path, resource: dict, ts: int) -> None:
        """Write activities/resource_{id}/resource.xml and inforef.xml."""
        d = tmp / "activities" / f"resource_{resource['id']}"
        d.mkdir(parents=True, exist_ok=True)
        xml = templates.RESOURCE_XML.format(
            id=resource["id"],
            ctx=resource["ctx"],
            name=esc(resource["name"]),
            ts=ts,
        )
        (d / "resource.xml").write_text(xml, encoding="utf-8")
        if resource["file_ids"]:
            file_lines = "\n".join(
                f"    <file><id>{fid}</id></file>" for fid in resource["file_ids"]
            )
            inforef = f'<?xml version="1.0" encoding="UTF-8"?>\n<inforef>\n  <fileref>\n{file_lines}\n  </fileref>\n</inforef>'
        else:
            inforef = '<?xml version="1.0" encoding="UTF-8"?>\n<inforef/>'
        (d / "inforef.xml").write_text(inforef, encoding="utf-8")
        (d / "grades.xml").write_text(templates.ACTIVITY_GRADES_XML, encoding="utf-8")
        (d / "grade_history.xml").write_text(
            templates.ACTIVITY_GRADE_HISTORY_XML, encoding="utf-8"
        )
        (d / "roles.xml").write_text(templates.ACTIVITY_ROLES_XML, encoding="utf-8")
        (d / "filters.xml").write_text(templates.ACTIVITY_FILTERS_XML, encoding="utf-8")
        module_xml = templates.RESOURCE_MODULE_XML.format(
            id=resource["id"],
            moodle_version=MOODLE_VERSION,
            sec_id=resource["sec_id"],
            sec_num=resource["sec_num"],
            ts=ts,
        )
        (d / "module.xml").write_text(module_xml, encoding="utf-8")

    def _write_subsection(self, tmp: Path, sub: dict, ts: int) -> None:
        """Write activities/subsection_{mod_id}/ files."""
        d = tmp / "activities" / f"subsection_{sub['mod_id']}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "subsection.xml").write_text(
            templates.SUBSECTION_XML.format(
                internal_id=sub["internal_id"],
                mod_id=sub["mod_id"],
                ctx=sub["ctx"],
                name=esc(sub["name"]),
                ts=ts,
            ),
            encoding="utf-8",
        )
        (d / "module.xml").write_text(
            templates.SUBSECTION_MODULE_XML.format(
                mod_id=sub["mod_id"],
                moodle_version=MOODLE_VERSION,
                sec_id=sub["parent_sec_id"],
                sec_num=sub["parent_sec_num"],
                ts=ts,
            ),
            encoding="utf-8",
        )
        (d / "inforef.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<inforef/>', encoding="utf-8"
        )
        (d / "grades.xml").write_text(templates.ACTIVITY_GRADES_XML, encoding="utf-8")
        (d / "grade_history.xml").write_text(
            templates.ACTIVITY_GRADE_HISTORY_XML, encoding="utf-8"
        )
        (d / "roles.xml").write_text(templates.ACTIVITY_ROLES_XML, encoding="utf-8")
        (d / "filters.xml").write_text(
            templates.SUBSECTION_FILTERS_XML, encoding="utf-8"
        )
        (d / "calendar.xml").write_text(
            templates.SUBSECTION_CALENDAR_XML, encoding="utf-8"
        )
        (d / "competencies.xml").write_text(
            templates.SUBSECTION_COMPETENCIES_XML, encoding="utf-8"
        )

    def _write_files_xml(self, tmp: Path, file_entries: list, ts: int) -> None:
        """Write files.xml listing all static asset metadata."""
        entries = "\n".join(
            templates.FILE_ENTRY.format(
                id=f["id"],
                sha1=f["sha1"],
                name=esc(f["name"]),
                size=f["size"],
                mime=esc(f["mime"]),
                ctx=f["ctx"],
                component=f["component"],
                ts=ts,
            )
            for f in file_entries
        )
        (tmp / "files.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<files>\n{entries}\n</files>',
            encoding="utf-8",
        )

    def _copy_static(self, tmp: Path, file_entries: list) -> None:
        """Copy static assets into files/{sha1[:2]}/{sha1}."""
        files_dir = tmp / "files"
        for f in file_entries:
            dest = files_dir / f["sha1"][:2]
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f["path"], dest / f["sha1"])
