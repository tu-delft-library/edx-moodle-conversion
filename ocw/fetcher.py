"""Fetch approved external assets for inclusion in a Moodle backup."""

import logging
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from ocw.utils import _UNSAFE_FILENAME_RE, resolve_asset_name

log = logging.getLogger("ocw.fetcher")

# Supported download types and their expected MIME types. Keep the mappings in sync.
FETCHABLE_EXTENSIONS = frozenset({
    ".pdf", ".xls", ".xlsx", ".doc", ".docx", ".ppt", ".pptx", ".zip", ".woff2", ".woff",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".mp3",
})
_CONTENT_TYPE_BY_EXT = {
    ".pdf": "application/pdf",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".zip": "application/zip",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".mp3": "audio/mpeg",
}

_MIN_HOST_INTERVAL = 1.0
_TIMEOUT = 15


class HostThrottle:
    """Enforce a minimum interval between requests to the same host, across every session."""

    def __init__(self, interval: float) -> None:
        self._interval = interval
        self._last: dict[str, float] = {}

    def wait(self, url: str) -> None:
        host = urlparse(url).netloc
        delay = self._interval - (time.monotonic() - self._last.get(host, 0.0))
        if delay > 0:
            time.sleep(delay)
        self._last[host] = time.monotonic()


THROTTLE = HostThrottle(_MIN_HOST_INTERVAL)


class AssetFetcher:
    """Fetch approved external assets into `dest_dir`.

    Results are cached by URL for this fetcher's lifetime. Requests to the same host are rate
    limited through `THROTTLE` to avoid repeatedly hitting the source service.
    """

    def __init__(self, dest_dir: Path) -> None:
        self.dest_dir = dest_dir
        self._session = requests.Session()
        self._cache: dict[str, Path | None] = {}
        self._text_cache: dict[str, str | None] = {}

    def fetch(self, url: str, name: str | None = None) -> Path | None:
        """Fetch `url` once and return its local path, or `None` when it is unsupported or unavailable.

        `name` saves the file under that name and takes its expected type from it, for URLs
        without a file extension. Failed results are cached too, so repeated references do not
        repeat network requests.
        """
        if url not in self._cache:
            self._cache[url] = self._fetch_uncached(url, name or _safe_filename(url))
        return self._cache[url]

    def _fetch_uncached(self, url: str, name: str) -> Path | None:
        """Download one uncached supported asset and validate its response type."""
        ext = Path(name).suffix.lower()
        if ext not in FETCHABLE_EXTENSIONS:
            return None
        path = self.dest_dir / name
        if path.exists():
            return path

        THROTTLE.wait(url)
        try:
            resp = self._session.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            log.warning("Failed to fetch external asset '%s': %s", url, e)
            return None

        content_type = resp.headers.get("content-type", "").split(";")[0].strip()
        if content_type != _CONTENT_TYPE_BY_EXT[ext]:
            log.warning(
                "External asset '%s' returned content-type '%s', expected '%s' — skipping "
                "(likely an auth wall or error page)",
                url,
                content_type or "<none>",
                _CONTENT_TYPE_BY_EXT[ext],
            )
            return None

        path.write_bytes(resp.content)
        log.info("DOWNLOAD: Fetched external asset '%s' -> %s", url, path.name)
        return path

    def fetch_text(self, url: str) -> str | None:
        """Fetch a page's text once, or `None` when unavailable. Failures are cached too."""
        if url not in self._text_cache:
            self._text_cache[url] = self._fetch_text_uncached(url)
        return self._text_cache[url]

    def _fetch_text_uncached(self, url: str) -> str | None:
        THROTTLE.wait(url)
        try:
            resp = self._session.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            log.warning("Failed to fetch page '%s': %s", url, e)
            return None
        return resp.text


def _safe_filename(url: str) -> str:
    """Convert a resolved asset name from `url` into a filesystem-safe filename."""
    return _UNSAFE_FILENAME_RE.sub("_", resolve_asset_name(url))
