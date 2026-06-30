import hashlib
import re
from pathlib import Path


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


def rewrite_static_urls(html: str) -> str:
    """Replace /static/<name> with @@PLUGINFILE@@/<name> for Moodle file embedding."""
    return re.sub(r'/static/([^"\'>\s]+)', r"@@PLUGINFILE@@/\1", html)
