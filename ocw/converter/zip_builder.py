import logging
import posixpath
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from html import escape
from pathlib import Path, PurePosixPath

from bs4 import BeautifulSoup

from ocw.converter.external_report import ExternalContentReport, collect_external
from ocw.parser.base import BaseParser
from ocw.utils import _UNSAFE_FILENAME_RE

log = logging.getLogger("ocw.zip_builder")
_ASSET_REF_RE = re.compile(r"(?:/static/|@@PLUGINFILE@@/)([^\"'>\s)]+)")
_ROOT_INDEX = PurePosixPath("index.html")
_EXTERNAL_DOCX = "external_content.docx"
_PAGE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>{title}</title></head>
<body>
{nav}{body}
</body>
</html>
"""
_EMPTY_BODY = "<p>No content was found on the source page.</p>"
_ASSET_BLACKLIST = (
    re.compile(r"^88x31\.png$"),
    re.compile(r"^featured-Image\.[a-z]+$"),
    re.compile(r"\.zip$"),
)


def _is_blacklisted_asset(name: str) -> bool:
    return any(pattern.search(name) for pattern in _ASSET_BLACKLIST)


def _key(url: str) -> str:
    return url.split("#")[0].rstrip("/")


def _safe_name(text: str, index: int) -> str:
    cleaned = _UNSAFE_FILENAME_RE.sub("_", text).strip("._") or "untitled"
    return f"{index:02d}_{cleaned[:60]}"


def _asset_name(name: str) -> str:
    return _UNSAFE_FILENAME_RE.sub("_", name)


def _rel(target: PurePosixPath, page: PurePosixPath) -> str:
    return posixpath.relpath(target.as_posix(), start=page.parent.as_posix())


@dataclass
class PlannedPage:
    title: str
    path: PurePosixPath
    components: list[dict] = field(default_factory=list)
    summary_html: str = ""


@dataclass
class PlannedChapter:
    index: PlannedPage
    sequentials: list[tuple[str, list[PlannedPage]]] = field(default_factory=list)


@dataclass
class Plan:
    chapters: list[PlannedChapter] = field(default_factory=list)
    readings: list[PlannedPage] = field(default_factory=list)
    shared: list[PlannedPage] = field(default_factory=list)

    def content_pages(self) -> list[PlannedPage]:
        pages = []
        for chapter in self.chapters:
            for _, verticals in chapter.sequentials:
                pages.extend(verticals)
        return pages + self.readings + self.shared


class ZipBuilder:
    """Write a parsed course as a browsable folder structure inside a zip archive."""

    def __init__(self, course: BaseParser) -> None:
        self.course = course
        self._by_url: dict[str, PlannedPage] = {}
        self._skipped_assets: set[str] = set()

    def build(self, out: Path) -> None:
        tmp = Path(tempfile.mkdtemp())
        try:
            slug = _safe_name(self.course.course_name, 0)[3:]
            root = tmp / slug
            plan = self._plan()
            self._copy_assets(root)
            self._write_pages(root, plan)
            self._write_index(root, plan)
            ExternalContentReport(collect_external(self.course)).write(
                root / _EXTERNAL_DOCX
            )
            self._zip(tmp, out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _plan(self) -> Plan:
        plan = Plan()
        for i, chapter in enumerate(self.course.chapters, 1):
            chapter_dir = PurePosixPath(_safe_name(chapter["display_name"], i))
            index = PlannedPage(
                chapter["display_name"],
                chapter_dir / "index.html",
                summary_html=chapter.get("summary_html", ""),
            )
            planned = PlannedChapter(index)
            for j, seq in enumerate(chapter["sequentials"], 1):
                seq_dir = chapter_dir / _safe_name(seq["display_name"], j)
                verticals = [
                    PlannedPage(
                        vert["display_name"],
                        seq_dir / f"{_safe_name(vert['display_name'], k)}.html",
                        vert["components"],
                    )
                    for k, vert in enumerate(seq["verticals"], 1)
                ]
                planned.sequentials.append((seq["display_name"], verticals))
            plan.chapters.append(planned)
        self._plan_linked(plan.readings, self.course.reading_pages, "readings", "reading_url")
        self._plan_linked(plan.shared, self.course.dedup_pages, "shared", "dedup_url")
        return plan

    def _plan_linked(
        self, target: list[PlannedPage], pages: list[dict], folder: str, url_key: str
    ) -> None:
        for i, page in enumerate(pages, 1):
            path = PurePosixPath(folder) / f"{_safe_name(page['display_name'], i)}.html"
            planned = PlannedPage(page["display_name"], path, page["components"])
            self._by_url[_key(page[url_key])] = planned
            target.append(planned)

    def _write_pages(self, root: Path, plan: Plan) -> None:
        for chapter in plan.chapters:
            self._write_page(root, chapter.index, self._chapter_body(chapter))
        for page in plan.content_pages():
            self._write_page(root, page, self._body(page) or _EMPTY_BODY)

    def _write_page(self, root: Path, page: PlannedPage, body: str) -> None:
        nav = f'<p><a href="{escape(_rel(_ROOT_INDEX, page.path))}">Back to index</a></p>\n'
        self._write_html(root / page.path, page.title, body, nav)

    @staticmethod
    def _write_html(target: Path, title: str, body: str, nav: str = "") -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            _PAGE.format(title=escape(title), nav=nav, body=body), encoding="utf-8"
        )

    def _body(self, page: PlannedPage) -> str:
        return "\n".join(self._render(comp, page.path) for comp in page.components)

    def _chapter_body(self, chapter: PlannedChapter) -> str:
        index = chapter.index
        parts = [f"<h1>{escape(index.title)}</h1>"]
        if index.summary_html:
            parts.append(self._localise(index.summary_html, index.path))
        for title, verticals in chapter.sequentials:
            parts.append(f"<h2>{escape(title)}</h2>")
            parts.append(self._link_list(verticals, index.path))
        return "\n".join(parts)

    def _render(self, comp: dict, page: PurePosixPath) -> str:
        match comp["type"]:
            case "html":
                return self._localise(comp["content"], page)
            case "video":
                return self._video_html(comp)
            case "reading_link":
                return self._page_link(comp["reading_url"], page)
            case "dedup_link":
                return self._page_link(comp["dedup_url"], page)
            case other:
                raise ValueError(f"unknown component type: {other}")

    def _localise(self, html: str, page: PurePosixPath) -> str:
        prefix = _rel(PurePosixPath("assets"), page)
        html = _ASSET_REF_RE.sub(
            lambda m: f"{prefix}/{_asset_name(m.group(1))}", html
        )
        return self._strip_scripts(html)

    def _page_link(self, url: str, page: PurePosixPath) -> str:
        target = self._by_url[_key(url)]
        return f'<p><a href="{escape(_rel(target.path, page))}">{escape(target.title)}</a></p>'

    @staticmethod
    def _video_html(comp: dict) -> str:
        src, label = escape(comp["src"]), escape(comp["display_name"])
        return (
            f'<p><a href="{src}">{label} (video)</a></p>'
            f'<iframe src="{src}" title="{label}"></iframe>'
        )

    def _strip_scripts(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("script"):
            tag.decompose()
        for tag in soup.find_all(["img", "a"]):
            ref = tag.get("src") or tag.get("href")
            if isinstance(ref, str) and posixpath.basename(ref) in self._skipped_assets:
                tag.decompose()
        for tag in soup.find_all(True):
            for attr in [a for a in tag.attrs if a.lower().startswith("on")]:
                del tag[attr]
            href = tag.get("href")
            if isinstance(href, str) and href.strip().lower().startswith("javascript:"):
                del tag["href"]
        return str(soup)

    @staticmethod
    def _link_list(pages: list[PlannedPage], page: PurePosixPath) -> str:
        items = "".join(
            f'<li><a href="{escape(_rel(p.path, page))}">{escape(p.title)}</a></li>'
            for p in pages
        )
        return f"<ul>{items}</ul>"

    def _write_index(self, root: Path, plan: Plan) -> None:
        parts = [f"<h1>{escape(self.course.course_name)}</h1>"]
        if self.course.overview_summary_html:
            parts.append(self._localise(self.course.overview_summary_html, _ROOT_INDEX))
        for chapter in plan.chapters:
            parts.append(self._chapter_entry(chapter))
        for heading, pages in (("Readings", plan.readings), ("Shared lectures", plan.shared)):
            if pages:
                parts.append(f"<h2>{heading}</h2>")
                parts.append(self._link_list(pages, _ROOT_INDEX))
        parts.append(f'<p><a href="{_EXTERNAL_DOCX}">External content overview (Docx)</a></p>')
        self._write_html(root / _ROOT_INDEX, self.course.course_name, "\n".join(parts))

    def _chapter_entry(self, chapter: PlannedChapter) -> str:
        head = (
            f'<h2><a href="{escape(_rel(chapter.index.path, _ROOT_INDEX))}">'
            f"{escape(chapter.index.title)}</a></h2>"
        )
        lists = "".join(
            f"<h3>{escape(title)}</h3>{self._link_list(verticals, _ROOT_INDEX)}"
            for title, verticals in chapter.sequentials
        )
        return head + lists

    def _copy_assets(self, root: Path) -> None:
        assets = root / "assets"
        assets.mkdir(parents=True, exist_ok=True)
        for name, source in self.course.static_files.items():
            if _is_blacklisted_asset(name):
                self._skipped_assets.add(_asset_name(name))
                log.info("Skipping blacklisted asset '%s'", name)
                continue
            shutil.copyfile(source, assets / _asset_name(name))

    @staticmethod
    def _zip(tmp: Path, out: Path) -> None:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(tmp.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(tmp).as_posix())