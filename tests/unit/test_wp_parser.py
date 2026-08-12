from pathlib import Path

from bs4 import BeautifulSoup

from ocw.wp_parser import WPCourse

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
    assert video["tuddownloadid"] == "xyz789"
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
