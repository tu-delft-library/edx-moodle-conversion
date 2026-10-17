
from pathlib import Path

import pytest

OLX_DIR = Path(__file__).parents[2] / "files" / "OLX"
WP_COURSES_TXT = Path(__file__).parent / "wp_courses.txt"

OLX_COURSES = ("AIfE4x", "MDRP1x", "IIES01x", "MECH3x", "PUP01x")

# Accepted leftovers, left for whoever fixes the course content.
KNOWN_HITS = {
    # <audio> source that 404s on delftxdownloads, kept so the missing podcast stays visible.
    "URED1x": {
        "https://delftxdownloads.tudelft.nl/URED1x_Urban_Ecology_Design/"
        "UEDNBS1x_Introducing_Urban_Ecology_Design_Podcast.mp3"
    },
    # edX catalog url typed as plain prose, never a link.
    "PDCE01x": {"https://www.edx.org/course/circular-economy-an-introduction"},
}


def course_id(root: Path) -> str:
    return root.parent.name.split()[1]


def olx_params(all_courses: bool) -> list:
    return [
        pytest.param(
            root,
            id=course_id(root),
            marks=[] if any((root / "chapter").glob("*.xml")) else pytest.mark.skip(
                reason="empty export: no chapter XML, re-export from Studio"
            ),
        )
        for root in sorted(OLX_DIR.glob("*/course"))
        if all_courses or course_id(root) in OLX_COURSES
    ]


def wp_params(all_courses: bool) -> list:
    """Uncommented lines of `wp_courses.txt`, plus the commented out `# https://` ones with
    `all_courses`."""
    urls = []
    for line in WP_COURSES_TXT.read_text().splitlines():
        line = line.strip()
        if all_courses and line.startswith("# https://"):
            line = line.removeprefix("# ")
        if line and not line.startswith("#"):
            urls.append(line)
    return [pytest.param(u, id=u.rstrip("/").rsplit("/", 1)[-1]) for u in urls]