import logging
import zipfile

import pytest

from ocw.converter.zip_builder import ZipBuilder
from ocw.zip_checks import log_zip_checks, run_zip_checks
from tests.unit.test_zip_builder import _site


@pytest.fixture
def built(tmp_path):
    course = _site().course(keep_all_content=True)
    course.parse()
    out = tmp_path / "course.zip"
    ZipBuilder(course).build(out)
    return course, out


def _without_first_content_page(src, dst) -> None:
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        dropped = False
        for name in zin.namelist():
            is_content = name.endswith(".html") and not name.endswith("index.html")
            if is_content and not dropped:
                dropped = True
                continue
            zout.writestr(name, zin.read(name))


def test_matching_zip_passes(built):
    course, out = built
    results = run_zip_checks(course, out)
    assert results[0].expected > 0
    assert all(r.passed for r in results)


def test_missing_page_fails(built, tmp_path):
    course, out = built
    broken = tmp_path / "broken.zip"
    _without_first_content_page(out, broken)
    result = run_zip_checks(course, broken)[0]
    assert result.actual == result.expected - 1
    assert not result.passed


def test_failed_check_logs_warning(built, tmp_path, caplog):
    course, out = built
    broken = tmp_path / "broken.zip"
    _without_first_content_page(out, broken)
    with caplog.at_level(logging.INFO):
        log_zip_checks(course, broken, logging.getLogger("ocw.zip_checks"))
    assert any(r.levelno == logging.WARNING and "FAIL" in r.getMessage() for r in caplog.records)
