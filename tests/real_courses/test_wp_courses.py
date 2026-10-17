import pytest

from ocw.converter import MBZBuilder
from ocw.fetcher import AssetFetcher
from ocw.parser.wp import WPCourse
from ocw.url_audit import audit_mbz, report

pytestmark = pytest.mark.real_courses


def test_wp_course_only_widget_and_video_urls(url, tmp_path, asset_cache):
    course = WPCourse(url, fetcher=AssetFetcher(asset_cache))
    course.parse()
    hits = []
    for authora in (True, False):
        out = tmp_path / f"course_{authora}.mbz"
        MBZBuilder(course, authora=authora).build(out)
        hits += audit_mbz(out)
        out.unlink()
    assert not hits, report(sorted(set(hits), key=lambda h: (h.member, h.url)))