import pytest

from ocw.converter.zip_builder import ZipBuilder
from ocw.fetcher import AssetFetcher
from ocw.parser.wp import WPCourse
from ocw.url_audit import audit_zip, report

pytestmark = pytest.mark.real_courses


def test_wp_zip_has_no_ocw_leftovers_or_broken_links(url, tmp_path, asset_cache):
    course = WPCourse(url, fetcher=AssetFetcher(asset_cache), keep_all_content=True)
    course.parse()
    out = tmp_path / "course.zip"
    ZipBuilder(course).build(out)
    hits = audit_zip(out)
    out.unlink()
    assert not hits, report(sorted(set(hits), key=lambda h: (h.member, h.url)))
