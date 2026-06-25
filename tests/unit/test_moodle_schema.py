import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from ocw.converter import MBZBuilder
from ocw.parser import Course
from tests.builders import Chapter, HtmlComponent, OLXFixtureBuilder, Sequential, Vertical

REFERENCE = Path(__file__).parent.parent / "fixtures" / "reference_mbz"
MINIMAL = Path(__file__).parent.parent / "fixtures" / "minimal"
PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
    b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)


def _xml_from_tar(tar, path: str) -> ET.Element:
    return ET.parse(tar.extractfile(path)).getroot()


def _assert_fields_match(gen_el: ET.Element, ref_el: ET.Element, path: str = "") -> None:
    """Assert every tag in ref_el exists as a direct child of gen_el (recursive, no value check)."""
    for child in ref_el:
        gen_child = gen_el.find(child.tag)
        assert gen_child is not None, f"<{child.tag}> missing under {path or gen_el.tag}"
        _assert_fields_match(gen_child, child, f"{path}/{child.tag}")


@pytest.fixture(scope="module")
def minimal_mbz(tmp_path_factory):
    out = tmp_path_factory.mktemp("mbz") / "out.mbz"
    course = Course(MINIMAL)
    course.parse()
    MBZBuilder(course).build(out)
    return out


@pytest.fixture(scope="module")
def file_page_mbz(tmp_path_factory):
    root = tmp_path_factory.mktemp("fp")
    b = OLXFixtureBuilder(root / "course")
    b.chapters = [Chapter("ch1", "Ch 1", [Sequential("s1", "S1", [Vertical("v1", "V1", [
        HtmlComponent("pg1", "Page 1", content='<img src="/static/test.png"/>'),
    ])])])]
    b.static_files = {"test.png": PNG}
    course = Course(b.build())
    course.parse()
    out = root / "out.mbz"
    MBZBuilder(course).build(out)
    return out


# --- Category A: reference schema diff ---

def test_course_xml_schema(minimal_mbz):
    ref = ET.parse(REFERENCE / "course" / "course.xml").getroot()
    with tarfile.open(minimal_mbz) as tar:
        gen = _xml_from_tar(tar, "course/course.xml")
    _assert_fields_match(gen, ref)


def test_section_xml_schema(minimal_mbz):
    ref = ET.parse(REFERENCE / "sections" / "section_1" / "section.xml").getroot()
    with tarfile.open(minimal_mbz) as tar:
        sec_path = next(n for n in tar.getnames() if n.endswith("section.xml"))
        gen = _xml_from_tar(tar, sec_path)
    _assert_fields_match(gen, ref)


def test_page_xml_schema(minimal_mbz):
    ref = ET.parse(REFERENCE / "activities" / "page_1" / "page.xml").getroot()
    with tarfile.open(minimal_mbz) as tar:
        page_path = next(n for n in tar.getnames() if n.endswith("page.xml"))
        gen = _xml_from_tar(tar, page_path)
    _assert_fields_match(gen, ref)


def test_module_xml_schema(minimal_mbz):
    ref = ET.parse(REFERENCE / "activities" / "page_1" / "module.xml").getroot()
    with tarfile.open(minimal_mbz) as tar:
        mod_path = next(n for n in tar.getnames() if n.endswith("module.xml"))
        gen = _xml_from_tar(tar, mod_path)
    _assert_fields_match(gen, ref)


@pytest.mark.xfail(strict=True, reason="stub emits <roles/>; reference requires <role_overrides> and <role_assignments>")
def test_activity_roles_xml_schema(minimal_mbz):
    ref = ET.parse(REFERENCE / "activities" / "page_1" / "roles.xml").getroot()
    with tarfile.open(minimal_mbz) as tar:
        path = next(n for n in tar.getnames() if "activities/" in n and n.endswith("roles.xml"))
        gen = _xml_from_tar(tar, path)
    _assert_fields_match(gen, ref)


@pytest.mark.xfail(strict=True, reason="stub emits <filters/>; reference requires <filter_actives> and <filter_configs>")
def test_activity_filters_xml_schema(minimal_mbz):
    ref = ET.parse(REFERENCE / "activities" / "page_1" / "filters.xml").getroot()
    with tarfile.open(minimal_mbz) as tar:
        path = next(n for n in tar.getnames() if "activities/" in n and n.endswith("filters.xml"))
        gen = _xml_from_tar(tar, path)
    _assert_fields_match(gen, ref)


@pytest.mark.xfail(strict=True, reason="stub emits <activity_gradebook/>; reference requires <grade_items> and <grade_letters>")
def test_activity_grades_xml_schema(minimal_mbz):
    ref = ET.parse(REFERENCE / "activities" / "page_1" / "grades.xml").getroot()
    with tarfile.open(minimal_mbz) as tar:
        path = next(n for n in tar.getnames() if "activities/" in n and n.endswith("grades.xml"))
        gen = _xml_from_tar(tar, path)
    _assert_fields_match(gen, ref)


@pytest.mark.xfail(strict=True, reason="stub emits <grade_history/>; reference requires <grade_grades>")
def test_activity_grade_history_xml_schema(minimal_mbz):
    ref = ET.parse(REFERENCE / "activities" / "page_1" / "grade_history.xml").getroot()
    with tarfile.open(minimal_mbz) as tar:
        path = next(n for n in tar.getnames() if "activities/" in n and n.endswith("grade_history.xml"))
        gen = _xml_from_tar(tar, path)
    _assert_fields_match(gen, ref)


def test_files_xml_schema(file_page_mbz):
    ref_file_el = ET.parse(REFERENCE / "files.xml").getroot().find("file")
    with tarfile.open(file_page_mbz) as tar:
        files_root = _xml_from_tar(tar, "files.xml")
    gen_file_el = files_root.find("file")
    assert gen_file_el is not None, "no <file> entries in files.xml"
    _assert_fields_match(gen_file_el, ref_file_el)


# --- Category B: semantic / cross-file integrity ---

def test_contextid_matches_page_ctx(file_page_mbz):
    with tarfile.open(file_page_mbz) as tar:
        files_root = _xml_from_tar(tar, "files.xml")
        page_ctx_ids = {
            ET.parse(tar.extractfile(m)).getroot().get("contextid")
            for m in tar.getmembers() if m.name.endswith("page.xml")
        }
    for f in files_root.findall("file"):
        ctx = f.findtext("contextid")
        assert ctx != "1", "contextid must not be site context (1)"
        assert ctx in page_ctx_ids, f"file contextid {ctx} has no matching page activity"


def test_inforef_lists_file_ids(file_page_mbz):
    with tarfile.open(file_page_mbz) as tar:
        files_root = _xml_from_tar(tar, "files.xml")
        all_file_ids = {f.get("id") for f in files_root.findall("file")}
        inforef_members = [m for m in tar.getmembers() if "activities/" in m.name and m.name.endswith("inforef.xml")]
        filerefs_found = False
        for m in inforef_members:
            root = ET.parse(tar.extractfile(m)).getroot()
            for fid_el in root.findall(".//fileref/file/id"):
                filerefs_found = True
                assert fid_el.text in all_file_ids, f"inforef references unknown file id {fid_el.text}"
    assert filerefs_found, "expected at least one activity inforef.xml with <fileref> entries"


def test_inforef_empty_when_no_files(minimal_mbz):
    with tarfile.open(minimal_mbz) as tar:
        for m in tar.getmembers():
            if "activities/" in m.name and m.name.endswith("inforef.xml"):
                root = ET.parse(tar.extractfile(m)).getroot()
                assert root.find("fileref") is None, f"{m.name} unexpectedly has <fileref>"
