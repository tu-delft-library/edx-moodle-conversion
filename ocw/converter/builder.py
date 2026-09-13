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
from ocw.converter.strategies import (
    FlatSectionStrategy,
    NestedSectionStrategy,
    SectionStrategy,
)
from ocw.parser.base import BaseParser
from ocw.utils import (
    _Counter,
    esc,
    html_to_plain_text,
    rewrite_static_urls,
    sha1_of,
    warn_external_edx_urls,
)

load_dotenv()
MOODLE_VERSION = os.getenv("MOODLE_VERSION", "2024042212")
MOODLE_BACKUP_RELEASE = os.getenv("MOODLE_BACKUP_RELEASE", "5.1")
MOODLE_RELEASE = os.getenv("MOODLE_RELEASE", "5.1 (Build: 20251208)")


class MBZBuilder:
    """Build a self-contained Moodle MBZ backup from a parsed course.

    Each build creates its own monotonically increasing `_Counter`. Every generated Moodle
    record identifier must be allocated from that one counter, in the order records are written.
    This keeps IDs unique and preserves the cross-file references that Moodle restores.

    Args:
        course: Source-normalised course data to export.
        sequential_sections: Create one Moodle section per source sequential instead of nested
            subsections.
        disable_custom_fields: Omit Edusources custom-field data from `course.xml`.
    """

    def __init__(
        self,
        course: BaseParser,
        *,
        sequential_sections: bool = False,
        disable_custom_fields: bool = False,
    ) -> None:
        self.course = course
        self.sequential_sections = sequential_sections
        self.disable_custom_fields = disable_custom_fields
        self.log = logging.getLogger("ocw.converter")

    def build(self, out: Path) -> None:
        """Create a temporary Moodle backup tree, package it as an MBZ archive, and remove it.

        The temporary tree is removed even if the build fails.
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            self._populate(tmp)
            with tarfile.open(out, "w:gz") as tar:
                for item in sorted(tmp.rglob("*")):
                    tar.add(item, arcname=str(item.relative_to(tmp)), recursive=False)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _populate(self, tmp: Path) -> None:
        """Materialise the complete MBZ tree in `tmp`."""
        ids = _Counter()
        ts = int(time.time())
        c = self.course
        section_offset = 1
        # Must be distinct from every other id allocated below, and in particular from 1 -- every
        # Moodle site's own system context is permanently id 1, and restore pre-maps backup
        # context id 1 straight to it. Reusing 1 here silently redirects course-context files
        # (course image, overviewfiles) into the site's system context instead of the course.
        course_ctx = ids.next()

        strategy = (
            FlatSectionStrategy(c, ids, section_offset)
            if self.sequential_sections
            else NestedSectionStrategy(c, ids, section_offset)
        )

        overview_section, all_sections, dedup_section, readings_child_sec = (
            self._alloc_sections(c, ids, strategy, section_offset)
        )
        sub_mods, readings_subsection = self._alloc_subsections(
            ids, strategy, overview_section, readings_child_sec
        )

        # Phase 3: every page/resource ID.
        resources: list[dict] = []
        readings_pages: list[dict] = []
        if c.readings:
            resources = self._build_readings_resources(c, ids, readings_child_sec)
            readings_child_sec["modules"] = [r["id"] for r in resources]
        elif c.reading_pages:
            readings_pages = self._build_wp_readings_pages(c, strategy, readings_child_sec)
            readings_child_sec["modules"] = [p["id"] for p in readings_pages]
            if not readings_pages:
                all_sections.remove(readings_child_sec)
                sub_mods.remove(readings_subsection)

        dedup_pages: list[dict] = []
        if dedup_section is not None:
            dedup_pages = [
                page
                for vert in c.dedup_pages
                if (
                    page := strategy._build_page(
                        vert, dedup_section["id"], dedup_section["number"]
                    )
                )
                is not None
            ]
            dedup_section["modules"] = [p["id"] for p in dedup_pages]
            if not dedup_pages:
                all_sections.remove(dedup_section)

        syllabus_page = self._build_syllabus_page(c, ids, overview_section)
        strategy_pages = strategy.build_pages()
        pages = dedup_pages + readings_pages + strategy_pages
        if syllabus_page is not None:
            pages.insert(0, syllabus_page)

        file_entries = self._build_file_entries(c, pages + resources, ids)
        file_entries += self._build_course_image_entries(c, ids, course_ctx)
        self._write_all(
            tmp, c, all_sections, sub_mods, pages, resources, file_entries, ts, ids, course_ctx
        )

    def _alloc_sections(
        self, c: BaseParser, ids: _Counter, strategy: SectionStrategy, section_offset: int
    ) -> tuple[dict, list[dict], dict | None, dict | None]:
        """Phase 1: allocate every section ID in the course, including Overview/Readings/Hidden
        which aren't part of `strategy`. See `_populate`'s docstring for the numbering rules."""
        overview_section = {"id": ids.next(), "name": "Overview", "number": 0, "modules": []}
        if c.overview_summary_html:
            overview_section["summary"] = strategy._process_html(
                c.overview_summary_html, context="Overview"
            )
        all_sections = strategy.build_sections()
        all_sections.insert(0, overview_section)

        # Hidden is a plain top-level section (no component), so it's a "regular" section whose
        # declared number Moodle actually honours -- keep it right after the strategy's regular
        # sections, with no gap.
        dedup_section = None
        if c.dedup_pages:
            dedup_section = {
                "id": ids.next(),
                "name": "Hidden",
                "modules": [],
                "visible": 0,
                "number": section_offset + strategy.regular_section_count,
            }
            all_sections.append(dedup_section)

        # Readings is always subsection-linked (see `_populate`'s docstring), so its declared
        # number is never honoured either -- it belongs in the same "past every regular section"
        # range as the strategy's own child sections, not right after them like Hidden.
        readings_child_sec = None
        if c.readings or c.reading_pages:
            readings_child_sec = {"id": ids.next(), "name": "Readings", "modules": []}
            all_sections.append(readings_child_sec)

        tail_start = (
            section_offset
            + strategy.regular_section_count
            + (1 if dedup_section is not None else 0)
        )
        strategy.relocate_child_sections(tail_start)
        if readings_child_sec is not None:
            readings_child_sec["number"] = tail_start + strategy.child_section_count

        return overview_section, all_sections, dedup_section, readings_child_sec

    def _alloc_subsections(
        self,
        ids: _Counter,
        strategy: SectionStrategy,
        overview_section: dict,
        readings_child_sec: dict | None,
    ) -> tuple[list[dict], dict | None]:
        """Phase 2: allocate every subsection-activity ID, now that every section ID exists."""
        sub_mods = strategy.build_subsections()
        readings_subsection = None
        if readings_child_sec is not None:
            sub_mod_id, sub_ctx_id, sub_int_id = ids.next(), ids.next(), ids.next()
            readings_child_sec["itemid"] = sub_int_id
            readings_child_sec["parent_mod_id"] = sub_mod_id
            readings_subsection = {
                "mod_id": sub_mod_id,
                "ctx": sub_ctx_id,
                "internal_id": sub_int_id,
                "name": "Readings",
                "parent_sec_id": overview_section["id"],
                "parent_sec_num": 0,
                "child_sec": readings_child_sec,
            }
            overview_section["modules"].append(sub_mod_id)
            sub_mods.append(readings_subsection)
        return sub_mods, readings_subsection

    def _build_syllabus_page(
        self, c: BaseParser, ids: _Counter, overview_section: dict
    ) -> dict | None:
        """Build the Syllabus page inside `overview_section`, when the course has one."""
        if c.syllabus_html is None:
            return None

        warn_external_edx_urls(
            c.syllabus_html, context="Syllabus", static_files=c.static_files
        )
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
        mod_id, ctx_id = ids.next(), ids.next()
        overview_section["modules"].append(mod_id)
        return {
            "id": mod_id,
            "ctx": ctx_id,
            "sec_id": overview_section["id"],
            "sec_num": 0,
            "name": c.syllabus_title,
            "content": content,
            "file_refs": re.findall(r'@@PLUGINFILE@@/([^"\'>\s]+)', content),
            "file_ids": [],
        }

    def _build_readings_resources(
        self, c: BaseParser, ids: _Counter, child_sec: dict
    ) -> list[dict]:
        """Build one resource activity per OLX reading, inside the already-built `child_sec`."""
        resources: list[dict] = []
        for reading in c.readings:
            mod_id, ctx_id = ids.next(), ids.next()
            resources.append(
                {
                    "id": mod_id,
                    "ctx": ctx_id,
                    "sec_id": child_sec["id"],
                    "sec_num": child_sec["number"],
                    "name": reading["title"],
                    "file_refs": [reading["name"]],
                    "file_ids": [],
                    "component": "mod_resource",
                }
            )
        return resources

    def _build_wp_readings_pages(
        self, c: BaseParser, strategy: SectionStrategy, child_sec: dict
    ) -> list[dict]:
        """Build one real page per WP reading, inside the already-built `child_sec`."""
        return [
            page
            for vert in c.reading_pages
            if (page := strategy._build_page(vert, child_sec["id"], child_sec["number"]))
            is not None
        ]

    def _build_file_entries(
        self, c: BaseParser, pages: list[dict], ids: _Counter
    ) -> list[dict]:
        """Build MBZ file records for locally resolved files referenced by pages or resources."""
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
                        "filearea": "content",
                        "itemid": 0,
                        "sortorder": 0,
                    }
                )
                page["file_ids"].append(fid)
        return file_entries

    def _build_course_image_entries(
        self, c: BaseParser, ids: _Counter, course_ctx: int
    ) -> list[dict]:
        """Build course-context `overviewfiles` file records for the course image and banner.

        Thumbnail first (sortorder 0) so it's the one Moodle picks for the catalogue tile; the
        banner rides along at sortorder 1, embedded but not wired to any rendering path yet.
        Deduplicated by path -- WP has only one image and registers it as both, and two entries
        for the same file would collide on Moodle's per-area filename uniqueness.
        """
        entries: list[dict] = []
        paths = dict.fromkeys(
            p for p in (c.course_image_path, c.banner_image_path) if p is not None
        )
        for sortorder, path in enumerate(paths):
            entries.append(
                {
                    "id": ids.next(),
                    "sha1": sha1_of(path),
                    "name": path.name,
                    "size": path.stat().st_size,
                    "mime": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                    "path": path,
                    "ctx": course_ctx,
                    "component": "course",
                    "filearea": "overviewfiles",
                    "itemid": 0,
                    "sortorder": sortorder,
                }
            )
        return entries

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
        course_ctx: int,
    ) -> None:
        """Write every XML manifest, activity directory, and referenced file into `tmp`."""
        self._write_moodle_backup(
            tmp, c, all_sections, sub_mods, pages, resources, ts, course_ctx
        )
        self._write_static_manifests(tmp)
        course_file_ids = [f["id"] for f in file_entries if f["component"] == "course"]
        self._write_course_xml(tmp, c, ts, ids, course_file_ids, course_ctx)
        for idx, sec in enumerate(all_sections):
            self._write_section(tmp, sec, sec.get("number", idx + 1), ts)
        for sub in sub_mods:
            self._write_subsection(tmp, sub, ts)
        for page in pages:
            if page.get("kind") == "url":
                self._write_url(tmp, page, ts)
            else:
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
        """Serialise activity manifest entries in each section's declared module order."""
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
                    modulename = "url" if p.get("kind") == "url" else "page"
                    lines.append(
                        f"      <activity><moduleid>{p['id']}</moduleid><sectionid>{p['sec_id']}</sectionid>"
                        f"<modulename>{modulename}</modulename><title>{esc(p['name'])}</title>"
                        f"<directory>activities/{modulename}_{p['id']}</directory>"
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
        """Serialise the section manifest, including parent links for child sections."""
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
        """Generate backup settings for the course, its sections, and its activities."""
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
            modulename = "url" if page.get("kind") == "url" else "page"
            aid = f"{modulename}_{page['id']}"
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
        course_ctx: int,
    ) -> None:
        """Write the root `moodle_backup.xml` manifest."""
        acts = "\n".join(self._activity_lines(sections, sub_mods, pages, resources))
        secs = "\n".join(self._section_lines(sections, sub_mods))
        settings = "\n".join(
            self._setting_lines(c, sections, sub_mods, pages, resources)
        )
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
            course_ctx=course_ctx,
        )
        (tmp / "moodle_backup.xml").write_text(xml, encoding="utf-8")

    def _write_static_manifests(self, tmp: Path) -> None:
        """Write the required empty root-level manifests for unsupported Moodle subsystems."""
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
        """Build the course-level video-routing XML block for parsed video components."""
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
            "      <srtbaseid>{}</srtbaseid>\n"
            "      <urlname>{}</urlname>\n"
            "      <videopagepath>{}</videopagepath>\n"
            "    </video>".format(
                esc(v["vidkey"]),
                esc(v["display_name"]),
                esc(v["youtubeid"] or ""),
                esc(v["edxvideoid"] or ""),
                esc(v["tuddownloadid"] or ""),
                esc(v["collegeramaid"] or ""),
                esc(v["srtbaseid"] or ""),
                esc(v["urlname"]),
                esc(v["videopagepath"]),
            )
            for v in c.videos
        )
        return f"  <plugin_local_vidrouter_course>\n{videos_xml}\n  </plugin_local_vidrouter_course>\n"

    def _build_customfields_block(self, c: BaseParser, ids: _Counter) -> str:
        """Build course custom-field XML records from source metadata."""

        if self.disable_custom_fields:
            return ""
        fields = [
            ("publisher", c.org),
            ("language", c.language),
            ("access", "open access"),
            ("license", c.license),
            (
                "summary",
                html_to_plain_text(c.overview_summary_html)
                if c.overview_summary_html
                else "",
            ),
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

    def _write_course_xml(
        self,
        tmp: Path,
        c: BaseParser,
        ts: int,
        ids: _Counter,
        course_file_ids: list[int],
        course_ctx: int,
    ) -> None:
        """Write the course record and its course-level extension data.

        `course_file_ids` (course image/banner) must be declared here as `<fileref>` entries --
        restore only loads a course-context file into `backup_files_temp` when its id appears in
        the owning task's `inforef.xml`, an empty `<inforef/>` (the old default) means the file
        is present in `files.xml` but never actually gets restored.
        """
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
                course_ctx=course_ctx,
            ),
            encoding="utf-8",
        )
        (d / "roles.xml").write_text(templates.COURSE_ROLES_XML, encoding="utf-8")
        (d / "filters.xml").write_text(templates.COURSE_FILTERS_XML, encoding="utf-8")
        if course_file_ids:
            file_lines = "\n".join(
                f"    <file><id>{fid}</id></file>" for fid in course_file_ids
            )
            inforef = f'<?xml version="1.0" encoding="UTF-8"?>\n<inforef>\n  <fileref>\n{file_lines}\n  </fileref>\n</inforef>'
        else:
            inforef = templates.COURSE_INFOREF_XML
        (d / "inforef.xml").write_text(inforef, encoding="utf-8")
        (d / "completiondefaults.xml").write_text(
            templates.COURSE_COMPLETION_DEFAULTS_XML, encoding="utf-8"
        )
        (d / "enrolments.xml").write_text(
            templates.COURSE_ENROLMENTS_XML.format(ts=ts), encoding="utf-8"
        )

    def _write_section(self, tmp: Path, sec: dict, idx: int, ts: int) -> None:
        """Write one section record and its empty information-reference manifest."""
        d = tmp / "sections" / f"section_{sec['id']}"
        d.mkdir(parents=True, exist_ok=True)
        if "itemid" in sec:
            tmpl = templates.CHILD_SECTION_XML
        elif sec.get("visible") == 0:
            tmpl = templates.HIDDEN_SECTION_XML
        else:
            tmpl = templates.SECTION_XML
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

    def _write_page(self, tmp: Path, page: dict, ts: int) -> None:
        """Write a page activity and its required supporting manifests."""
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

    def _write_url(self, tmp: Path, url_page: dict, ts: int) -> None:
        """Write a URL activity that redirects to `url_page["externalurl"]` and its supporting manifests."""
        d = tmp / "activities" / f"url_{url_page['id']}"
        d.mkdir(parents=True, exist_ok=True)
        xml = templates.URL_XML.format(
            id=url_page["id"],
            ctx=url_page["ctx"],
            name=esc(url_page["name"]),
            externalurl=url_page["externalurl"],
            ts=ts,
        )
        (d / "url.xml").write_text(xml, encoding="utf-8")
        (d / "inforef.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<inforef/>', encoding="utf-8"
        )
        (d / "grades.xml").write_text(templates.ACTIVITY_GRADES_XML, encoding="utf-8")
        (d / "grade_history.xml").write_text(
            templates.ACTIVITY_GRADE_HISTORY_XML, encoding="utf-8"
        )
        (d / "roles.xml").write_text(templates.ACTIVITY_ROLES_XML, encoding="utf-8")
        (d / "filters.xml").write_text(templates.ACTIVITY_FILTERS_XML, encoding="utf-8")
        module_xml = templates.URL_MODULE_XML.format(
            id=url_page["id"],
            moodle_version=MOODLE_VERSION,
            sec_id=url_page["sec_id"],
            sec_num=url_page["sec_num"],
            ts=ts,
        )
        (d / "module.xml").write_text(module_xml, encoding="utf-8")

    def _write_resource(self, tmp: Path, resource: dict, ts: int) -> None:
        """Write a resource activity and its required supporting manifests."""
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
        """Write the subsection activity that links a parent section to a child section."""
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
        """Write the archive-wide catalogue for every embedded file."""
        entries = "\n".join(
            templates.FILE_ENTRY.format(
                id=f["id"],
                sha1=f["sha1"],
                name=esc(f["name"]),
                size=f["size"],
                mime=esc(f["mime"]),
                ctx=f["ctx"],
                component=f["component"],
                filearea=f["filearea"],
                itemid=f["itemid"],
                sortorder=f["sortorder"],
                ts=ts,
            )
            for f in file_entries
        )
        (tmp / "files.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n<files>\n{entries}\n</files>',
            encoding="utf-8",
        )

    def _copy_static(self, tmp: Path, file_entries: list) -> None:
        """Copy embedded file payloads into Moodle's SHA-1-addressed file store.

        Each payload path and SHA-1 comes from the same `file_entries` record used in `files.xml`.
        """
        files_dir = tmp / "files"
        for f in file_entries:
            dest = files_dir / f["sha1"][:2]
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f["path"], dest / f["sha1"])
