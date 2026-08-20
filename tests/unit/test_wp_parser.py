from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from ocw.wp_parser import WPCourse

HOME_NO_ACTIVITIES = """
<h1>Example Course</h1>
<p>No chapter list on this page.</p>
"""

SUBJECT_PAGE_NO_ACTIVITIES = """
<article><p>No activities list here.</p></article>
"""

SUBJECT_PAGE_UNHANDLED_ICON_TYPE = """
<article>
<ul class="activities">
<li>
<h4 class="expand expand--showing"><span class="icon fa-minus course-title">1.1 Basics</span></h4>
<ul>
<li><a class="icon icon--quiz" href="https://ocw.tudelft.nl/course-quizzes/q1/">Quiz 1</a></li>
</ul>
</li>
</ul>
</article>
"""

READING_EMPTY_EXPANDABLE_WIDGET = """
<article>
<div class="vc_row">
<p>Kept text.</p>
<div class="vc_expandable_text"></div>
</div>
</article>
"""

READING_PLAIN_IMAGE_NO_ALIGN_CLASS = """
<article><p><img src="https://ocw.tudelft.nl/photo.jpg"/>Bio text.</p></article>
"""

READING_NO_ARTICLE = """
<div>No article element on this page at all.</div>
"""

LECTURE_WITH_PDF = """
<article>
<h1>Lecture 1</h1>
<div class="vc_row">
<div class="vc_download">
<a class="icon fa-file" href="https://ocw.tudelft.nl/wp-content/uploads/slides.pdf"><strong>Slides</strong></a>
</div>
</div>
</article>
"""

READING_WITH_UNRESOLVABLE_PDF = """
<article>
<h1>Reading 1</h1>
<div class="vc_row"><p>Some descriptive text.</p></div>
<div class="vc_row">
<div class="vc_download">
<a class="icon fa-file" href="https://ocw.tudelft.nl/wp-content/uploads/missing.pdf"><strong>Missing</strong></a>
</div>
</div>
</article>
"""


class _FakeFetcher:
    def __init__(self, path: Path | None):
        self._path = path
        self.calls: list[str] = []

    def fetch(self, url: str) -> Path | None:
        self.calls.append(url)
        return self._path

HOME = """
<h1>Example Course</h1>
<ul class="activities activities--bordered">
<li>
<h4>Subjects</h4>
<ul>
<li><a href="https://ocw.tudelft.nl/courses/example/subjects/1-intro/">1. Intro</a></li>
</ul>
</li>
</ul>
"""

HOME_WEEKS_HEADING = """
<h1>Example Course</h1>
<ul class="activities activities--bordered">
<li>
<h4>Weeks</h4>
<ul>
<li><a href="https://ocw.tudelft.nl/courses/example/subjects/1-intro/">1. Intro</a></li>
</ul>
</li>
</ul>
"""

SUBJECT_PAGE = """
<article>
<ul class="activities">
<li>
<h4 class="expand expand--showing"><span class="icon fa-minus course-title">1.1 Basics</span></h4>
<ul>
<li><a class="icon icon--lecture" href="https://ocw.tudelft.nl/course-lectures/lec1/">Lecture 1</a></li>
<li><a class="icon icon--reading" href="https://ocw.tudelft.nl/course-readings/read1/">Reading 1</a></li>
<li><a class="icon icon--exercise" href="https://ocw.tudelft.nl/course-exercises/ex1/">Exercise 1</a></li>
</ul>
</li>
</ul>
</article>
"""

SUBJECT_PAGE_WITH_INTRO = """
<article>
<div class="vc_row wpb_row vc_row-fluid"><p>Intro text for this subject.</p></div>
<ul class="activities">
<li>
<h4 class="expand expand--showing"><span class="icon fa-minus course-title">1.1 Basics</span></h4>
<ul>
<li><a class="icon icon--lecture" href="https://ocw.tudelft.nl/course-lectures/lec1/">Lecture 1</a></li>
</ul>
</li>
</ul>
</article>
"""

LECTURE_YOUTUBE = """
<article><iframe src="https://www.youtube.com/embed/abc123"></iframe></article>
"""

LECTURE_COLLEGERAMA = """
<article><iframe src="https://collegerama.tudelft.nl/Mediasite/Play/xyz789"></iframe></article>
"""

