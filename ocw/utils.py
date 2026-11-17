"""Shared helpers for Moodle backup generation, source assets, and conversion diagnostics.

The asset regexes here match source urls that may become a static file ref. Refs to files already
bundled (`/static/`, `@@PLUGINFILE@@/`) are matched in `ocw/assets.py`.
"""

import hashlib
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

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

_UNSAFE_FILENAME_RE = re.compile(r"[^-\w.]")

_LOG_LINE_RE = re.compile(r"^(\d{2}:\d{2}:\d{2}) \[(\w+)\] (.*)$")

_DFRAME_RE = re.compile(
    r'<iframe\b[^>]*class="[^"]*\bdframe\b[^"]*"[^>]*>', re.IGNORECASE
)
_DOWNLOADID_RE = re.compile(r'data-downloadid="([^"]*)"')

_XML_ILLEGAL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


def safe_vidkey(raw: str) -> str:
    """Convert a source video identifier into a key safe for vidrouter placeholders and lookups."""
    return _VIDKEY_UNSAFE_RE.sub("_", raw)


def esc(s: str | None) -> str:
    """Escape a value for XML text or attribute insertion."""
    return (
        _XML_ILLEGAL_CHARS_RE.sub("", s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def html_to_plain_text(html: str) -> str:
    """Collapse HTML markup down to plain text, for metadata fields that reject markup."""
    return BeautifulSoup(html, "lxml").get_text(" ", strip=True)


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
    """Return the local filename represented by a source asset reference."""
    if url.startswith("http"):
        match = _ABSOLUTE_ASSET_RE.search(url)
        return match.group(1) if match else (Path(urlparse(url).path).name or url)
    match = _RELATIVE_ASSET_RE.search(url)
    return match.group(1) if match else url.removeprefix("/static/")


def rewrite_static_urls(html: str, static_files: dict[str, Path] | None = None) -> str:
    """Rewrite embedded local assets to Moodle's `@@PLUGINFILE@@` placeholder."""
    html = re.sub(r'/static/([^"\'>\s]+)', r"@@PLUGINFILE@@/\1", html)
    if not static_files:
        return html

    def _rewrite_asset(m: re.Match) -> str:
        name = m.group(1)
        return f"@@PLUGINFILE@@/{name}" if name in static_files else m.group(0)

    html = _ABSOLUTE_ASSET_RE.sub(_rewrite_asset, html)
    return _RELATIVE_ASSET_RE.sub(_rewrite_asset, html)


# Regex alternation of the edX domains, shared with `PLATFORM_LINK_RE` in `ocw/converter/html.py`.
EDX_DOMAINS = r"edx\.org|edx-video\.net|edx-cdn\.org|edxapp\.org|edx\.readthedocs\.(?:org|io)"

# Hosts that mean "still depends on edX or DelftX infrastructure": checked by the audit and the WP zip.
PLATFORM_HOST_RE = re.compile(
    rf"(^|\.)({EDX_DOMAINS}"
    r"|d2f1egay8yehza\.cloudfront\.net|d37djvu3ytnwxt\.cloudfront\.net"
    r"|delftx[\w-]*\.tudelft\.nl)$",
    re.IGNORECASE,
)

OCW_HOST = "ocw.tudelft.nl"


def hostname(url: str) -> str:
    return urlparse(url.strip()).hostname or ""


def in_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def is_ocw_host(host: str) -> bool:
    return in_domain(host, OCW_HOST)


def is_platform_host(host: str) -> bool:
    return bool(PLATFORM_HOST_RE.search(host))


def is_dead_host(host: str) -> bool:
    """Hosts the WP zip must not leave a live link to: ocw.tudelft.nl and the edX / DelftX hosts."""
    return is_ocw_host(host) or is_platform_host(host)


# Parse time warning for edX content. Same hosts as `PLATFORM_HOST_RE` bar the delftx ones (the download widget keeps
# its delftxdownloads Video / Subtitles links on purpose), and generic `www.edx.org` links are excluded.
_EDX_HOST_RE = re.compile(
    r"(?:https?:)?//(?:"
    rf"(?!www\.edx\.org)(?:[\w-]+\.)*(?:{EDX_DOMAINS})"
    r"|d2f1egay8yehza\.cloudfront\.net"
    r"|d37djvu3ytnwxt\.cloudfront\.net"
    r')[^"\'>\s]*'
)


def warn_external_edx_urls(
    html: str, context: str = "", static_files: dict[str, Path] | None = None
) -> None:
    """Warn about EdX-hosted URLs that will remain external after conversion."""
    for match in _EDX_HOST_RE.findall(html):
        if static_files and resolve_asset_name(match) in static_files:
            continue
        log.warning(
            "Content still hosted on edX%s: '%s'",
            f" on page '{context}'" if context else "",
            match,
        )


_WP_HOST_RE = re.compile(r'(?:https?:)?//(?:[\w-]+\.)*ocw\.tudelft\.nl[^"\'>\s]*')


def warn_external_wp_urls(html: str, context: str = "") -> None:
    """Warn about ocw.tudelft.nl-hosted URLs that will remain external after conversion."""
    for match in _WP_HOST_RE.findall(html):
        log.warning(
            "Content still hosted on ocw.tudelft.nl%s: '%s'",
            f" on page '{context}'" if context else "",
            match,
        )
