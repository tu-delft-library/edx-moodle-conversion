import logging
import re
from abc import ABC, abstractmethod

from ocw.converter.html import (
    constrain_img_size,
    constrain_table_size,
    mark_hyperlinks_nomediaplugin,
    strip_blacklisted_classes,
    strip_templated_iframes,
    style_figcaption,
)
from ocw.parser_base import BaseParser
from ocw.utils import _Counter, rewrite_static_urls, warn_external_edx_urls

log = logging.getLogger("ocw.converter")


class SectionStrategy(ABC):
    """Convert a parsed course hierarchy into ordered Moodle sections, subsections, and pages.

    Subclasses choose either a flat or nested Moodle topology. `section_offset` reserves section
    numbers for course-level content that is created before the source chapters. Every generated
    record ID is allocated through the shared `ids` counter.
    """

    def __init__(
        self, course: BaseParser, ids: _Counter, section_offset: int = 0
    ) -> None:
        self.c = course
        self.ids = ids
        self.section_offset = section_offset

    @abstractmethod
    def build(self) -> tuple[list[dict], list[dict], list[dict]]:
        """Return ordered section, subsection-activity, and page records for MBZ serialisation.

        The section order is the restore order used to reconstruct the Moodle course structure.
        """

    def _process_html(self, content: str, context: str = "") -> str:
        """Apply the standard source-to-Moodle HTML transformation pipeline.

        All page and summary HTML passes through this method so asset rewriting, external-host
        warnings, unsupported embeds, and presentation fixes are handled consistently.
        """
        warn_external_edx_urls(
            content, context=context, static_files=self.c.static_files
        )
        return style_figcaption(
            constrain_table_size(
                constrain_img_size(
                    mark_hyperlinks_nomediaplugin(
                        strip_templated_iframes(
                            strip_blacklisted_classes(
                                rewrite_static_urls(content, self.c.static_files)
                            )
                        )
                    )
                )
            )
        )

    def _build_page(self, vert: dict, sec_id: int, sec_num: int) -> dict | None:
        """Convert one source vertical into a Moodle page record.

        HTML components are transformed and video components become routing tokens. Allocates the
        page module and context IDs when the vertical contains supported content, otherwise
        returns `None`.
        """
        parts = []
        for comp in vert["components"]:
            if comp["type"] == "html":
                processed = self._process_html(
                    comp["content"], context=vert.get("display_name", "")
                )
                parts.append(processed + '<div style="clear:both"></div>')
            elif comp["type"] == "video":
                parts.append(f"<p>[[vid:{comp['vidkey']}]]</p>")
            else:
                log.debug(
                    "Dropping component type '%s' in vertical '%s'",
                    comp["type"],
                    vert.get("display_name", ""),
                )
        if not parts:
            return None
        mod_id, ctx_id = self.ids.next(), self.ids.next()
        combined = "".join(parts)
        file_refs = re.findall(r'@@PLUGINFILE@@/([^"\'>\s]+)', combined)
        return {
            "id": mod_id,
            "ctx": ctx_id,
            "sec_id": sec_id,
            "sec_num": sec_num,
            "name": vert["display_name"],
            "content": combined,
            "file_refs": file_refs,
            "file_ids": [],
        }


class FlatSectionStrategy(SectionStrategy):
    """Represent each source sequential as a top-level Moodle section.

    This topology does not create Moodle subsection activities.
    """

    def build(self) -> tuple[list[dict], list[dict], list[dict]]:
        """Build one top-level section per source sequential.

        Sections are created before pages so every page can reference its final section ID and
        number.
        """
        sections: list[dict] = []
        sec_idx_for: dict[int, int] = {}
        for ch in self.c.chapters:
            for i, seq in enumerate(ch["sequentials"]):
                sec_idx_for[id(seq)] = len(sections)
                sec = {
                    "id": self.ids.next(),
                    "name": f"{ch['display_name']} - {seq['display_name']}",
                    "modules": [],
                    # Set an explicit, offset-aware number instead of `_write_section()`'s
                    # `idx + 1` fallback.
                    "number": len(sections) + 1 + self.section_offset,
                }
                if i == 0 and ch.get("summary_html"):
                    sec["summary"] = self._process_html(
                        ch["summary_html"], context=ch["display_name"]
                    )
                sections.append(sec)

        pages: list[dict] = []
        for ch in self.c.chapters:
            for seq in ch["sequentials"]:
                sec_idx = sec_idx_for[id(seq)]
                sec = sections[sec_idx]
                for vert in seq["verticals"]:
                    page = self._build_page(
                        vert, sec["id"], sec_idx + 1 + self.section_offset
                    )
                    if page is None:
                        continue
                    pages.append(page)
                    sec["modules"].append(page["id"])

        return sections, [], pages


class NestedSectionStrategy(SectionStrategy):
    """Represent source chapters as Moodle sections and sequentials as child subsections."""

    def build(self) -> tuple[list[dict], list[dict], list[dict]]:
        """Build the nested section hierarchy and its pages.

        Parent sections, subsection activities, and child sections are created before pages so
        every relationship and section number is available when page records are built.
        """
        sub_mods: list[dict] = []
        ch_sections: list[dict] = []
        for ch in self.c.chapters:
            ch_sec = {"id": self.ids.next(), "name": ch["display_name"], "modules": []}
            if ch.get("summary_html"):
                ch_sec["summary"] = self._process_html(
                    ch["summary_html"], context=ch["display_name"]
                )
            ch_sections.append(ch_sec)
            for seq in ch["sequentials"]:
                sub_mod_id, sub_ctx_id, sub_int_id = (
                    self.ids.next(),
                    self.ids.next(),
                    self.ids.next(),
                )
                child_sec = {
                    "id": self.ids.next(),
                    "name": seq["display_name"],
                    "modules": [],
                    "itemid": sub_int_id,
                    "parent_mod_id": sub_mod_id,
                }
                sub_mods.append(
                    {
                        "mod_id": sub_mod_id,
                        "ctx": sub_ctx_id,
                        "internal_id": sub_int_id,
                        "name": seq["display_name"],
                        "parent_sec_id": ch_sec["id"],
                        "child_sec": child_sec,
                        "seq": seq,
                    }
                )
                ch_sec["modules"].append(sub_mod_id)

        all_sections: list[dict] = []
        sub_cursor = 0
        for ch_i, ch_sec in enumerate(ch_sections):
            all_sections.append(ch_sec)
            n = len(self.c.chapters[ch_i]["sequentials"])
            all_sections.extend(
                sub["child_sec"] for sub in sub_mods[sub_cursor : sub_cursor + n]
            )
            sub_cursor += n

        # Number parent chapters `offset..offset+n-1` and child sections
        # `offset+n..offset+n+m-1`, matching Moodle's course-wide layout and preserving the
        # course-level offset.
        num_ch = len(ch_sections)
        for ch_i, ch_sec in enumerate(ch_sections):
            ch_sec["number"] = ch_i + self.section_offset
        for i, sub in enumerate(sub_mods):
            sub["child_sec"]["number"] = num_ch + i + self.section_offset
        sec_num = {s["id"]: s["number"] for s in all_sections}
        for sub in sub_mods:
            sub["parent_sec_num"] = sec_num[sub["parent_sec_id"]]

        pages: list[dict] = []
        for sub in sub_mods:
            child_sec = sub["child_sec"]
            for vert in sub["seq"]["verticals"]:
                page = self._build_page(vert, child_sec["id"], sec_num[child_sec["id"]])
                if page is None:
                    continue
                pages.append(page)
                child_sec["modules"].append(page["id"])

        return all_sections, sub_mods, pages
