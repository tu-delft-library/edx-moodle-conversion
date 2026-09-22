import zipfile
from pathlib import PurePosixPath

import pytest

from ocw.converter.zip_builder import ZipBuilder, _asset_name, _key, _safe_name
from tests.wp_builders import WPFixtureSite

LECTURE_URL = "https://ocw.tudelft.nl/course-lectures/lec1/"
EXERCISE_URL = "https://ocw.tudelft.nl/course-exercises/ex1/"
READING_URL = "https://ocw.tudelft.nl/course-readings/read1/"
SUBJECT_URL = "https://ocw.tudelft.nl/courses/example/subjects/1-intro/"


def _site() -> WPFixtureSite:
    site = WPFixtureSite()
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_subject_page(
        SUBJECT_URL,
        f"""
        <ul class="activities">
        <li>
        <h4><span class="course-title">1.1 Basics</span></h4>
        <ul>
        <li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>
        <li><a class="icon icon--exercise" href="{EXERCISE_URL}">Exercise 1</a></li>
        <li><a class="icon icon--reading" href="{READING_URL}">Reading 1</a></li>
        </ul>
        </li>
        </ul>
        """,
        intro_html='<div class="vc_row"><p>Subject intro.</p></div>',
    )
    site.add_lecture_page(
        LECTURE_URL,
        """
        <h1>Lecture 1</h1>
        <div class="vc_row"><p onclick="steal()">Text.</p><script>alert(1)</script></div>
        <div class="vc_row"><img src="https://ocw.tudelft.nl/wp-content/uploads/diagram.png"></div>
        <div class="vc_row"><iframe src="https://www.youtube.com/embed/abc123"></iframe></div>
        """,
    )
    site.add_lecture_page(EXERCISE_URL, "<h1>Exercise 1</h1><p>Solve it.</p>")
    site.add_reading_page(
        READING_URL,
        '<div class="vc_download"><a class="icon fa-file" '
        'href="https://ocw.tudelft.nl/wp-content/uploads/Chapter.pdf">'
        "<strong>Chapter</strong></a></div>",
        pdf_name="Chapter.pdf",
    )
    site.add_static_file("diagram.png", b"png-bytes")
    site.add_static_file("fontawesome-webfont.woff2", b"font")
    site.add_static_file("fontawesome-webfont.woff", b"font")
    return site


@pytest.fixture
def archive(tmp_path):
    course = _site().course(keep_all_content=True)
    course.parse()
    out = tmp_path / "course.zip"
    ZipBuilder(course).build(out)
    with zipfile.ZipFile(out) as zf:
        yield zf


def _read(zf: zipfile.ZipFile, name: str) -> str:
    return zf.read(name).decode("utf-8")


def test_zip_has_folder_tree_under_course_slug(archive):
    names = set(archive.namelist())
    assert "Example_Course/index.html" in names
    assert "Example_Course/01_1._Intro/index.html" in names
    assert "Example_Course/01_1._Intro/01_1.1_Basics/01_Lecture_1.html" in names
    assert "Example_Course/01_1._Intro/01_1.1_Basics/02_Exercise_1.html" in names


def test_assets_are_flat_under_assets(archive):
    names = set(archive.namelist())
    assert "Example_Course/assets/diagram.png" in names
    assert "Example_Course/assets/Chapter.pdf" in names
    assert archive.read("Example_Course/assets/diagram.png") == b"png-bytes"


def test_static_references_point_at_relative_assets(archive):
    page = _read(archive, "Example_Course/01_1._Intro/01_1.1_Basics/01_Lecture_1.html")
    assert 'src="../../assets/diagram.png"' in page
    assert "/static/" not in page


def test_scripts_and_event_handlers_are_stripped(archive):
    page = _read(archive, "Example_Course/01_1._Intro/01_1.1_Basics/01_Lecture_1.html")
    assert "<script" not in page
    assert "onclick" not in page
    assert "Text." in page


def test_kept_title_and_video_embed_are_in_the_page(archive):
    page = _read(archive, "Example_Course/01_1._Intro/01_1.1_Basics/01_Lecture_1.html")
    assert "<h1>Lecture 1</h1>" in page
    assert 'src="https://www.youtube.com/embed/abc123"' in page


def test_reading_link_resolves_to_reading_page(archive):
    page = _read(archive, "Example_Course/01_1._Intro/01_1.1_Basics/03_Reading_1.html")
    assert 'href="../../readings/01_Reading_1.html"' in page
    assert "Example_Course/readings/01_Reading_1.html" in archive.namelist()


def test_chapter_index_lists_summary_and_pages(archive):
    page = _read(archive, "Example_Course/01_1._Intro/index.html")
    assert "<h1>1. Intro</h1>" in page
    assert "Subject intro." in page
    assert 'href="01_1.1_Basics/01_Lecture_1.html"' in page


def test_root_index_lists_chapters_and_readings(archive):
    page = _read(archive, "Example_Course/index.html")
    assert "<h1>Example Course</h1>" in page
    assert 'href="01_1._Intro/index.html"' in page
    assert 'href="readings/01_Reading_1.html"' in page
    assert "Back to index" not in page


def test_pages_link_back_to_root_index(archive):
    page = _read(archive, "Example_Course/01_1._Intro/01_1.1_Basics/01_Lecture_1.html")
    assert 'href="../../index.html">Back to index' in page


def test_dedup_link_resolves_to_shared_page(tmp_path):
    site = _site()
    second = "https://ocw.tudelft.nl/courses/example/subjects/2-more/"
    site.add_home([(SUBJECT_URL, "1. Intro"), (second, "2. More")])
    site.add_subject_page(
        second,
        f"""
        <ul class="activities"><li>
        <h4><span class="course-title">2.1 Again</span></h4>
        <ul><li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li></ul>
        </li></ul>
        """,
    )
    course = site.course(keep_all_content=True)
    course.parse()
    out = tmp_path / "shared.zip"
    ZipBuilder(course).build(out)
    with zipfile.ZipFile(out) as zf:
        assert "Example_Course/shared/01_Lecture_1.html" in zf.namelist()
        page = _read(zf, "Example_Course/01_1._Intro/01_1.1_Basics/01_Lecture_1.html")
        assert 'href="../../shared/01_Lecture_1.html"' in page


def test_unknown_component_type_raises():
    builder = ZipBuilder(_site().course())
    with pytest.raises(ValueError, match="unknown component type: nope"):
        builder._render({"type": "nope"}, PurePosixPath("a.html"))


def test_safe_name_neutralises_path_traversal():
    assert _safe_name("../../etc/passwd", 3) == "03_etc_passwd"


def test_safe_name_falls_back_for_empty_titles():
    assert _safe_name("///", 1) == "01_untitled"


def test_asset_name_and_key_helpers():
    assert _asset_name("a b/c.png") == "a_b_c.png"
    assert _key("https://x/y/#frag") == "https://x/y"
