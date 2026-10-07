from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from ocw.parser.base import BaseParser
from ocw.utils import _XML_ILLEGAL_CHARS_RE

_OCW_HOST = "ocw.tudelft.nl"
# Domains never reported (each entry also covers its subdomains). Add boilerplate hosts here.
_BLACKLIST = frozenset({"creativecommons.org", "amazon.com"})
_HYPERLINK_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
_HTML_REFS = (("a", "href", "link"), ("iframe", "src", "embed"), ("img", "src", "image"))


@dataclass(frozen=True)
class ExternalRef:
    title: str
    url: str
    kind: str
    page: str


def _in_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _is_blacklisted(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(_in_domain(host, domain) for domain in _BLACKLIST)


def _is_external(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return (
        parsed.scheme in ("http", "https")
        and not _in_domain(host, _OCW_HOST)
        and not _is_blacklisted(url)
    )


def _fallback_title(url: str) -> str:
    parsed = urlparse(url)
    last = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    return f"{parsed.hostname}/{last}" if last else parsed.hostname


def _refs_in_html(html: str, page: str) -> list[ExternalRef]:
    soup = BeautifulSoup(html, "lxml")
    refs = []
    for tag, attr, kind in _HTML_REFS:
        for el in soup.find_all(tag, **{attr: True}):
            url = el[attr]
            if _is_external(url):
                title = el.get("title") or el.get("alt") or el.get_text(" ", strip=True)
                refs.append(ExternalRef(title.strip() or _fallback_title(url), url, kind, page))
    return refs


def _all_components(course: BaseParser) -> Iterator[tuple[str, list[dict]]]:
    if course.overview_summary_html:
        yield "Course overview", [{"type": "html", "content": course.overview_summary_html}]
    for chapter in course.chapters:
        if chapter.get("summary_html"):
            yield chapter["display_name"], [{"type": "html", "content": chapter["summary_html"]}]
        for sequential in chapter["sequentials"]:
            for vertical in sequential["verticals"]:
                yield vertical["display_name"], vertical["components"]
    for page in course.reading_pages + course.dedup_pages:
        yield page["display_name"], page["components"]


def collect_external(course: BaseParser) -> list[ExternalRef]:
    """List every video embed, third party link and unlocalised image in the course."""
    refs: list[ExternalRef] = []
    for page_name, components in _all_components(course):
        for comp in components:
            if comp["type"] == "video" and not _is_blacklisted(comp["src"]):
                refs.append(ExternalRef(comp["display_name"], comp["src"], "video", page_name))
            elif comp["type"] == "html":
                refs.extend(_refs_in_html(comp["content"], page_name))
    return refs


def _clean(text: str) -> str:
    return _XML_ILLEGAL_CHARS_RE.sub("", text)


def merge_refs(refs: list[ExternalRef]) -> list[tuple[ExternalRef, list[str]]]:
    """Collapse refs with an identical URL into one entry, keeping every page they were found on."""
    merged: dict[str, tuple[ExternalRef, list[str]]] = {}
    for ref in refs:
        _, pages = merged.setdefault(ref.url, (ref, []))
        if ref.page not in pages:
            pages.append(ref.page)
    return list(merged.values())


def _found_on(pages: list[str]) -> str:
    if len(pages) == 1:
        return pages[0]
    if len(pages) == 2:
        return f"found on both: {pages[0]}; {pages[1]}"
    joined = "; ".join(pages)
    return f"found on {len(pages)} pages: {joined}"


class ExternalContentReport:
    """Write external references as a Docx table with clickable URLs."""

    def __init__(self, refs: list[ExternalRef]) -> None:
        self.refs = refs

    def write(self, path: Path) -> None:
        doc = Document()
        doc.add_heading("External content", level=0)
        table = doc.add_table(rows=1, cols=4)
        for cell, label in zip(table.rows[0].cells, ("Title", "Type", "URL", "Found on")):
            cell.text = label
        for ref, pages in merge_refs(self.refs):
            row = table.add_row().cells
            row[0].text, row[1].text, row[3].text = _clean(ref.title), ref.kind, _clean(_found_on(pages))
            self._add_hyperlink(row[2].paragraphs[0], ref.url)
        doc.save(path)

    @staticmethod
    def _add_hyperlink(paragraph, url: str) -> None:
        rel_id = paragraph.part.relate_to(url, _HYPERLINK_REL, is_external=True)
        link = OxmlElement("w:hyperlink")
        link.set(qn("r:id"), rel_id)
        run, text = OxmlElement("w:r"), OxmlElement("w:t")
        text.text = _clean(url)
        run.append(text)
        link.append(run)
        paragraph._p.append(link)