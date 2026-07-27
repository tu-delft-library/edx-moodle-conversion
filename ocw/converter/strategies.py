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
from ocw.parser import Course
from ocw.utils import _Counter, rewrite_static_urls


class SectionStrategy(ABC):
    """Turns a parsed Course into (all_sections, sub_mods, pages) for the MBZ writer."""

    def __init__(self, course: Course, ids: _Counter, section_offset: int = 0) -> None:
        self.c = course
        self.ids = ids
        # NOTE: non-zero when an Overview section (Syllabus/Readings) is
        # prepended ahead of these chapter-derived sections, so numbering
        # starts after it instead of colliding with its <number>0</number>.
        self.section_offset = section_offset

    @abstractmethod
    def build(self) -> tuple[list[dict], list[dict], list[dict]]:
        """Returns (all_sections, sub_mods, pages)."""

    # NOTE: Whenever we append structural things i think it should always be in an auxillory function so that we keep a grasp on expected structure
    def _build_page(self, vert: dict, sec_id: int, sec_num: int) -> dict | None:
        """Shared: turn a vertical's html components into a page dict, or None if it has none."""
        parts = []
        for comp in vert["components"]:
            if comp["type"] == "html":
                parts.append(
                    style_figcaption(
                        constrain_table_size(
                            constrain_img_size(
                                mark_hyperlinks_nomediaplugin(
                                    strip_templated_iframes(
                                        strip_blacklisted_classes(rewrite_static_urls(comp["content"]))
                                    )
                                )
                            )
                        )
                    )
                    + '<div style="clear:both"></div>'
                )
            elif comp["type"] == "video":
                parts.append(f"<p>[[vid:{comp['vidkey']}]]</p>")
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
    """sequential_sections=True: one section per sequential, no subsections."""

    def build(self) -> tuple[list[dict], list[dict], list[dict]]:
        sections: list[dict] = []
        sec_idx_for: dict[int, int] = {}
        for ch in self.c.chapters:
            for seq in ch["sequentials"]:
                sec_idx_for[id(seq)] = len(sections)
                sections.append(
                    {
                        "id": self.ids.next(),
                        "name": f"{ch['display_name']} - {seq['display_name']}",
                        "modules": [],
                        # explicit, offset-aware — must not rely on
                        # _write_section's positional idx+1 fallback, which
                        # would silently drift from sec_num below the moment
                        # anything gets prepended to all_sections (e.g. an
                        # Overview section)
                        "number": len(sections) + 1 + self.section_offset,
                    }
                )

        pages: list[dict] = []
        for ch in self.c.chapters:
            for seq in ch["sequentials"]:
                sec_idx = sec_idx_for[id(seq)]
                sec = sections[sec_idx]
                for vert in seq["verticals"]:
                    page = self._build_page(vert, sec["id"], sec_idx + 1 + self.section_offset)
                    if page is None:
                        continue
                    pages.append(page)
                    sec["modules"].append(page["id"])

        return sections, [], pages


class NestedSectionStrategy(SectionStrategy):
    """sequential_sections=False: chapters become sections, sequentials become subsections."""

    def build(self) -> tuple[list[dict], list[dict], list[dict]]:
        sub_mods: list[dict] = []
        ch_sections: list[dict] = []
        for ch in self.c.chapters:
            ch_sec = {"id": self.ids.next(), "name": ch["display_name"], "modules": []}
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
            all_sections.extend(sub["child_sec"] for sub in sub_mods[sub_cursor : sub_cursor + n])
            sub_cursor += n

        # number parent chapters offset..offset+n-1, child sections
        # offset+n..offset+n+m-1 (matching Moodle's DB layout, shifted past
        # any prepended Overview section)
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
