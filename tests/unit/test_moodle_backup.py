import re
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


# ── module-scoped fixtures ────────────────────────────────────────────────────

_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
    b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)


@pytest.fixture(scope="module")
def mbz(tmp_path_factory):
    out = tmp_path_factory.mktemp("bu") / "course.mbz"
    course = Course(MINIMAL)
    course.parse()
    MBZBuilder(course).build(out)
    return out


@pytest.fixture(scope="module")
def mbz_names(mbz):
    with tarfile.open(mbz) as tar:
        return set(tar.getnames())


@pytest.fixture(scope="module")
def file_mbz(tmp_path_factory):
    root = tmp_path_factory.mktemp("fmbz")
    b = OLXFixtureBuilder(root / "course")
    b.chapters = [Chapter("ch1", "Ch 1", [Sequential("s1", "S1", [Vertical("v1", "V1", [
        HtmlComponent("pg1", "Page 1", content='<img src="/static/test.png"/>'),
    ])])])]
    b.static_files = {"test.png": _PNG}
    course = Course(b.build())
    course.parse()
    out = root / "out.mbz"
    MBZBuilder(course).build(out)
    return out


def _parse(mbz_path, entry):
    with tarfile.open(mbz_path) as tar:
        return ET.parse(tar.extractfile(entry)).getroot()


# ── A: required file existence ────────────────────────────────────────────────

@pytest.mark.parametrize("path", [
    "moodle_backup.xml",
    "course/course.xml",
    pytest.param(
        "course/inforef.xml",
        marks=pytest.mark.xfail(strict=True, reason="course/inforef.xml not yet generated"),
    ),
    "roles.xml", "gradebook.xml", "grade_history.xml",
    "groups.xml", "outcomes.xml", "questions.xml", "scales.xml",
    "files.xml",
])
def test_required_root_file_exists(mbz_names, path):
    assert path in mbz_names


@pytest.mark.parametrize("filename", [
    "page.xml", "module.xml", "inforef.xml",
    "grades.xml", "grade_history.xml", "roles.xml", "filters.xml",
])
def test_activity_dir_has_file(mbz_names, filename):
    act_dirs = {n.rsplit("/", 1)[0] for n in mbz_names if re.match(r"activities/page_\d+/.+\.xml", n)}
    assert act_dirs, "no activity dirs found"
    for d in act_dirs:
        assert f"{d}/{filename}" in mbz_names


@pytest.mark.parametrize("filename", ["section.xml", "inforef.xml"])
def test_section_dir_has_file(mbz_names, filename):
    sec_dirs = {n.rsplit("/", 1)[0] for n in mbz_names if re.match(r"sections/section_\d+/.+\.xml", n)}
    assert sec_dirs, "no section dirs found"
    for d in sec_dirs:
        assert f"{d}/{filename}" in mbz_names


# ── B: XML field presence ─────────────────────────────────────────────────────

_SECTION_FIELDS = frozenset({
    "number", "name", "summary", "summaryformat",
    "sequence", "visible", "availabilityjson", "timemodified",
})
_MODULE_FIELDS = frozenset({
    "modulename", "sectionid", "sectionnumber", "idnumber", "added",
    "score", "indent", "visible", "visibleoncoursepage", "visibleold",
    "groupmode", "groupingid", "completion", "completiongradeitemnumber",
    "completionpassgrade", "completionview", "completionexpected",
    "availability", "showdescription", "tags",
})
_PAGE_FIELDS = frozenset({
    "name", "intro", "introformat", "content", "contentformat",
    "legacyfiles", "legacyfileslast", "display", "displayoptions",
    "revision", "timemodified",
})
_COURSE_FIELDS = frozenset({
    "shortname", "fullname", "idnumber", "summary", "summaryformat",
    "format", "showgrades", "newsitems", "startdate", "enddate",
    "marker", "maxbytes", "legacyfiles", "showreports", "visible",
    "groupmode", "groupmodeforce", "defaultgroupingid", "lang", "theme",
    "timecreated", "timemodified", "requested", "enablecompletion",
    "completionnotify", "hiddensections", "coursedisplay",
    "category", "tags", "customfields",
})


@pytest.mark.parametrize("pattern,fields,nested_under", [
    (r"sections/section_\d+/section\.xml", _SECTION_FIELDS, None),
    (r"activities/page_\d+/module\.xml",   _MODULE_FIELDS,  None),
    (r"activities/page_\d+/page\.xml",     _PAGE_FIELDS,    "page"),
])
def test_xml_required_fields_present(mbz, mbz_names, pattern, fields, nested_under):
    paths = [n for n in mbz_names if re.match(pattern, n)]
    assert paths
    for path in paths:
        root = _parse(mbz, path)
        el = root.find(nested_under) if nested_under else root
        missing = fields - {child.tag for child in el}
        assert not missing, f"{path} missing: {missing}"


def test_course_xml_required_fields(mbz):
    root = _parse(mbz, "course/course.xml")
    missing = _COURSE_FIELDS - {child.tag for child in root}
    assert not missing, f"course/course.xml missing: {missing}"


# ── C: semantic values ────────────────────────────────────────────────────────

def test_section_availabilityjson_null_sentinel(mbz, mbz_names):
    for path in [n for n in mbz_names if re.match(r"sections/section_\d+/section\.xml", n)]:
        assert _parse(mbz, path).findtext("availabilityjson") == "$@NULL@$"


def test_page_display_is_5(mbz, mbz_names):
    for path in [n for n in mbz_names if re.match(r"activities/page_\d+/page\.xml", n)]:
        assert _parse(mbz, path).find("page").findtext("display") == "5"


def test_page_displayoptions_exact_php(mbz, mbz_names):
    expected = 'a:1:{s:10:"printintro";s:1:"0";}'
    for path in [n for n in mbz_names if re.match(r"activities/page_\d+/page\.xml", n)]:
        val = _parse(mbz, path).find("page").findtext("displayoptions")
        assert val == expected, f"{path}: {val!r}"


def test_course_format_topics(mbz):
    assert _parse(mbz, "course/course.xml").findtext("format") == "topics"


# ── E: files.xml entry completeness ──────────────────────────────────────────

_FILES_REQUIRED_FIELDS = frozenset({
    "contenthash", "contextid", "component", "filearea", "itemid",
    "filepath", "filename", "userid", "filesize", "mimetype",
    "status", "timecreated", "timemodified", "sortorder",
    "repositorytype", "repositoryid", "reference",
    "source", "author", "license",
})


def test_files_xml_entry_has_required_fields(file_mbz):
    root = _parse(file_mbz, "files.xml")
    entries = root.findall("file")
    assert entries, "no <file> entries — test needs a course with a static file ref"
    for entry in entries:
        missing = _FILES_REQUIRED_FIELDS - {child.tag for child in entry}
        assert not missing, f"files.xml entry id={entry.get('id')} missing: {missing}"
