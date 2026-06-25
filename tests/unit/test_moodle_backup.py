import tarfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from ocw.converter import MBZBuilder
from ocw.parser import Course
from tests.builders import Chapter, HtmlComponent, OLXFixtureBuilder, Sequential, Vertical

MINIMAL = Path(__file__).parent.parent / "fixtures" / "minimal"


def _get_backup_xml(tmp_path) -> ET.Element:
    course = Course(MINIMAL)
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        return ET.parse(tar.extractfile("moodle_backup.xml")).getroot()


def test_details_block_present(tmp_path):
    detail = _get_backup_xml(tmp_path).find(".//details/detail")
    assert detail is not None
    assert detail.findtext("type") == "course"
    assert detail.findtext("format") == "moodle2"


def test_required_metadata_fields(tmp_path):
    info = _get_backup_xml(tmp_path).find("information")
    for field in (
        "moodle_version", "backup_version", "backup_release", "backup_date",
        "original_course_format", "original_course_contextid", "original_system_contextid",
    ):
        assert info.findtext(field) is not None, f"missing {field}"


def test_root_settings_present(tmp_path):
    names = {s.findtext("name") for s in _get_backup_xml(tmp_path).findall(".//settings/setting")}
    for required in ("activities", "blocks", "users", "filters"):
        assert required in names


def test_section_settings_generated(tmp_path):
    section_settings = [
        s for s in _get_backup_xml(tmp_path).findall(".//settings/setting")
        if s.findtext("level") == "section"
    ]
    assert len(section_settings) > 0
    names = {s.findtext("name") for s in section_settings}
    assert any("_included" in n for n in names)
    assert any("_userinfo" in n for n in names)


def test_activity_settings_generated(tmp_path):
    activity_settings = [
        s for s in _get_backup_xml(tmp_path).findall(".//settings/setting")
        if s.findtext("level") == "activity"
    ]
    assert len(activity_settings) > 0
    names = {s.findtext("name") for s in activity_settings}
    assert any("page_" in n and "_included" in n for n in names)


def test_empty_course_still_valid(tmp_path):
    b = OLXFixtureBuilder(tmp_path / "course")
    course = Course(b.build())
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        xml = ET.parse(tar.extractfile("moodle_backup.xml")).getroot()
    assert xml.find(".//details/detail") is not None
    assert [s for s in xml.findall(".//settings/setting") if s.findtext("level") == "activity"] == []
