import tarfile
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

