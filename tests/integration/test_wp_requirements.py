import logging
import tarfile
from xml.etree import ElementTree as ET

from ocw.converter import MBZBuilder
from ocw.utils import esc
from tests.wp_builders import WPFixtureSite

SUBJECT_URL = "https://ocw.tudelft.nl/subjects/1-intro/"
LECTURE_URL = "https://ocw.tudelft.nl/course-lectures/lec1/"
READING_URL = "https://ocw.tudelft.nl/course-readings/read1/"


def _activities_html(*links: str) -> str:
    items = "\n".join(links)
    return f"""
    <ul class="activities">
    <li>
    <h4 class="expand expand--showing"><span class="icon fa-minus course-title">1.1 Basics</span></h4>
    <ul>{items}</ul>
    </li>
    </ul>
    """


# WP-CC1
def test_wp_cc1_structure_mapped():
    site = WPFixtureSite()
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>'
        ),
    )
    site.add_lecture_page(LECTURE_URL, "<p>content</p>")
    course = site.course()
    course.parse()

    assert course.course_name == "Example Course"
    assert len(course.chapters) == 1
    chapter = course.chapters[0]
    assert chapter["display_name"] == "1. Intro"
    assert len(chapter["sequentials"]) == 1
    sequential = chapter["sequentials"][0]
    assert sequential["display_name"] == "1.1 Basics"
    assert len(sequential["verticals"]) == 1
    assert sequential["verticals"][0]["display_name"] == "Lecture 1"


# WP-CC2
def test_wp_cc2_image_alignment_survives_into_mbz(tmp_path):
    site = WPFixtureSite()
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>'
        ),
    )
    site.add_lecture_page(LECTURE_URL, '<p><img class="alignleft" src="pic.png"/></p>')
    course = site.course()
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)

    with tarfile.open(out) as tar:
        page_xml = next(
            tar.extractfile(m).read().decode()
            for m in tar.getmembers()
            if m.name.endswith("page.xml")
        )
    assert esc("float:left;margin:0 1em 1em 0;") in page_xml


# WP-CC3
def test_wp_cc3_separator_becomes_hr(tmp_path):
    site = WPFixtureSite()
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>'
        ),
    )
    site.add_lecture_page(
        LECTURE_URL, '<p>before</p><div class="vc_separator"><span/></div><p>after</p>'
    )
    course = site.course()
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)

    with tarfile.open(out) as tar:
        page_xml = next(
            tar.extractfile(m).read().decode()
            for m in tar.getmembers()
            if m.name.endswith("page.xml")
        )
    assert esc("<hr/>") in page_xml


# WP-CC4
def test_wp_cc4_video_shortcode_and_vidrouter_block(tmp_path):
    site = WPFixtureSite()
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>'
        ),
    )
    site.add_lecture_page(
        LECTURE_URL, '<iframe src="https://www.youtube.com/embed/abc123"></iframe>'
    )
    course = site.course()
    course.parse()
    out = tmp_path / "course.mbz"
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
    assert videos[0].findtext("vidkey") == "lec1"
    assert "[[vid:lec1]]" in page_xml


# WP-CC5
def test_wp_cc5_multiple_videos_on_one_page_all_captured(tmp_path):
    site = WPFixtureSite()
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>'
        ),
    )
    site.add_lecture_page(
        LECTURE_URL,
        '<div class="vc_row">'
        '<iframe src="https://www.youtube.com/embed/abc123"></iframe>'
        '<iframe src="https://www.youtube.com/embed/def456"></iframe>'
        "</div>",
    )
    course = site.course()
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)

    with tarfile.open(out) as tar:
        course_xml = ET.parse(tar.extractfile("course/course.xml")).getroot()
        page_xml = next(
            tar.extractfile(m).read().decode()
            for m in tar.getmembers()
            if m.name.endswith("page.xml")
        )

    videos = course_xml.findall(".//plugin_local_vidrouter_course/video")
    assert len(videos) == len(course.videos) == 2
    youtubeids = {v.findtext("vidkey"): v.findtext("youtubeid") for v in videos}
    assert youtubeids == {"lec1-1": "abc123", "lec1-2": "def456"}
    assert "[[vid:lec1-1]]" in page_xml
    assert "[[vid:lec1-2]]" in page_xml


# WP-C1
def test_wp_c1_warns_missing_pdf(caplog):
    site = WPFixtureSite()
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--reading" href="{READING_URL}">Reading 1</a></li>'
        ),
    )
    site.add_reading_page(
        READING_URL,
        '<div class="vc_download"><a class="icon fa-file" '
        'href="https://ocw.tudelft.nl/wp-content/uploads/Missing.pdf">'
        "<strong>Missing</strong></a></div>",
    )
    course = site.course()
    with caplog.at_level(logging.WARNING, logger="ocw.wp_parser"):
        course.parse()

    assert course.readings == []
    assert any("Missing pdf" in r.message for r in caplog.records)
