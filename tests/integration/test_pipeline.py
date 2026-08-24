import re
import tarfile
from xml.etree import ElementTree as ET

from ocw.converter import MBZBuilder
from ocw.parser.olx import Course
from tests.builders import Chapter, HtmlComponent, OLXFixtureBuilder, Sequential, StaticTab, Vertical


# INFO: Check constructor works and generated path is valid
def test_olxcourse_instantiates(minimal_fixture):
    course = Course(minimal_fixture)
    assert course.root == minimal_fixture


# INFO: Check that the MBZBuilder's constructor works
def test_mbzbuilder_instantiates(minimal_fixture):
    course = Course(minimal_fixture)
    builder = MBZBuilder(course)
    assert builder.course is course


# INFO: Check if builder adds all XML elements
def test_fixture_builder_writes_files(simple_course):
    assert (simple_course / "course" / "course.xml").exists()
    assert (simple_course / "html" / "page1.html").exists()
    assert (simple_course / "video" / "vid1.xml").exists()


# INFO: Output as tar
def test_fixture_builder_as_tar(olx_builder):
    olx_builder.build()
    tar_path = olx_builder.as_tar()
    assert tarfile.is_tarfile(tar_path)


# ── F: cross-file integrity ───────────────────────────────────────────────────


def _build_minimal(tmp_path, minimal_fixture):
    out = tmp_path / "course.mbz"
    course = Course(minimal_fixture)
    course.parse()
    MBZBuilder(course).build(out)
    return out


def test_section_sequence_ids_have_activity_dirs(minimal_fixture, tmp_path):
    out = _build_minimal(tmp_path, minimal_fixture)
    with tarfile.open(out) as tar:
        names = set(tar.getnames())
        section_paths = [
            n for n in names if re.match(r"sections/section_\d+/section\.xml", n)
        ]
        for path in section_paths:
            seq = ET.parse(tar.extractfile(path)).getroot().findtext("sequence") or ""
            for mod_id in filter(None, (s.strip() for s in seq.split(","))):
                assert any(
                    n.startswith(f"activities/page_{mod_id}/") or n.startswith(f"activities/subsection_{mod_id}/")
                    for n in names
                ), f"section sequence references mod {mod_id} but no matching activity dir"


def test_module_sectionid_is_real_section(minimal_fixture, tmp_path):
    out = _build_minimal(tmp_path, minimal_fixture)
    with tarfile.open(out) as tar:
        names = set(tar.getnames())
        section_ids = {
            re.search(r"section_(\d+)", n).group(1)
            for n in names
            if re.match(r"sections/section_\d+/section\.xml", n)
        }
        for path in [
            n for n in names if re.match(r"activities/page_\d+/module\.xml", n)
        ]:
            sec_id = ET.parse(tar.extractfile(path)).getroot().findtext("sectionid")
            assert sec_id in section_ids, (
                f"{path}: sectionid={sec_id} has no matching section dir"
            )


def test_backup_manifest_activity_dirs_exist(minimal_fixture, tmp_path):
    out = _build_minimal(tmp_path, minimal_fixture)
    with tarfile.open(out) as tar:
        names = set(tar.getnames())
        backup = ET.parse(tar.extractfile("moodle_backup.xml")).getroot()
    for activity in backup.findall(".//contents/activities/activity"):
        d = activity.findtext("directory")
        assert any(n.startswith(d + "/") for n in names), (
            f"moodle_backup.xml lists '{d}' but dir doesn't exist"
        )


def test_backup_manifest_section_dirs_exist(minimal_fixture, tmp_path):
    out = _build_minimal(tmp_path, minimal_fixture)
    with tarfile.open(out) as tar:
        names = set(tar.getnames())
        backup = ET.parse(tar.extractfile("moodle_backup.xml")).getroot()
    for section in backup.findall(".//contents/sections/section"):
        d = section.findtext("directory")
        assert any(n.startswith(d + "/") for n in names), (
            f"moodle_backup.xml lists '{d}' but dir doesn't exist"
        )

_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00'
    b'\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)


def test_syllabus_static_ref_rewritten_and_linked(tmp_path):
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [Chapter("ch1", "Ch 1", [Sequential("s1", "S1", [Vertical("v1", "V1", [
        HtmlComponent("pg1", "Page 1"),
    ])])])]
    b.static_tabs = [StaticTab("Syllabus", "syllabus-slug")]
    b.tabs_files = {"syllabus-slug": '<img src="/static/syllabus.png"/>'}
    b.static_files = {"syllabus.png": _PNG}
    course = Course(b.build())
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)

    with tarfile.open(out) as tar:
        names = set(tar.getnames())
        overview_page = next(
            n for n in names
            if re.match(r"activities/page_\d+/page\.xml", n)
            and "syllabus.png" in tar.extractfile(n).read().decode()
        )
        page_xml = ET.parse(tar.extractfile(overview_page)).getroot().find("page")
        assert "@@PLUGINFILE@@/syllabus.png" in page_xml.findtext("content")

        files_xml = ET.parse(tar.extractfile("files.xml")).getroot()
        file_entry = next(f for f in files_xml.findall("file") if f.findtext("filename") == "syllabus.png")
        sha1 = file_entry.findtext("contenthash")
        assert f"files/{sha1[:2]}/{sha1}" in names
