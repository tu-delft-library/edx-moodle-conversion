import logging
import tarfile
from xml.etree import ElementTree as ET

from tests.builders import Chapter, HtmlComponent, OLXFixtureBuilder, Sequential, Vertical, VideoComponent
from ocw.converter import MBZBuilder
from ocw.parser.olx import Course
from ocw.utils import esc


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
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1",
                    "S1",
                    [
                        Vertical(
                            "v1",
                            "V1",
                            [
                                HtmlComponent(
                                    "pg1",
                                    "Page 1",
                                    content='<img src="/static/test.png"/>',
                                )
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    b.static_files = {"test.png": png}
    course = Course(b.build())
    course.parse()
    out = tmp_path / "out.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        page_xml = next(
            tar.extractfile(m).read().decode()
            for m in tar.getmembers()
            if m.name.endswith("page.xml")
        )
        names = tar.getnames()
    assert "@@PLUGINFILE@@/test.png" in page_xml
    assert any("files/" in n for n in names)


# CC4
def test_cc4_video_shortcode_and_vidrouter_block(tmp_path):
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1",
                    "S1",
                    [
                        Vertical(
                            "v1",
                            "V1",
                            [
                                HtmlComponent("pg1", "Page 1", content="<p>intro</p>"),
                                VideoComponent(
                                    "vid1",
                                    "Video 1",
                                    youtube_id="_tX7iFAJvZY",
                                    edx_video_id="d54b76a4-c214-49ea-a4da-161e7f8520a3",
                                ),
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    course = Course(b.build())
    course.parse()
    out = tmp_path / "out.mbz"
    MBZBuilder(course).build(out)

    with tarfile.open(out) as tar:
        course_xml = ET.parse(tar.extractfile("course/course.xml")).getroot()
        page_xml = next(
            tar.extractfile(m).read().decode()
            for m in tar.getmembers()
            if m.name.endswith("page.xml")
        )

    videos = course_xml.findall(".//plugin_local_vidrouter_course/video")
    assert len(videos) == len(course.videos) == 1
    assert videos[0].findtext("vidkey") == "d54b76a4-c214-49ea-a4da-161e7f8520a3"

    assert esc("<p>intro</p>") in page_xml
    assert "[[vid:d54b76a4-c214-49ea-a4da-161e7f8520a3]]" in page_xml
    assert page_xml.index("intro") < page_xml.index("[[vid:")


# SK1
def test_sk1_unsupported_silently_skipped(tmp_path):
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1", "S1", [Vertical("v1", "V1", [HtmlComponent("pg1", "Page 1")])]
                )
            ],
        )
    ]
    root = b.build()
    v_path = root / "vertical" / "v1.xml"
    v_path.write_text(
        v_path.read_text(encoding="utf-8").replace(
            "</vertical>", '<problem url_name="prob1"/>\n</vertical>'
        ),
        encoding="utf-8",
    )
    course = Course(root)
    course.parse()
    total = sum(
        len(v["components"])
        for ch in course.chapters
        for s in ch["sequentials"]
        for v in s["verticals"]
    )
    assert total == 1


# C1
def test_c1_warns_missing_static(tmp_path, caplog):
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1",
                    "S1",
                    [
                        Vertical(
                            "v1",
                            "V1",
                            [
                                HtmlComponent(
                                    "pg1",
                                    "Page 1",
                                    content='<img src="/static/missing.png"/>',
                                )
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    b.build()
    with caplog.at_level(logging.WARNING, logger="ocw.parser"):
        Course(tmp_path / "course").parse()
    assert any("missing.png" in r.message for r in caplog.records)


# C3
def test_c3_warns_missing_asset_v1_reference(tmp_path, caplog):
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1",
                    "S1",
                    [
                        Vertical(
                            "v1",
                            "V1",
                            [
                                HtmlComponent(
                                    "pg1",
                                    "Page 1",
                                    content=(
                                        '<img src="asset-v1:Org+Course+Run+type@asset'
                                        '+block@missing.png"/>'
                                    ),
                                )
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    b.build()
    with caplog.at_level(logging.WARNING, logger="ocw.parser"):
        Course(tmp_path / "course").parse()
    assert any("missing.png" in r.message for r in caplog.records)


# CC5
def test_cc5_course_image_and_banner_in_overviewfiles(tmp_path):
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [
        Chapter("ch1", "Ch 1", [Sequential("s1", "S1", [Vertical("v1", "V1", [])])])
    ]
    b.static_files = {"course_image.jpg": png, "banner.png": png}
    b.course_image = "course_image.jpg"
    b.banner_image = "/static/banner.png"
    course = Course(b.build())
    course.parse()
    assert course.course_image_path == course.static_files["course_image.jpg"]
    assert course.banner_image_path == course.static_files["banner.png"]

    out = tmp_path / "out.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        files_xml = next(
            tar.extractfile(m).read().decode()
            for m in tar.getmembers()
            if m.name == "files.xml"
        ).encode()
        root = ET.fromstring(files_xml)

    overview_files = {
        f.findtext("filename"): f
        for f in root.findall("file")
        if f.findtext("component") == "course"
        and f.findtext("filearea") == "overviewfiles"
    }
    assert set(overview_files) == {"course_image.jpg", "banner.png"}
    ctxids = {f.findtext("contextid") for f in overview_files.values()}
    assert len(ctxids) == 1
    assert next(iter(ctxids)) != "1"
    for f in overview_files.values():
        assert f.findtext("itemid") == "0"
    assert overview_files["course_image.jpg"].findtext("sortorder") == "0"
    assert overview_files["banner.png"].findtext("sortorder") == "1"


# CC5
def test_cc5_no_course_image_declared_emits_no_overviewfiles(minimal_fixture, tmp_path):
    course = Course(minimal_fixture)
    course.parse()
    assert course.course_image_path is None
    assert course.banner_image_path is None

    out = tmp_path / "out.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        files_xml = next(
            tar.extractfile(m).read().decode()
            for m in tar.getmembers()
            if m.name == "files.xml"
        ).encode()
        root = ET.fromstring(files_xml)

    assert not [
        f for f in root.findall("file") if f.findtext("component") == "course"
    ]


# CC5
def test_cc5_warns_missing_course_image(tmp_path, caplog):
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [
        Chapter("ch1", "Ch 1", [Sequential("s1", "S1", [Vertical("v1", "V1", [])])])
    ]
    b.course_image = "missing.jpg"
    b.build()
    with caplog.at_level(logging.WARNING, logger="ocw.parser"):
        course = Course(tmp_path / "course")
        course.parse()
    assert course.course_image_path is None
    assert any("missing.jpg" in r.message for r in caplog.records)
