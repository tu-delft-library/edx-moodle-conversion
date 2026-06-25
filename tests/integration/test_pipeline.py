import re
import tarfile
from xml.etree import ElementTree as ET

import pytest

from ocw.converter import MBZBuilder
from ocw.parser import Course


#INFO: Check constructor works and generated path is valid 
def test_olxcourse_instantiates(minimal_fixture):
    course = Course(minimal_fixture)
    assert course.root == minimal_fixture

#INFO: Check that the MBZBuilder's constructor works 
def test_mbzbuilder_instantiates(minimal_fixture):
    course = Course(minimal_fixture)
    builder = MBZBuilder(course)
    assert builder.course is course


#INFO: Check if builder adds all XML elements
def test_fixture_builder_writes_files(simple_course):
    assert (simple_course / "course" / "course.xml").exists()
    assert (simple_course / "html" / "page1.html").exists()
    assert (simple_course / "video" / "vid1.xml").exists()

#INFO: Output as tar
def test_fixture_builder_as_tar(olx_builder):
    olx_builder.build()
    tar_path = olx_builder.as_tar()
    assert tarfile.is_tarfile(tar_path)


#TODO: The following which are tests that specifically test the requirments should be composed in their own file 

# CC1
def test_cc1_structure_mapped(minimal_fixture):
    course = Course(minimal_fixture)
    course.parse()
    assert course.course_name == "Minimal Course"
    assert course.course_id == "MIN101"
    assert len(course.chapters) == 1
    assert course.chapters[0]["display_name"] == "Week 1"

# CC2
def test_cc2_html_content_in_mbz(minimal_fixture, tmp_path):
    course = Course(minimal_fixture)
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        names = tar.getnames()
    assert "moodle_backup.xml" in names
    assert any("page_" in n for n in names)

# CC3
def test_cc3_image_rewrite_and_present(tmp_path):
    from tests.builders import OLXFixtureBuilder, Chapter, Sequential, Vertical, HtmlComponent
    png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [Chapter("ch1", "Ch 1", [Sequential("s1", "S1", [Vertical("v1", "V1", [
        HtmlComponent("pg1", "Page 1", content='<img src="/static/test.png"/>')
    ])])])]
    b.static_files = {"test.png": png}
    course = Course(b.build())
    course.parse()
    out = tmp_path / "out.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        page_xml = next(
            tar.extractfile(m).read().decode()
            for m in tar.getmembers() if m.name.endswith("page.xml")
        )
        names = tar.getnames()
    assert "@@PLUGINFILE@@/test.png" in page_xml
    assert any("files/" in n for n in names)

# SK1
def test_sk1_unsupported_silently_skipped(tmp_path):
    from tests.builders import OLXFixtureBuilder, Chapter, Sequential, Vertical, HtmlComponent
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [Chapter("ch1", "Ch 1", [Sequential("s1", "S1", [
        Vertical("v1", "V1", [HtmlComponent("pg1", "Page 1")])
    ])])]
    root = b.build()
    v_path = root / "vertical" / "v1.xml"
    v_path.write_text(
        v_path.read_text(encoding="utf-8").replace("</vertical>", '<problem url_name="prob1"/>\n</vertical>'),
        encoding="utf-8"
    )
    course = Course(root)
    course.parse()
    total = sum(len(v["components"]) for ch in course.chapters for s in ch["sequentials"] for v in s["verticals"])
    assert total == 1

# C1
def test_c1_warns_missing_static(tmp_path, caplog):
    import logging
    from tests.builders import OLXFixtureBuilder, Chapter, Sequential, Vertical, HtmlComponent
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [Chapter("ch1", "Ch 1", [Sequential("s1", "S1", [Vertical("v1", "V1", [
        HtmlComponent("pg1", "Page 1", content='<img src="/static/missing.png"/>')
    ])])])]
    b.build()
    with caplog.at_level(logging.WARNING, logger="ocw.parser"):
        Course(tmp_path / "course").parse()
    assert any("C1" in r.message and "missing.png" in r.message for r in caplog.records)

# Script 2
def test_script2_unit_count_parity(minimal_fixture, tmp_path):
    course = Course(minimal_fixture)
    course.parse()
    olx_count = sum(
        len(vert["components"])
        for ch in course.chapters
        for seq in ch["sequentials"]
        for vert in seq["verticals"]
    )
    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        page_count = sum(1 for m in tar.getmembers() if m.name.endswith("page.xml"))
    assert page_count == olx_count


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
        section_paths = [n for n in names if re.match(r"sections/section_\d+/section\.xml", n)]
        for path in section_paths:
            seq = ET.parse(tar.extractfile(path)).getroot().findtext("sequence") or ""
            for mod_id in filter(None, (s.strip() for s in seq.split(","))):
                assert any(n.startswith(f"activities/page_{mod_id}/") for n in names), \
                    f"section sequence references page_{mod_id} but no matching activity dir"


def test_module_sectionid_is_real_section(minimal_fixture, tmp_path):
    out = _build_minimal(tmp_path, minimal_fixture)
    with tarfile.open(out) as tar:
        names = set(tar.getnames())
        section_ids = {
            re.search(r"section_(\d+)", n).group(1)
            for n in names if re.match(r"sections/section_\d+/section\.xml", n)
        }
        for path in [n for n in names if re.match(r"activities/page_\d+/module\.xml", n)]:
            sec_id = ET.parse(tar.extractfile(path)).getroot().findtext("sectionid")
            assert sec_id in section_ids, f"{path}: sectionid={sec_id} has no matching section dir"


def test_backup_manifest_activity_dirs_exist(minimal_fixture, tmp_path):
    out = _build_minimal(tmp_path, minimal_fixture)
    with tarfile.open(out) as tar:
        names = set(tar.getnames())
        backup = ET.parse(tar.extractfile("moodle_backup.xml")).getroot()
    for activity in backup.findall(".//contents/activities/activity"):
        d = activity.findtext("directory")
        assert any(n.startswith(d + "/") for n in names), \
            f"moodle_backup.xml lists '{d}' but dir doesn't exist"


def test_backup_manifest_section_dirs_exist(minimal_fixture, tmp_path):
    out = _build_minimal(tmp_path, minimal_fixture)
    with tarfile.open(out) as tar:
        names = set(tar.getnames())
        backup = ET.parse(tar.extractfile("moodle_backup.xml")).getroot()
    for section in backup.findall(".//contents/sections/section"):
        d = section.findtext("directory")
        assert any(n.startswith(d + "/") for n in names), \
            f"moodle_backup.xml lists '{d}' but dir doesn't exist"

