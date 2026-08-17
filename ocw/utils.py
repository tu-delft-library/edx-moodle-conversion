import hashlib
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from ocw._version import __version__

log = logging.getLogger("ocw.converter")


def versioned_output_path(path: Path) -> Path:
    """Insert the ocw version into an output filename: course.mbz -> course_v1.2.3.mbz."""
    return path.with_name(f"{path.stem}_{__version__}{path.suffix}")


# INFO: This helps keep track of each unique XML element when parsing and reconstructing
class _Counter:
    """Sequential integer ID generator for Moodle XML elements."""

    def __init__(self, start: int = 100) -> None:
        self._n = start

    def next(self) -> int:
        """Return the next ID and advance the counter."""
        v = self._n
        self._n += 1
        return v


_VIDKEY_UNSAFE_RE = re.compile(r"[^A-Za-z0-9_-]")


def safe_vidkey(raw: str) -> str:
    """Sanitize a video source id/slug down to the charset the vidrouter
    placeholder ([[vid:{key}]]) and its DB lookup key can safely contain."""
    return _VIDKEY_UNSAFE_RE.sub("_", raw)


def esc(s: str) -> str:
    """XML-escape a string, treating None as empty."""
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def sha1_of(path: Path) -> str:
    """Return the hex SHA-1 digest of a file's contents."""
    return hashlib.sha1(path.read_bytes()).hexdigest()


def static_file_kind(filename: str) -> str:
    match Path(filename).suffix.lower():
        case ".png" | ".jpg" | ".jpeg" | ".gif" | ".svg" | ".webp":
            return "image"
        case ".mp4" | ".webm" | ".ogv":
            return "video"
        case ".mp3" | ".ogg" | ".wav":
            return "audio"
        case ".pdf":
            return "pdf"
        case _:
            return "file"


_ABSOLUTE_ASSET_RE = re.compile(
    r'https?://(?:[\w-]+\.)*edx\.org[^"\'>\s]*?'
    r'(?:asset-v1:[^"\'>\s]*?type@asset\+block@|/c4x/[^"\'>\s]*/asset/)([^"\'>\s]+)'
)

# Same asset-v1/c4x addressing, but the bare relative form OLX also emits (no host at
# all, e.g. src="/asset-v1:Org+Course+Run+type@asset+block@name.png") — distinct from
# _ABSOLUTE_ASSET_RE, which requires an edx.org host to avoid mistaking this for one.
_RELATIVE_ASSET_RE = re.compile(
    r'(?:asset-v1:[^"\'>\s]*?type@asset\+block@|/c4x/[^"\'>\s]*/asset/)([^"\'>\s]+)'
)


def resolve_asset_name(url: str) -> str:
    """Bare filename an asset reference should resolve to in static_files, regardless of
    whether url is a /static/-relative path or an absolute edX asset URL. Falls back to
    the URL's last path segment for an absolute URL that doesn't match the recognized
    asset-addressing pattern — display-only, not a signal that url is fetchable."""
    if url.startswith("http"):
        match = _ABSOLUTE_ASSET_RE.search(url)
        return match.group(1) if match else (Path(urlparse(url).path).name or url)
    return url.removeprefix("/static/")


def rewrite_static_urls(html: str, static_files: dict[str, Path] | None = None) -> str:
    """Replace /static/<name> with @@PLUGINFILE@@/<name> for Moodle file embedding, and
    the same for an edX asset-v1/c4x reference — absolute (with an edx.org host) or the
    bare relative form OLX also emits — whose resolved name is in static_files (i.e. it
    was fetched or otherwise resolved locally). An unresolved reference is left as-is
    rather than rewritten into a dangling @@PLUGINFILE@@ link."""
    html = re.sub(r'/static/([^"\'>\s]+)', r"@@PLUGINFILE@@/\1", html)
    if not static_files:
        return html

    def _rewrite_asset(m: re.Match) -> str:
        name = m.group(1)
        return f"@@PLUGINFILE@@/{name}" if name in static_files else m.group(0)

    html = _ABSOLUTE_ASSET_RE.sub(_rewrite_asset, html)
    return _RELATIVE_ASSET_RE.sub(_rewrite_asset, html)


# Confirmed against 26 real course exports in files/OLX/ (see PLAN_2.md "Survey findings").
# www.edx.org deliberately excluded — those are generic marketing/FAQ links, not asset
# dependencies. edx-video.net / cloudfront are included here for completeness but in
# practice never match: those URLs live in video/*.xml, not html content — see the
# _parse_video gap noted under PLAN_2.md "Out of scope".
_EDX_HOST_RE = re.compile(
    r'https?://(?:'
    r'(?!www\.edx\.org)(?:[\w-]+\.)*edx\.org'       # courses./studio./learning./support./
                                                      # discussions./ecommerce./help./files./
                                                      # course-authoring./payment.edx.org
    r'|(?:[\w-]+\.)*edx-video\.net'                  # edx-video.net, prod-images.edx-video.net
    r'|d2f1egay8yehza\.cloudfront\.net'              # edX's video cloudfront distribution
    r'|edx\.readthedocs\.(?:org|io)'
    r')[^"\'>\s]*'
)


def warn_external_edx_urls(
    html: str, context: str = "", static_files: dict[str, Path] | None = None
) -> None:
    """Warn on any absolute URL still pointing at edX-hosted infrastructure — skips a URL
    whose resolved asset name is already in static_files (bundled locally, or fetched),
    since rewrite_static_urls rewrites that one to a local file at build time instead of
    leaving it external."""
    for match in _EDX_HOST_RE.findall(html):
        if static_files and resolve_asset_name(match) in static_files:
            continue
        log.warning(
            "Content still hosted on edX%s: '%s'",
            f" on page '{context}'" if context else "",
            match,
        )