LECTURE_WITH_SURROUNDING_TEXT = """
<article>
<h1>Lecture 1</h1>
<p class="article__link-list">Course subject(s) 1. Intro</p>
<div class="vc_row"><p>Intro paragraph before the video.</p></div>
<div class="vc_row"><iframe src="https://www.youtube.com/embed/abc123"></iframe></div>
<div class="vc_row"><p>Follow-up paragraph after the video.</p></div>
<section class="license"><p>CC license text.</p></section>
</article>
"""

READING_WITH_PDF = """
<article>
<div class="vc_download">
<a class="icon fa-file" href="https://ocw.tudelft.nl/wp-content/uploads/Chapter.pdf"><strong>Chapter</strong></a>
</div>
</article>
"""

READING_WITH_PDF_AND_TEXT = """
<article>
<h1>Reading 1</h1>
<p class="article__link-list">Course subject(s) 1. Intro</p>
<div class="vc_row"><p>Some descriptive text about the reading.</p></div>
<div class="vc_row">
<div class="vc_download">
<a class="icon fa-file" href="https://ocw.tudelft.nl/wp-content/uploads/Chapter.pdf"><strong>Chapter</strong></a>
</div>
</div>
<section class="license"><p>CC license text.</p></section>
</article>
"""

READING_NO_ATTACHMENT = """
<article><p>Just inline text, no download link.</p></article>
"""

READING_WITH_ALIGNED_IMAGE_AND_SEPARATOR = """
<article>
<div class="vc_row">
<p><img alt="" class="alignleft wp-image-1" src="https://ocw.tudelft.nl/photo.jpg"/>Bio text here.</p>
<div class="vc_separator"><span class="vc_sep_holder"><span class="vc_sep_line"></span></span></div>
</div>
</article>
"""

READING_WITH_EXPANDABLE_TEXT = """
<article>
<div class="vc_row">
<div class="vc_expandable_text">
<div class="vc_expandable_text__text" style="display: block;">
<strong>Chapter 1: Introduction</strong><br>
Some chapter text.
</div>
<span class="vc_expandable_text__more showing" data-label-less="Read less" data-label-more="Read more">Read less</span>
</div>
</div>
</article>
"""


def _course(pages: dict[str, str]) -> WPCourse:
    course = WPCourse("https://ocw.tudelft.nl/courses/example/")
    course._fetch_page = lambda url: BeautifulSoup(pages[url], "lxml")
    return course


def test_parse_discovers_chapter_from_subjects_sidebar():
    pages = {
        "https://ocw.tudelft.nl/courses/example/": HOME,
        "https://ocw.tudelft.nl/courses/example/subjects/1-intro/": SUBJECT_PAGE,
        "https://ocw.tudelft.nl/course-lectures/lec1/": LECTURE_YOUTUBE,
        "https://ocw.tudelft.nl/course-readings/read1/": READING_NO_ATTACHMENT,
    }
    course = _course(pages)
    course.parse()
    assert course.course_name == "Example Course"
    assert len(course.chapters) == 1
    assert course.chapters[0]["display_name"] == "1. Intro"
    assert len(course.chapters[0]["sequentials"]) == 1
    assert course.chapters[0]["sequentials"][0]["display_name"] == "1.1 Basics"


def test_exercise_link_dropped():
    pages = {
        "https://ocw.tudelft.nl/courses/example/": HOME,
        "https://ocw.tudelft.nl/courses/example/subjects/1-intro/": SUBJECT_PAGE,
        "https://ocw.tudelft.nl/course-lectures/lec1/": LECTURE_YOUTUBE,
        "https://ocw.tudelft.nl/course-readings/read1/": READING_NO_ATTACHMENT,
    }
    course = _course(pages)
    course.parse()
    verticals = course.chapters[0]["sequentials"][0]["verticals"]
    # lecture + reading-with-no-attachment (folded to html); exercise dropped
    assert len(verticals) == 2
    assert {v["display_name"] for v in verticals} == {"Lecture 1", "Reading 1"}


