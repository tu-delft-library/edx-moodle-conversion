import logging
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from ocw.utils import resolve_asset_name

log = logging.getLogger("ocw.fetcher")

# Fetch allowlist. Extend this + _CONTENT_TYPE_BY_EXT together to support a new file type —
# nothing else in this module is PDF-specific.
FETCHABLE_EXTENSIONS = frozenset({".pdf"})
_CONTENT_TYPE_BY_EXT = {".pdf": "application/pdf"}

_MIN_HOST_INTERVAL = 1.0  # seconds between requests to the same host — be a good citizen
_TIMEOUT = 15  # seconds
_UNSAFE_FILENAME_RE = re.compile(r"[^-\w.]")


class AssetFetcher:
    """Downloads externally-hosted OLX assets into a local temp dir. Rate-limited per host
    and de-duplicated by URL within the fetcher's lifetime (one per conversion run)."""

    def __init__(self, dest_dir: Path) -> None:
        self.dest_dir = dest_dir
        self._session = requests.Session()
        self._cache: dict[str, Path | None] = {}
        self._last_request_at: dict[str, float] = {}

    def fetch(self, url: str) -> Path | None:
        """Return a local Path for url, or None if it's not fetchable / the fetch failed.
        Safe to call repeatedly with the same url — only hits the network once."""
        if url not in self._cache:
            self._cache[url] = self._fetch_uncached(url)
        return self._cache[url]

    def _fetch_uncached(self, url: str) -> Path | None:
        ext = Path(urlparse(url).path).suffix.lower()
        if ext not in FETCHABLE_EXTENSIONS:
            return None

        self._throttle(urlparse(url).netloc)
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
                url, content_type or "<none>", _CONTENT_TYPE_BY_EXT[ext],
            )
            return None

        name = _safe_filename(url)
        path = self.dest_dir / name
        path.write_bytes(resp.content)
        log.info("DOWNLOAD: Fetched external asset '%s' -> %s", url, name)
        return path

    def _throttle(self, host: str) -> None:
        wait = _MIN_HOST_INTERVAL - (time.monotonic() - self._last_request_at.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        self._last_request_at[host] = time.monotonic()


def _safe_filename(url: str) -> str:
    return _UNSAFE_FILENAME_RE.sub("_", resolve_asset_name(url))
