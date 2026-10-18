"""One place that decides how a static file ref is found, named and kept, for the MBZ and the zip."""

import re

from ocw.utils import _UNSAFE_FILENAME_RE

STATIC_REF_RE = re.compile(r"(?:/static/|@@PLUGINFILE@@/)([^\"'>\s)#?]+)")

# Fetched like any asset, but only the MBZ ships them (course image, banner and licence badge).
ASSET_BLACKLIST = (
    re.compile(r"^88x31\.png$"),
    re.compile(r"^featured-Image\.[a-z]+$"),
)

# The inlined download widget's Video/Subtitles links: the one place a platform URL may stay a link.
WIDGET_MEDIA_LINKS = (
    ".TUD_box_download .video-download a[href], .TUD_box_download .subtitle-download a[href]"
)


def static_refs(html: str) -> list[str]:
    return STATIC_REF_RE.findall(html)


def is_skipped_asset(name: str) -> bool:
    return any(pattern.search(name) for pattern in ASSET_BLACKLIST)


def asset_name(name: str) -> str:
    return _UNSAFE_FILENAME_RE.sub("_", name)
