import hashlib
import re
from pathlib import Path


class _Counter:
    def __init__(self, start=100):
        self._n = start

    def next(self) -> int:
        v = self._n
        self._n += 1
        return v


def esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def sha1_of(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def rewrite_static_urls(html: str) -> str:
    return re.sub(r'/static/([^"\'>\s]+)', r'@@PLUGINFILE@@/\1', html)
