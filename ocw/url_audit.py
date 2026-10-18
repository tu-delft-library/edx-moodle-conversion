"""Find every edX / DelftX (delftxdownloads, delftxtools, ...) URL in a built MBZ that isn't one of the two allowed cases:
a Video/Subtitles link inside the inlined download widget, or a video record in the course-level
vidrouter block."""

import html
import logging
import posixpath
import re
import tarfile
import warnings
import zipfile
from xml.etree import ElementTree
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from openpyxl import load_workbook

from ocw.assets import WIDGET_MEDIA_LINKS
from ocw.converter.external_report import _OCW_HOST, _in_domain, _refs_in_html
from ocw.utils import PLATFORM_HOST_RE

_URL_RE = re.compile(r"(?:https?:)?//[^\s\"'<>)]+")
_ZIP_URL_ATTRS = (("a", "href"), ("img", "src"), ("iframe", "src"), ("link", "href"), ("source", "src"))
_ASSET_REF_RE = re.compile(r"assets/([^\"'\s)<>#?]+)")
_TABLE_URL_COLUMN = 2
_TABLE_KINDS_ON_PAGES = frozenset({"link", "embed", "video"})
_ZIP_XLSX = "external_content.xlsx"
_ZIP_DOCX = "course.docx"
_DOCX_RELS = "word/_rels/document.xml.rels"
_HYPERLINK_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
_VIDROUTER_RE = re.compile(
    r"<plugin_local_vidrouter_course>.*?</plugin_local_vidrouter_course>", re.DOTALL
)


@dataclass(frozen=True)
class Hit:
    member: str
    element: str
    url: str


def _watched_host(host: str) -> bool:
    return bool(PLATFORM_HOST_RE.search(host))


def _watched(url: str) -> bool:
    return _watched_host(url.split("//", 1)[1].split("/", 1)[0].split(":")[0].lower())


def audit_html(member: str, fragment: str) -> list[Hit]:
    """Every watched-host URL in `fragment`, in any attribute or text, that isn't a widget
    Video/Subtitles link."""
    soup = BeautifulSoup(fragment, "html.parser")
    allowed = {id(a) for a in soup.select(WIDGET_MEDIA_LINKS)}
    hits = []
    for el in soup.find_all(True):
        for attr, value in el.attrs.items():
            values = value if isinstance(value, list) else [value]
            for url in (u for v in values for u in _URL_RE.findall(v)):
                if _watched(url) and not (attr == "href" and id(el) in allowed):
                    hits.append(Hit(member, f"<{el.name} {attr}>", url))
    for text in soup.find_all(string=True):
        hits += [Hit(member, "text", u) for u in _URL_RE.findall(text) if _watched(u)]
    return hits


def audit_mbz(mbz: Path) -> list[Hit]:
    """Audit every XML member, once unescaped back to the HTML it carries. The vidrouter block
    in `course/course.xml` is the one place videos may live, so it's cut out first."""
    hits = []
    with warnings.catch_warnings(), tarfile.open(mbz) as tar:
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        for m in tar.getmembers():
            if not (m.isfile() and m.name.endswith(".xml")):
                continue
            text = _VIDROUTER_RE.sub("", tar.extractfile(m).read().decode())
            hits += audit_html(m.name, html.unescape(text))
    return hits


def _page_urls(page: str) -> list[tuple[str, str, str]]:
    """Every `(tag, attribute, url)` a page links to, srcset candidates included."""
    soup = BeautifulSoup(page, "html.parser")
    found = []
    for tag, attr in _ZIP_URL_ATTRS:
        found += [(tag, attr, el[attr].strip()) for el in soup.find_all(tag, **{attr: True})]
    for el in soup.find_all(srcset=True):
        found += [(el.name, "srcset", c.split()[0]) for c in el["srcset"].split(",") if c.strip()]
    return found


def _widget_media_urls(page: str) -> set[str]:
    return {a["href"].strip() for a in BeautifulSoup(page, "html.parser").select(WIDGET_MEDIA_LINKS)}


def _is_local(url: str) -> bool:
    parts = urlparse(url)
    return not (parts.scheme or parts.netloc or url.startswith("#"))


