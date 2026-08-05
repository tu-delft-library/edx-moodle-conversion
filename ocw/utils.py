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


_CC_TOKEN_RE = re.compile(r"\b(BY|SA|NC|ND)\b", re.IGNORECASE)
_CC_PRIORITY = ["by", "nc", "nd", "sa"]


def normalise_license(raw: str) -> str:
    """
    Map an edX `license` attribute to a Wikiwijs Gebruiksrecht dropdown value.
    """
    raw = raw.strip()
    if not raw or raw.lower() == "all-rights-reserved":
        return "alle rechten voorbehouden"
    if not raw.lower().startswith("creative-commons"):
        return "alle rechten voorbehouden"
    tokens = {m.group(1).lower() for m in _CC_TOKEN_RE.finditer(raw)}
    ordered = [t for t in _CC_PRIORITY if t in tokens]
    return f"cc-{'-'.join(ordered)}" if ordered else "cc0"
