import io
import zipfile
from pathlib import PurePosixPath

import pytest
from docx import Document
from docx.oxml.ns import qn
from PIL import Image

from ocw.converter.zip_builder import ZipBuilder
from ocw.url_audit import audit_zip
from tests.unit.test_zip_builder import EXERCISE_URL, LECTURE_URL, READING_URL, SUBJECT_URL, _site

LECTURE = "Example_Course/01_1._Intro/01_1.1_Basics/01_Lecture_1.html"
EXERCISE = "02_Exercise_1.html"
LINKS = f"""
<p><a href="{EXERCISE_URL}">go exercise</a>
<a href=" http://ocw.tudelft.nl{EXERCISE_URL.removeprefix("https://ocw.tudelft.nl")}/ ">spaced</a>
<a href="{READING_URL}">go reading</a>
<a href="{SUBJECT_URL}">go subject</a>
<a href="https://ocw.tudelft.nl/courses/example/">home</a>
<a href="https://ocw.tudelft.nl/more/hall-of-fame/">fame</a>
<a href="http://ocw.tudelft.nl">TU Delft OpenCourseWare</a>
<a href="https://ocw.tudelft.nl/courses/example/">https://ocw.tudelft.nl/courses/example/</a>
<a href="https://www.youtube.com/watch?v=abc">yt</a></p>
"""

WIDGET = """<div class="TUD_box_download"><div class="video-download"><ul><li>
<a href="https://delftxdownloads.tudelft.nl/x/video.mp4">video</a></li></ul></div>
<div class="other-download"><ul><li>
<a href="https://delftxdownloads.tudelft.nl/x/other.zip">other</a></li></ul></div></div>
"""


@pytest.fixture
def page(tmp_path):
    site = _site()
    site.pages[LECTURE_URL] = site.pages[LECTURE_URL].replace("</article>", f"{LINKS}</article>")
    course = site.course(keep_all_content=True)
    course.parse()
    out = tmp_path / "course.zip"
    ZipBuilder(course).build(out)
    with zipfile.ZipFile(out) as zf:
        zf.audit_path = out
        yield zf.read(LECTURE).decode(), out


def test_links_to_pages_in_the_zip_become_relative(page):
    html, _ = page
    assert html.count(f'href="{EXERCISE}"') == 2
    assert 'href="../../index.html"' in html


def test_subject_link_points_at_the_chapter_index(page):
    html, _ = page
    assert 'href="../index.html"' in html


def test_unknown_dead_host_link_is_unwrapped_with_its_url_as_text(page):
    html, _ = page
    assert "fame (https://ocw.tudelft.nl/more/hall-of-fame/)" in html
    assert "hall-of-fame/\"" not in html


def test_attribution_link_is_unwrapped_to_plain_text(page):
    html, _ = page
    assert "TU Delft OpenCourseWare (http://ocw.tudelft.nl)" in html


def test_link_whose_text_is_its_url_is_not_repeated(page):
    html, _ = page
    assert "https://ocw.tudelft.nl/courses/example/ (" not in html


def test_third_party_and_widget_media_links_stay(page):
    html, _ = page
    assert 'href="https://www.youtube.com/watch?v=abc"' in html


def test_widget_media_links_stay_but_other_widget_links_are_unwrapped():
    builder = ZipBuilder(_site().course(keep_all_content=True))
    out = builder._relink(WIDGET, PurePosixPath("a/b.html"))
    assert 'href="https://delftxdownloads.tudelft.nl/x/video.mp4"' in out
    assert "other.zip" in out and 'href="https://delftxdownloads.tudelft.nl/x/other.zip"' not in out


def test_audit_passes_on_a_relinked_zip(page):
    _, out = page
    assert [h for h in audit_zip(out) if h.element.startswith(("ocw", "platform", "broken"))] == []


def test_course_banner_is_shown_on_the_index_so_it_is_not_an_orphan(tmp_path):
    site = _site()
    site.add_home([(SUBJECT_URL, "1. Intro")], banner_url="https://ocw.tudelft.nl/wp-content/uploads/banner.jpg")
    site.add_static_file("banner.jpg", b"banner")
    course = site.course(keep_all_content=True)
    course.parse()
    out = tmp_path / "course.zip"
    ZipBuilder(course).build(out)
    with zipfile.ZipFile(out) as zf:
        assert '<img src="assets/banner.jpg" alt="">' in zf.read("Example_Course/index.html").decode()
    assert [h for h in audit_zip(out) if h.element == "orphan asset"] == []


def test_course_banner_is_embedded_in_the_docx(tmp_path):
    site = _site()
    site.add_home([(SUBJECT_URL, "1. Intro")], banner_url="https://ocw.tudelft.nl/wp-content/uploads/banner.jpg")
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4)).save(buffer, "JPEG")
    site.add_static_file("banner.jpg", buffer.getvalue())
    course = site.course(keep_all_content=True)
    course.parse()
    out = tmp_path / "course.zip"
    ZipBuilder(course).build(out)
    with zipfile.ZipFile(out) as zf:
        doc = Document(io.BytesIO(zf.read("Example_Course/course.docx")))
    assert any(blip.get(qn("r:embed")) for blip in doc.element.body.iter(qn("a:blip")))