def test_youtube_lecture_becomes_video_component():
    course = _course({})
    course._fetch_page = lambda url: BeautifulSoup(LECTURE_YOUTUBE, "lxml")
    result = course._parse_lecture("https://x/lec1/", "Lecture 1", "Ch 1", "Seq 1")
    video = next(c for c in result["components"] if c["type"] == "video")
    assert video["youtubeid"] == "abc123"
    assert video["tuddownloadid"] is None
    assert video["edxvideoid"] is None
    assert video["vidkey"] == "lec1"
    assert video["videopagepath"] == "Ch 1 > Seq 1 > Lecture 1"


def test_collegerama_lecture_becomes_video_component():
    course = _course({})
    course._fetch_page = lambda url: BeautifulSoup(LECTURE_COLLEGERAMA, "lxml")
    result = course._parse_lecture("https://x/lec2/", "Lecture 2", "Ch 1", "Seq 1")
    video = next(c for c in result["components"] if c["type"] == "video")
    assert video["collegeramaid"] == "xyz789"
    assert video["tuddownloadid"] is None
    assert video["youtubeid"] is None
    assert video["vidkey"] == "lec2"


def test_weeks_heading_still_discovered_via_activities_wrapper():
    """Sidebar heading text varies by course ("Subjects", "Weeks", ...); the
    chapter list is found via the surrounding ul.activities markup instead."""
    pages = {
        "https://ocw.tudelft.nl/courses/example/": HOME_WEEKS_HEADING,
        "https://ocw.tudelft.nl/courses/example/subjects/1-intro/": SUBJECT_PAGE,
        "https://ocw.tudelft.nl/course-lectures/lec1/": LECTURE_YOUTUBE,
        "https://ocw.tudelft.nl/course-readings/read1/": READING_NO_ATTACHMENT,
    }
    course = _course(pages)
    course.parse()
    assert len(course.chapters) == 1
    assert course.chapters[0]["display_name"] == "1. Intro"


def test_reading_with_download_block_becomes_readings_entry():
    course = _course({})
    course.static_files["Chapter.pdf"] = Path("/tmp/Chapter.pdf")
    course._fetch_page = lambda url: BeautifulSoup(READING_WITH_PDF, "lxml")
    result = course._parse_reading("https://x/read1/", "Chapter 1")
    assert result is None  # lives in self.readings, not a vertical
    assert course.readings == [{"title": "Chapter 1", "name": "Chapter.pdf"}]


def test_reading_without_download_block_becomes_html_component():
    course = _course({})
    course._fetch_page = lambda url: BeautifulSoup(READING_NO_ATTACHMENT, "lxml")
    result = course._parse_reading("https://x/read1/", "Chapter 1")
    assert result is not None
    assert result["components"][0]["type"] == "html"
    assert course.readings == []


def test_same_pdf_linked_from_multiple_subjects_appends_twice_no_dedup():
    course = _course({})
    course.static_files["Chapter.pdf"] = Path("/tmp/Chapter.pdf")
    course._fetch_page = lambda url: BeautifulSoup(READING_WITH_PDF, "lxml")
    course._parse_reading("https://x/read1/", "Chapter 1")
    course._parse_reading("https://x/read1/", "Chapter 1")
    assert course.readings == [
        {"title": "Chapter 1", "name": "Chapter.pdf"},
        {"title": "Chapter 1", "name": "Chapter.pdf"},
    ]


def test_subject_page_intro_text_becomes_chapter_summary():
    course = _course({})
    course._fetch_page = lambda url: BeautifulSoup(SUBJECT_PAGE_WITH_INTRO, "lxml")
    chapter = course._parse_subject_page("https://x/subj1/", "1. Intro")
    assert "summary_html" in chapter
    assert "Intro text for this subject." in chapter["summary_html"]


def test_subject_page_without_intro_has_no_summary_key():
    course = _course({})
    course._fetch_page = lambda url: BeautifulSoup(SUBJECT_PAGE, "lxml")
    chapter = course._parse_subject_page("https://x/subj1/", "1. Intro")
    assert "summary_html" not in chapter