def _table_urls(zf: zipfile.ZipFile, prefix: str) -> tuple[set[str], set[str]]:
    """URLs in the external content xlsx: all of them, and those expected to still be on a page."""
    with zf.open(f"{prefix}{_ZIP_XLSX}") as handle:
        rows = list(load_workbook(handle, read_only=True).active.iter_rows(min_row=2, values_only=True))
    rows = [r for r in rows if r[_TABLE_URL_COLUMN]]
    on_pages = {r[_TABLE_URL_COLUMN] for r in rows if r[1] in _TABLE_KINDS_ON_PAGES}
    return {r[_TABLE_URL_COLUMN] for r in rows}, on_pages


def _docx_links(zf: zipfile.ZipFile, prefix: str) -> list[str]:
    with zf.open(f"{prefix}{_ZIP_DOCX}") as handle, zipfile.ZipFile(handle) as docx:
        rels = ElementTree.fromstring(docx.read(_DOCX_RELS))
    return [r.get("Target", "").strip() for r in rels if r.get("Type") == _HYPERLINK_TYPE]


def _audit_docx(member: str, links: list[str], names: set[str], allowed: set[str]) -> list[Hit]:
    hits = []
    for url in links:
        host = urlparse(url).hostname or ""
        if _is_local(url):
            target = posixpath.normpath(posixpath.join(posixpath.dirname(member), unquote(urlparse(url).path)))
            if urlparse(url).path and target not in names:
                hits.append(Hit(member, "broken link <hyperlink>", url))
        elif _in_domain(host, _OCW_HOST):
            hits.append(Hit(member, "ocw link <hyperlink>", url))
        elif _watched_host(host) and url not in allowed:
            hits.append(Hit(member, "platform link <hyperlink>", url))
    return hits


def audit_zip(zip_path: Path) -> list[Hit]:
    """Check a built WP zip: no `ocw.tudelft.nl` or edX/DelftX link left (bar the widget Video/Subtitles links), every relative link resolves to a file in
    the zip, the external content table and the pages list the same non OCW URLs, and every file in
    `assets/` is used by a page."""
    hits = []
    with zipfile.ZipFile(zip_path) as zf:
        names = {n for n in zf.namelist() if not n.endswith("/")}
        prefix = f"{PurePosixPath(sorted(names)[0]).parts[0]}/"
        pages = {n: zf.read(n).decode("utf-8") for n in sorted(names) if n.endswith(".html")}
        table_urls, table_page_urls = _table_urls(zf, prefix)
        docx_links = _docx_links(zf, prefix)

    page_urls = set()
    asset_refs = set()
    media = set().union(*(_widget_media_urls(page) for page in pages.values()))
    for member, page in pages.items():
        asset_refs.update(unquote(m) for m in _ASSET_REF_RE.findall(page))
        for tag, attr, url in _page_urls(page):
            page_urls.add(url)
            element = f"<{tag} {attr}>"
            if _is_local(url):
                path = unquote(urlparse(url).path)
                target = posixpath.normpath(posixpath.join(posixpath.dirname(member), path))
                if path and target not in names:
                    hits.append(Hit(member, f"broken link {element}", url))
            elif _in_domain(urlparse(url).hostname or "", _OCW_HOST):
                hits.append(Hit(member, f"ocw link {element}", url))
            elif _watched_host(urlparse(url).hostname or "") and url not in media:
                hits.append(Hit(member, f"platform link {element}", url))
        hits += [
            Hit(member, "missing from table", ref.url)
            for ref in _refs_in_html(page, member)
            if ref.url not in table_urls
        ]
    hits += _audit_docx(f"{prefix}{_ZIP_DOCX}", docx_links, names, media | table_urls)
    hits += [
        Hit(_ZIP_XLSX, "not on any page", url)
        for url in sorted(table_page_urls - page_urls)
        if not any(url in page for page in pages.values())
    ]
    hits += [
        Hit(n, "orphan asset", PurePosixPath(n).name)
        for n in sorted(names)
        if n.startswith(f"{prefix}assets/") and PurePosixPath(n).name not in asset_refs
    ]
    return hits


def report(hits: list[Hit]) -> str:
    return "\n".join(f"{h.member}  {h.element}  {h.url}" for h in hits)


def log_url_audit(mbz: Path, log: logging.Logger) -> None:
    """Warn about every edX/DelftX URL left in a built MBZ, besides widget links and video records."""
    hits = sorted(set(audit_mbz(mbz)), key=lambda h: (h.member, h.url))
    for h in hits:
        log.warning("URL AUDIT: %s %s %s", h.member, h.element, h.url)
    level = logging.WARNING if hits else logging.INFO
    log.log(level, "URL AUDIT: %d edX/DelftX URL(s) left in %s", len(hits), mbz.name)
