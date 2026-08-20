"""Shared helpers for Moodle backup generation, source assets, and conversion diagnostics."""

import hashlib
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from ocw._version import __version__

log = logging.getLogger("ocw.converter")


def versioned_output_path(path: Path) -> Path:
    """Insert the current OCW version before an output file's extension."""
    return path.with_name(f"{path.stem}_{__version__}{path.suffix}")


class _Counter:
    """Allocate monotonically increasing IDs for one MBZ build.

    One instance is shared across record builders and XML writers so every cross-file reference
    remains unique.
    """

    def __init__(self, start: int = 100) -> None:
        self._n = start

    def next(self) -> int:
        """Return the next ID and advance the counter."""
        v = self._n
        self._n += 1
        return v


_VIDKEY_UNSAFE_RE = re.compile(r"[^A-Za-z0-9_-]")


def safe_vidkey(raw: str) -> str:
    """Convert a source video identifier into a key safe for vidrouter placeholders and lookups."""
    return _VIDKEY_UNSAFE_RE.sub("_", raw)


def esc(s: str | None) -> str:
    """Escape a value for XML text or attribute insertion.

    `None` becomes an empty string.
    """
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def sha1_of(path: Path) -> str:
    """Return the lowercase SHA-1 digest of `path`'s contents."""
    return hashlib.sha1(path.read_bytes()).hexdigest()


def static_file_kind(filename: str) -> str:
    """Classify a static filename for missing-asset warnings."""
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


# Absolute edX asset-v1 and legacy c4x references.
_ABSOLUTE_ASSET_RE = re.compile(
    r'https?://(?:[\w-]+\.)*edx\.org[^"\'>\s]*?'
    r'(?:asset-v1:[^"\'>\s]*?type@asset\+block@|/c4x/[^"\'>\s]*/asset/)([^"\'>\s]+)'
)

# Equivalent asset-v1 and c4x references without an edX hostname.
_RELATIVE_ASSET_RE = re.compile(
    r'(?:asset-v1:[^"\'>\s]*?type@asset\+block@|/c4x/[^"\'>\s]*/asset/)([^"\'>\s]+)'
)


def resolve_asset_name(url: str) -> str:
    """Return the local filename represented by a source asset reference.

    Recognises `/static/`, edX asset-v1, and legacy c4x forms. Unknown absolute URLs fall back to
    their final path segment.
    """
    if url.startswith("http"):
        match = _ABSOLUTE_ASSET_RE.search(url)
        return match.group(1) if match else (Path(urlparse(url).path).name or url)
    match = _RELATIVE_ASSET_RE.search(url)
    return match.group(1) if match else url.removeprefix("/static/")


def rewrite_static_urls(html: str, static_files: dict[str, Path] | None = None) -> str:
    """Rewrite embedded local assets to Moodle's `@@PLUGINFILE@@` placeholder.

    `/static/` references are always local. Asset-v1 and c4x references are rewritten only when
    their resolved filename exists in `static_files`, leaving unresolved external references intact.
    """
    html = re.sub(r'/static/([^"\'>\s]+)', r"@@PLUGINFILE@@/\1", html)
    if not static_files:
        return html

    def _rewrite_asset(m: re.Match) -> str:
        name = m.group(1)
        return f"@@PLUGINFILE@@/{name}" if name in static_files else m.group(0)

    html = _ABSOLUTE_ASSET_RE.sub(_rewrite_asset, html)
    return _RELATIVE_ASSET_RE.sub(_rewrite_asset, html)


# EdX domains that indicate a course-content dependency. Generic `www.edx.org` links are excluded.
_EDX_HOST_RE = re.compile(
    r'https?://(?:'
    r'(?!www\.edx\.org)(?:[\w-]+\.)*edx\.org'
    r'|(?:[\w-]+\.)*edx-video\.net'
    r'|d2f1egay8yehza\.cloudfront\.net'
    r'|edx\.readthedocs\.(?:org|io)'
    r')[^"\'>\s]*'
)


def warn_external_edx_urls(
    html: str, context: str = "", static_files: dict[str, Path] | None = None
) -> None:
    """Warn about EdX-hosted URLs that will remain external after conversion.

    Locally packaged or fetched assets are skipped because `rewrite_static_urls()` embeds them in
    the Moodle backup instead.
    """
    for match in _EDX_HOST_RE.findall(html):
        if static_files and resolve_asset_name(match) in static_files:
            continue
        log.warning(
            "Content still hosted on edX%s: '%s'",
            f" on page '{context}'" if context else "",
            match,
        )
