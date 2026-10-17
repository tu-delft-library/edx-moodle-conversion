"""Find every edX / DelftX (delftxdownloads, delftxtools, ...) URL in a built MBZ that isn't one of the two allowed cases:
a Video/Subtitles link inside the inlined download widget, or a video record in the course-level
vidrouter block."""

import html
import re
import tarfile
import warnings
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

WATCHED_HOST_RE = re.compile(
    r"(^|\.)(edx\.org|edx-video\.net|edx-cdn\.org|edxapp\.org|delftx[\w-]*\.tudelft\.nl)$"
)
_URL_RE = re.compile(r"(?:https?:)?//[^\s\"'<>)]+")
_WIDGET_TABS = (
    ".TUD_box_download .video-download a[href], .TUD_box_download .subtitle-download a[href]"
)
_VIDROUTER_RE = re.compile(
    r"<plugin_local_vidrouter_course>.*?</plugin_local_vidrouter_course>", re.DOTALL
)


@dataclass(frozen=True)
class Hit:
    member: str
    element: str
    url: str


def _watched(url: str) -> bool:
    host = url.split("//", 1)[1].split("/", 1)[0].split(":")[0].lower()
    return bool(WATCHED_HOST_RE.search(host))


def audit_html(member: str, fragment: str) -> list[Hit]:
    """Every watched-host URL in `fragment`, in any attribute or text, that isn't a widget
    Video/Subtitles link."""
    soup = BeautifulSoup(fragment, "html.parser")
    allowed = {id(a) for a in soup.select(_WIDGET_TABS)}
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
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    with tarfile.open(mbz) as tar:
        for m in tar.getmembers():
            if not (m.isfile() and m.name.endswith(".xml")):
                continue
            text = _VIDROUTER_RE.sub("", tar.extractfile(m).read().decode())
            hits += audit_html(m.name, html.unescape(text))
    return hits


def report(hits: list[Hit]) -> str:
    return "\n".join(f"{h.member}  {h.element}  {h.url}" for h in hits)
