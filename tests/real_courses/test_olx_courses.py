import pytest

from ocw.converter import MBZBuilder
from ocw.fetcher import AssetFetcher
from ocw.parser.olx import Course
from ocw.url_audit import audit_mbz, report
from tests.real_courses.courses import KNOWN_HITS, course_id

pytestmark = pytest.mark.real_courses


def test_olx_course_only_widget_and_video_urls(root, tmp_path, asset_cache):
    course = Course(root, fetcher=AssetFetcher(asset_cache))
    course.parse()
    known = KNOWN_HITS.get(course_id(root), set())
    hits = []
    for authora in (True, False):
        out = tmp_path / f"course_{authora}.mbz"
        MBZBuilder(course, authora=authora).build(out)
        hits += [h for h in audit_mbz(out) if h.url not in known]
        out.unlink()
    assert not hits, report(sorted(set(hits), key=lambda h: (h.member, h.url)))