def test_lecture_text_captured_in_order_around_video():
    course = _course({})
    course._fetch_page = lambda url: BeautifulSoup(LECTURE_WITH_SURROUNDING_TEXT, "lxml")
    result = course._parse_lecture("https://x/lec1/", "Lecture 1", "Ch 1", "Seq 1")
    # nav list (kept), intro text, video, follow-up text, in document order
    assert [c["type"] for c in result["components"]] == ["html", "html", "video", "html"]
    assert "Course subject(s)" in result["components"][0]["content"]
    assert "Intro paragraph before the video." in result["components"][1]["content"]
    assert "Follow-up paragraph after the video." in result["components"][3]["content"]


def test_lecture_nav_list_kept_license_excluded_from_text():
    course = _course({})
    course._fetch_page = lambda url: BeautifulSoup(LECTURE_WITH_SURROUNDING_TEXT, "lxml")
    result = course._parse_lecture("https://x/lec1/", "Lecture 1", "Ch 1", "Seq 1")
    combined = " ".join(c.get("content", "") for c in result["components"])
    assert "Course subject(s)" in combined
    assert "CC license text" not in combined


def test_expandable_text_converted_to_details_spoiler():
    course = _course({})
    course._fetch_page = lambda url: BeautifulSoup(READING_WITH_EXPANDABLE_TEXT, "lxml")
    result = course._parse_reading("https://x/read1/", "Reading 1")
    assert result is not None
    content = result["components"][0]["content"]
    assert "<details>" in content
    assert "<summary>Read more</summary>" in content
    assert "vc_expandable_text__more" not in content
    assert "display: block" not in content
    assert "Chapter 1: Introduction" in content


def test_aligned_image_gets_float_style_and_separator_dropped():
    course = _course({})
    course._fetch_page = lambda url: BeautifulSoup(
        READING_WITH_ALIGNED_IMAGE_AND_SEPARATOR, "lxml"
    )
    result = course._parse_reading("https://x/read1/", "Bio")
    content = result["components"][0]["content"]
    assert 'style="float:left' in content
    assert "vc_separator" not in content
    assert "<hr" in content


def test_reading_with_pdf_and_text_returns_both_readings_entry_and_page():
    course = _course({})
    course.static_files["Chapter.pdf"] = Path("/tmp/Chapter.pdf")
    course._fetch_page = lambda url: BeautifulSoup(READING_WITH_PDF_AND_TEXT, "lxml")
    result = course._parse_reading("https://x/read1/", "Chapter 1")
    assert course.readings == [{"title": "Chapter 1", "name": "Chapter.pdf"}]
    assert result is not None
    content = result["components"][0]["content"]
    assert "Some descriptive text about the reading." in content
    assert "Course subject(s)" in content
    assert "CC license text" not in content


def test_no_chapter_list_on_home_page_logs_warning_and_returns_empty(caplog):
    course = _course({})
    with caplog.at_level("WARNING"):
        result = course._parse_subjects_sidebar(BeautifulSoup(HOME_NO_ACTIVITIES, "lxml"))
    assert result == []
    assert "No chapter list found" in caplog.text


def test_subject_page_without_activities_list_logs_warning_and_returns_empty_sequentials(
    caplog,
):
    course = _course({})
    course._fetch_page = lambda url: BeautifulSoup(SUBJECT_PAGE_NO_ACTIVITIES, "lxml")
    with caplog.at_level("WARNING"):
        chapter = course._parse_subject_page("https://x/subj1/", "1. Intro")
    assert chapter == {"display_name": "1. Intro", "sequentials": []}
    assert "No activities list found" in caplog.text


def test_unhandled_icon_type_logs_warning_and_is_dropped(caplog):
    course = _course({})
    course._fetch_page = lambda url: BeautifulSoup(
        SUBJECT_PAGE_UNHANDLED_ICON_TYPE, "lxml"
    )
    with caplog.at_level("WARNING"):
        chapter = course._parse_subject_page("https://x/subj1/", "1. Intro")
    assert chapter["sequentials"][0]["verticals"] == []
    assert "Unhandled WP item type 'icon--quiz'" in caplog.text


def test_empty_expandable_widget_is_removed():
    course = _course({})
    course._fetch_page = lambda url: BeautifulSoup(
        READING_EMPTY_EXPANDABLE_WIDGET, "lxml"
    )
    result = course._parse_reading("https://x/read1/", "Reading 1")
    assert result is not None
    content = result["components"][0]["content"]
    assert "Kept text." in content
    assert "vc_expandable_text" not in content


