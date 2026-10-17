from pathlib import Path

import pytest

from ocw.converter import MBZBuilder
from ocw.fetcher import AssetFetcher
from ocw.parser.olx import Course
from tests.real_courses.url_audit import audit_mbz, report

# One course per known URL shape: edX prose links, DelftX PDFs + widget css, edX upgrade button,
# Studio editor attributes, heavy delftxdownloads use.
OLX_COURSES = ("AIfE4x", "MDRP1x", "IIES01x", "MECH3x", "PUP01x")

OLX_ROOTS = [
    pytest.param(
        root,
        id=root.parent.name.split()[1],
        marks=[] if any((root / "chapter").glob("*.xml")) else pytest.mark.skip(
            reason="empty export: no chapter XML, re-export from Studio"
        ),
    )
    for root in sorted((Path(__file__).parents[2] / "files" / "OLX").glob("*/course"))
    if root.parent.name.split()[1] in OLX_COURSES
]

pytestmark = pytest.mark.real_courses


@pytest.mark.parametrize("root", OLX_ROOTS)
def test_olx_course_only_widget_and_video_urls(root, tmp_path, asset_cache):
    course = Course(root, fetcher=AssetFetcher(asset_cache))
    course.parse()
    hits = []
    for authora in (True, False):
        out = tmp_path / f"course_{authora}.mbz"
        MBZBuilder(course, authora=authora).build(out)
        hits += audit_mbz(out)
        out.unlink()
    assert not hits, report(sorted(set(hits), key=lambda h: (h.member, h.url)))
