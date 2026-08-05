import hashlib
import logging
import re
import subprocess
from pathlib import Path

log = logging.getLogger("ocw.converter")


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


def warn_external_edx_urls(html: str, context: str = "") -> None:
    """Warn on any absolute URL still pointing at edX-hosted infrastructure."""
    for match in _EDX_HOST_RE.findall(html):
        log.warning(
            "Content still hosted on edX%s: '%s'",
            f" on page '{context}'" if context else "",
            match,
        )


_CC_TOKEN_RE = re.compile(r"\b(BY|SA|NC|ND)\b", re.IGNORECASE)
_CC_PRIORITY = ["by", "nc", "nd", "sa"]


def run_hybrid_checks(olx_path: Path, mbz_path: Path) -> None:
    """Run the OLX<->MBZ hybrid integration checks and route their output
    through logging. A bare subprocess.run() inherits stdout/stderr straight
    to the terminal, bypassing logging entirely — neither the CLI's ocw.log
    file handler nor the GUI's log box ever see it that way.
    """
    result = subprocess.run(
        [
            "poetry",
            "run",
            "pytest",
            "tests/integration/test_hybrid_checks.py",
            "--olx-path",
            str(olx_path),
            "--mbz-path",
            str(mbz_path),
            "-v",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    level = logging.INFO if result.returncode == 0 else logging.WARNING
    for line in (result.stdout + result.stderr).splitlines():
        log.log(level, line)


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