def test_image_without_align_class_gets_no_float_style():
    course = _course({})
    course._fetch_page = lambda url: BeautifulSoup(
        READING_PLAIN_IMAGE_NO_ALIGN_CLASS, "lxml"
    )
    result = course._parse_reading("https://x/read1/", "Bio")
    content = result["components"][0]["content"]
    assert "style=" not in content


def test_reading_page_without_article_element_returns_none():
    course = _course({})
    course._fetch_page = lambda url: BeautifulSoup(READING_NO_ARTICLE, "lxml")
    result = course._parse_reading("https://x/read1/", "Reading 1")
    assert result is None
    assert course.readings == []


def test_lecture_with_download_block_resolves_pdf_into_link_component():
    course = _course({})
    course.fetcher = _FakeFetcher(Path("/tmp/slides.pdf"))
    course._fetch_page = lambda url: BeautifulSoup(LECTURE_WITH_PDF, "lxml")
    result = course._parse_lecture("https://x/lec1/", "Lecture 1", "Ch 1", "Seq 1")
    contents = [c["content"] for c in result["components"] if c["type"] == "html"]
    assert any('href="/static/slides.pdf"' in c for c in contents)
    assert course.static_files["slides.pdf"] == Path("/tmp/slides.pdf")


def test_reading_with_unresolvable_pdf_logs_warning_and_omits_readings_entry(caplog):
    course = _course({})
    course.fetcher = None
    course._fetch_page = lambda url: BeautifulSoup(READING_WITH_UNRESOLVABLE_PDF, "lxml")
    with caplog.at_level("WARNING"):
        result = course._parse_reading("https://x/read1/", "Reading 1")
    assert course.readings == []
    assert "Missing pdf for Readings entry 'Reading 1'" in caplog.text
    assert result is not None
    assert "Some descriptive text." in result["components"][0]["content"]


def test_resolve_and_fetch_returns_cached_static_file_name_without_fetcher():
    course = _course({})
    course.fetcher = None
    course.static_files["Chapter.pdf"] = Path("/tmp/Chapter.pdf")
    name = course._resolve_and_fetch("https://x/wp-content/uploads/Chapter.pdf")
    assert name == "Chapter.pdf"


def test_resolve_and_fetch_returns_none_when_no_fetcher_and_not_cached():
    course = _course({})
    course.fetcher = None
    assert course._resolve_and_fetch("https://x/wp-content/uploads/Unknown.pdf") is None


def test_resolve_and_fetch_returns_none_when_fetcher_fails():
    course = _course({})
    course.fetcher = _FakeFetcher(None)
    assert course._resolve_and_fetch("https://x/wp-content/uploads/Unknown.pdf") is None


def test_resolve_and_fetch_registers_static_file_on_success():
    course = _course({})
    course.fetcher = _FakeFetcher(Path("/tmp/dest/Unknown.pdf"))
    name = course._resolve_and_fetch("https://x/wp-content/uploads/Unknown.pdf")
    assert name == "Unknown.pdf"
    assert course.static_files["Unknown.pdf"] == Path("/tmp/dest/Unknown.pdf")


def test_fetch_page_parses_response_body(monkeypatch):
    course = WPCourse("https://ocw.tudelft.nl/courses/example/")

    class _FakeResponse:
        text = "<h1>Real Page</h1>"

        def raise_for_status(self):
            pass

    class _FakeSession:
        def get(self, url, timeout=None):
            assert url == "https://ocw.tudelft.nl/courses/example/"
            assert timeout == 15
            return _FakeResponse()

    course._session = _FakeSession()
    soup = course._fetch_page("https://ocw.tudelft.nl/courses/example/")
    assert soup.select_one("h1").get_text() == "Real Page"


def test_fetch_page_propagates_http_errors():
    import requests

    course = WPCourse("https://ocw.tudelft.nl/courses/example/")

    class _FakeResponse:
        def raise_for_status(self):
            raise requests.HTTPError("500 server error")

    class _FakeSession:
        def get(self, url, timeout=None):
            return _FakeResponse()

    course._session = _FakeSession()
    with pytest.raises(requests.HTTPError):
        course._fetch_page("https://ocw.tudelft.nl/courses/example/")
