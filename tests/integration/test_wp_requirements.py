import logging
import tarfile
from xml.etree import ElementTree as ET

import pytest

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


# WP-CC6
def test_wp_cc6_vc_single_image_wrapper_alignment_survives_into_mbz(tmp_path):
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
        '<div class="wpb_single_image wpb_content_element vc_align_left">'
        '<figure class="wpb_wrapper vc_figure">'
        '<div class="vc_single_image-wrapper vc_box_border_grey">'
        '<img class="vc_single_image-img attachment-full" src="pic.png"/>'
        "</div></figure></div>",
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
    assert esc("float:left;margin:0 1em 1em 0;") in page_xml


_TUD_HOST_CHECK = 'TUD_location.indexOf("ocw.tudelft.nl")!=-1'

_DOWNLOAD_TOOL_HTML = (
    '<div class="wpb_raw_code wpb_content_element wpb_raw_html"><div class="wpb_wrapper">'
    '<div class="TUD_box_download" data-downloadid="Course/Week_1/Course_lec" '
    'data-videotype=".mp4" data-youtubeid="abc123">'
    '<div class="tud-button tud-float video-download">'
    '<img class="tud-float tud_video_img" src="/static/icon_grey1_video_blanc_36.png"/>'
    '<ul class="TUD"><li class="TUD TUD_High_Video"><a href="#" target="_blank">High</a></li></ul>'
    "</div></div>"
    '<script type="text/javascript">'
    "var TUD_location=window.location.href;"
    'if(TUD_location.indexOf("ocw.tudelft.nl")!=-1){'
    '$.getScript("https://delftxdownloads.tudelft.nl/download-tool/OCW/TUD_download_tool.js")'
    '}else $.getScript("/static/TUD_download_tool.js");'
    "</script></div></div>"
)


_WIDGET_ID = "Course/Week_1/Course_lec"
_WIDGET_BASE = f"https://delftxdownloads.tudelft.nl/{_WIDGET_ID}"


def _widget_site(body_html: str, *tool_ids: str, slides: bool = True) -> WPFixtureSite:
    site = WPFixtureSite()
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>'
        ),
    )
    site.add_lecture_page(LECTURE_URL, body_html)
    for tool_id in tool_ids or (_WIDGET_ID,):
        site.add_download_tool_page(tool_id, slides=slides)
    return site


def _built_page_xml(site: WPFixtureSite, tmp_path) -> str:
    course = site.course()
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        return next(
            tar.extractfile(m).read().decode()
            for m in tar.getmembers()
            if m.name.endswith("page.xml")
        )


# WP-CC7
@pytest.mark.parametrize(
    "wrap",
    [
        pytest.param(lambda html: html, id="bare_markup"),
        pytest.param(lambda html: f'<div id="download_tool">{html}</div>', id="id_wrapped"),
    ],
)
def test_wp_cc7_download_tool_widget_inlined_from_tool_page(tmp_path, wrap):
    """The DelftxDownloads widget is rebuilt inline from its server-rendered tool page, instead
    of depending on the CDN script chain (TUD_download_tool.js -> builder.js -> resizer.js),
    which aborts under Moodle's RequireJS. Dropdowns become native `details` so no JS is needed.
    Matched by class so it's patched whether or not WP wraps it in `id="download_tool"`."""
    site = _widget_site(f"<p>content</p>{wrap(_DOWNLOAD_TOOL_HTML)}")
    page_xml = _built_page_xml(site, tmp_path)

    assert esc(_TUD_HOST_CHECK) not in page_xml
    assert "TUD_download_tool" not in page_xml
    assert "iframeResizer" not in page_xml
    assert "transfer_div" not in page_xml
    assert esc("<iframe") not in page_xml
    assert esc('<details class="tud-button tud-float video-download"') in page_xml
    assert esc('<summary class="tud-button-top video-download-top">') in page_xml
    assert esc(".tud-button[open]") in page_xml
    assert f"{_WIDGET_BASE}-video.mp4" in page_xml
    assert f"{_WIDGET_BASE}-video.srt" in page_xml


def test_wp_cc7_download_tool_widget_placeholder_icons_not_reported_lost(caplog):
    """The WP box's own placeholder markup is replaced wholesale, so its icons going missing is
    expected, not content loss."""
    course = _widget_site(f"<p>content</p>{_DOWNLOAD_TOOL_HTML}").course()
    with caplog.at_level("WARNING"):
        course.parse()

    assert "icon_grey1_video_blanc_36.png" not in caplog.text


def test_wp_cc7_download_tool_widget_defaults_filetype_when_missing():
    """builder.js defaults a missing/empty filetype to "mp4"; the tool page is requested with
    the same default (the fixture only serves the `ft=mp4` URL)."""
    html = (
        f'<div class="TUD_box_download" data-downloadid="{_WIDGET_ID}">'
        '<ul class="TUD"><li class="TUD TUD_High_Video"><a href="#">High</a></li></ul>'
        "</div>"
    )
    course = _widget_site(f"<p>content</p>{html}").course()
    course.parse()

    lecture = course.chapters[0]["sequentials"][0]["verticals"][0]
    assert any(
        f"{_WIDGET_BASE}-video.mp4" in c["content"]
        for c in lecture["components"]
        if c["type"] == "html"
    )


def test_wp_cc7_download_tool_widget_without_id_is_dropped():
    html = '<div class="TUD_box_download" data-videotype=".mp4"></div>'
    course = _widget_site(f"<p>content</p>{html}").course()
    course.parse()

    lecture = course.chapters[0]["sequentials"][0]["verticals"][0]
    assert not any(
        "TUD_box_download" in c["content"]
        for c in lecture["components"]
        if c["type"] == "html"
    )


def test_wp_cc7_download_tool_widget_icons_bundled_locally(tmp_path):
    site = _widget_site(
        f'<div class="TUD_box_download" data-downloadid="{_WIDGET_ID}" '
        'data-videotype=".mp4"></div>'
    )
    site.add_static_file("icon_video_blanc_36.png", content=b"\x89PNG\r\n\x1a\n")
    site.add_static_file("icon_subtitles_blanc_36.png", content=b"\x89PNG\r\n\x1a\n")
    page_xml = _built_page_xml(site, tmp_path)

    assert esc("@@PLUGINFILE@@/icon_video_blanc_36.png") in page_xml
    assert esc("@@PLUGINFILE@@/icon_subtitles_blanc_36.png") in page_xml
    assert "img/icon_video_blanc_36.png" not in page_xml


# WP-CC7 (negative case)
def test_wp_cc7_no_download_tool_widget_is_a_no_op():
    course = _widget_site("<p>content</p>").course()
    course.parse()

    lecture = course.chapters[0]["sequentials"][0]["verticals"][0]
    html_components = [
        c["content"] for c in lecture["components"] if c["type"] == "html"
    ]
    assert any("content" in html for html in html_components)


# WP-CC7 (tuddownloadid pairing)
def test_wp_cc7_download_widget_pairs_tuddownloadid_onto_the_page_video():
    """A lecture page with exactly one download widget and one video gets the widget's id
    attached to the video's vidrouter record, the same cross-reference OLX already populates
    for dframe/video pairs."""
    html = (
        '<iframe src="https://www.youtube.com/embed/abc123"></iframe>'
        f'<div class="TUD_box_download" data-downloadid="{_WIDGET_ID}" '
        'data-videotype=".mp4"></div>'
    )
    course = _widget_site(html).course()
    course.parse()

    video = next(
        c
        for c in course.chapters[0]["sequentials"][0]["verticals"][0]["components"]
        if c["type"] == "video"
    )
    assert video["tuddownloadid"] == _WIDGET_ID


def test_wp_cc7_download_widget_tuddownloadid_ambiguous_multiple_widgets(caplog):
    """Two download widgets and one video on the same page -> ambiguous, logged, left
    unpaired. Mirrors OLX's `_attach_video_download_ids` ambiguity rule exactly."""
    html = (
        '<iframe src="https://www.youtube.com/embed/abc123"></iframe>'
        '<div class="TUD_box_download" data-downloadid="a" data-videotype=".mp4"></div>'
        '<div class="TUD_box_download" data-downloadid="b" data-videotype=".mp4"></div>'
    )
    course = _widget_site(html, "a", "b").course()
    with caplog.at_level("WARNING"):
        course.parse()

    video = next(
        c
        for c in course.chapters[0]["sequentials"][0]["verticals"][0]["components"]
        if c["type"] == "video"
    )
    assert video["tuddownloadid"] is None
    assert "Ambiguous" in caplog.text


# WP-CC7 (slides / "Other" tab)
def test_wp_cc7_download_widget_other_tab_serves_slides_from_mbz(tmp_path):
    """The "Other" tab's slide deck is fetched and bundled, and the tab's own link points at
    the bundled copy; Video/Subtitles links keep pointing at delftxdownloads."""
    site = _widget_site(
        f'<div class="TUD_box_download" data-downloadid="{_WIDGET_ID}" '
        'data-videotype=".mp4"></div>'
    )
    site.add_static_file("Course_lec-slides.pdf")
    page_xml = _built_page_xml(site, tmp_path)

    assert esc('<details class="tud-button tud-float other-download"') in page_xml
    assert esc('href="@@PLUGINFILE@@/Course_lec-slides.pdf"') in page_xml
    assert f"{_WIDGET_BASE}-slides.pdf" not in page_xml
    assert f"{_WIDGET_BASE}-video.mp4" in page_xml
    assert esc(">Slides<") in page_xml


def test_wp_cc7_download_widget_no_slides_is_a_no_op():
    """Lectures without a deck get no Other tab from the tool page, so none is rendered."""
    html = (
        f'<div class="TUD_box_download" data-downloadid="{_WIDGET_ID}" '
        'data-videotype=".mp4"></div>'
    )
    course = _widget_site(html, slides=False).course()
    course.parse()

    lecture = course.chapters[0]["sequentials"][0]["verticals"][0]
    assert not any(
        "Slides" in c["content"] or "other-download" in c["content"]
        for c in lecture["components"]
        if c["type"] == "html"
    )


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


# WP-C2
def test_wp_c2_image_sibling_of_video_iframe_still_captured(caplog):
    """A top-level container mixing a video iframe with sibling real content (images/text) --
    WPBakery's normal shape, video and text/image columns nested several layout-div levels deep
    inside one shared row -- must not have its non-video siblings swallowed by the video branch.
    Reproduces the shape found live in `mathematical-modeling-basics` (`example-2-sediment-
    estuary`, 21 images lost across 6 lecture pages before this fix) and asserts both the image
    is captured in a component and the content-loss audit stays silent about it.
    """
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
        '<div class="wpb_text_column"><img src="https://ocw.tudelft.nl/wp-content/uploads/diagram.png"/></div>'
        '<div class="vc_lecture"><iframe src="https://www.youtube.com/embed/abc123"></iframe></div>'
        "</div>",
    )
    course = site.course()
    with caplog.at_level(logging.WARNING, logger="ocw.wp_parser"):
        course.parse()

    assert not any("not captured" in r.message for r in caplog.records)
    lecture = course.chapters[0]["sequentials"][0]["verticals"][0]
    html_components = [
        c["content"] for c in lecture["components"] if c["type"] == "html"
    ]
    assert any("diagram.png" in html for html in html_components)
    videos = [c for c in lecture["components"] if c["type"] == "video"]
    assert len(videos) == 1
    assert videos[0]["youtubeid"] == "abc123"


# WP-C2 (negative case)
def test_wp_c2_no_false_positive_on_single_video_page(caplog):
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
    with caplog.at_level(logging.WARNING, logger="ocw.wp_parser"):
        course.parse()

    assert not any("not captured" in r.message for r in caplog.records)


# WP-C2 (negative case)
def test_wp_c2_no_false_positive_on_image_only_page(caplog):
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
        '<p><img src="https://ocw.tudelft.nl/wp-content/uploads/pic.png"/></p>',
    )
    course = site.course()
    with caplog.at_level(logging.WARNING, logger="ocw.wp_parser"):
        course.parse()

    assert not any("not captured" in r.message for r in caplog.records)


# WP-C3
def test_wp_c3_multiple_downloads_in_one_row_all_captured(tmp_path, caplog):
    """Reproduces the shape found live in `breakwaters-and-closure-dams` (`6-data-collection`):
    two `vc_download` blocks side by side in one `vc_row`, as WPBakery column siblings rather
    than at the article's top level. Both must be fetched, keep their own caption/filename
    (never the lecture title), and stay in source order relative to surrounding text."""
    site = WPFixtureSite()
    site.add_static_file("ct530806.pdf", b"%PDF-1.4 fake")
    site.add_static_file("GumbelWeibull__1_.xls", b"fake xls bytes")
    site.add_static_file("fontawesome-webfont.woff2", b"fake woff2 bytes")
    site.add_static_file("fontawesome-webfont.woff", b"fake woff bytes")
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>'
        ),
    )
    site.add_lecture_page(
        LECTURE_URL,
        '<p>before text</p>'
        '<div class="vc_row wpb_row vc_row-fluid">'
        '<div class="wpb_column vc_column_container vc_col-sm-6"><div class="vc_column-inner">'
        '<div class="wpb_wrapper"><div class="vc_download">'
        '<a class="icon fa-file" target="_blank" '
        'href="https://ocw.tudelft.nl/wp-content/uploads/ct530806.pdf">'
        '<strong>Download of the presentation</strong>ct530806.pdf</a>'
        '</div></div></div></div>'
        '<div class="wpb_column vc_column_container vc_col-sm-6"><div class="vc_column-inner">'
        '<div class="wpb_wrapper"><div class="vc_download">'
        '<a class="icon fa-file" target="_blank" '
        'href="https://ocw.tudelft.nl/wp-content/uploads/GumbelWeibull__1_.xls">'
        '<strong>Download of the presentation</strong>GumbelWeibull__1_.xls</a>'
        '</div></div></div></div>'
        '</div>'
        '<p>after text</p>',
    )
    course = site.course()
    with caplog.at_level(logging.WARNING, logger="ocw.wp_parser"):
        course.parse()

    assert not any("download" in r.message for r in caplog.records)

    lecture = course.chapters[0]["sequentials"][0]["verticals"][0]
    html_components = [c["content"] for c in lecture["components"] if c["type"] == "html"]

 
    row_html = next(h for h in html_components if "ct530806.pdf" in h)
    assert "GumbelWeibull__1_.xls" in row_html
    assert row_html.startswith('<div class="ocw-vc-row">')
    assert "Download of the presentation" in row_html
    assert "Lecture 1" not in row_html
    pdf_pos = row_html.index("ct530806.pdf")
    xls_pos = row_html.index("GumbelWeibull__1_.xls")
    assert pdf_pos < xls_pos  # source order preserved within the row

    before_i = next(i for i, h in enumerate(html_components) if "before text" in h)
    row_i = html_components.index(row_html)
    after_i = next(i for i, h in enumerate(html_components) if "after text" in h)
    assert before_i < row_i < after_i

    style_components = [h for h in html_components if h.startswith("<style>")]
    assert len(style_components) == 1
    assert "fontawesome-webfont.woff2" in style_components[0]

    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        files_xml = ET.parse(tar.extractfile("files.xml")).getroot()
        filenames = [f.findtext("filename") for f in files_xml.findall("file")]
    assert filenames.count("ct530806.pdf") == 1
    assert filenames.count("GumbelWeibull__1_.xls") == 1
    assert filenames.count("fontawesome-webfont.woff2") == 1
    assert filenames.count("fontawesome-webfont.woff") == 1


# WP-C4
def test_wp_c4_sibling_text_survives_alongside_grouped_downloads(tmp_path):
    """Reproduces the shape found live on `introduction-development-cooperation`: a row with a
    non-download column (a bullet-list link) sitting beside several `vc_download` columns.
    `_find_download_link`'s descendant-wide search used to make `_classify_lecture_child`
    swallow the whole row into one `pdf_url_group`, silently dropping the bullet list. The
    downloads must still end up grouped in one `ocw-vc-row` and the bullet list must survive as
    its own component."""
    site = WPFixtureSite()
    site.add_static_file("Report.pdf", b"%PDF-1.4 fake")
    site.add_static_file("Summary.pdf", b"%PDF-1.4 fake")
    site.add_static_file("fontawesome-webfont.woff2", b"fake woff2 bytes")
    site.add_static_file("fontawesome-webfont.woff", b"fake woff bytes")
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>'
        ),
    )
    site.add_lecture_page(
        LECTURE_URL,
        '<div class="vc_row wpb_row vc_row-fluid">'
        '<div class="wpb_column vc_column_container vc_col-sm-3"><div class="vc_column-inner">'
        '<div class="wpb_wrapper"><div class="wpb_text_column"><div class="wpb_wrapper">'
        '<ul><li>The website: <a href="http://www.actionaid.org/">www.actionaid.org</a></li></ul>'
        '</div></div></div></div></div>'
        '<div class="wpb_column vc_column_container vc_col-sm-3"><div class="vc_column-inner">'
        '<div class="wpb_wrapper"><div class="vc_download">'
        '<a class="icon fa-file" target="_blank" '
        'href="https://ocw.tudelft.nl/wp-content/uploads/Report.pdf">'
        '<strong>The Report</strong>Report.pdf</a>'
        '</div></div></div></div>'
        '<div class="wpb_column vc_column_container vc_col-sm-3"><div class="vc_column-inner">'
        '<div class="wpb_wrapper"><div class="vc_download">'
        '<a class="icon fa-file" target="_blank" '
        'href="https://ocw.tudelft.nl/wp-content/uploads/Summary.pdf">'
        '<strong>The Summary</strong>Summary.pdf</a>'
        '</div></div></div></div>'
        '</div>',
    )
    course = site.course()
    course.parse()

    lecture = course.chapters[0]["sequentials"][0]["verticals"][0]
    html_components = [c["content"] for c in lecture["components"] if c["type"] == "html"]

    bullet_html = next(h for h in html_components if "actionaid.org" in h)
    assert "website" in bullet_html

    row_html = next(h for h in html_components if "Report.pdf" in h)
    assert "Summary.pdf" in row_html
    assert row_html.startswith('<div class="ocw-vc-row">')

    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        files_xml = ET.parse(tar.extractfile("files.xml")).getroot()
        filenames = [f.findtext("filename") for f in files_xml.findall("file")]
    assert filenames.count("Report.pdf") == 1
    assert filenames.count("Summary.pdf") == 1


# WP-C4 (nested case)
def test_wp_c4_heading_survives_above_nested_download_row(tmp_path):
    """Reproduces the shape found live on `field-visit-kitui-kenya`: a heading + paragraph sit
    above a nested `vc_row vc_inner` containing several `vc_download` blocks, all inside one
    shared top-level row. The heading/paragraph must survive as their own component and the
    nested downloads must still end up grouped together."""
    site = WPFixtureSite()
    site.add_static_file("Mission.pdf", b"%PDF-1.4 fake")
    site.add_static_file("Villagers.pdf", b"%PDF-1.4 fake")
    site.add_static_file("fontawesome-webfont.woff2", b"fake woff2 bytes")
    site.add_static_file("fontawesome-webfont.woff", b"fake woff bytes")
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>'
        ),
    )
    site.add_lecture_page(
        LECTURE_URL,
        '<div class="vc_row wpb_row vc_row-fluid">'
        '<div class="wpb_column vc_column_container vc_col-sm-12"><div class="vc_column-inner">'
        '<div class="wpb_wrapper">'
        '<div class="wpb_text_column"><div class="wpb_wrapper">'
        '<h2>Senegal Roleplay material</h2><p>.</p>'
        '</div></div>'
        '<div class="vc_row wpb_row vc_inner vc_row-fluid">'
        '<div class="wpb_column vc_column_container vc_col-sm-4"><div class="vc_column-inner">'
        '<div class="wpb_wrapper"><div class="vc_download">'
        '<a class="icon fa-file" target="_blank" '
        'href="https://ocw.tudelft.nl/wp-content/uploads/Mission.pdf">'
        '<strong>Mission</strong>Mission.pdf</a>'
        '</div></div></div></div>'
        '<div class="wpb_column vc_column_container vc_col-sm-4"><div class="vc_column-inner">'
        '<div class="wpb_wrapper"><div class="vc_download">'
        '<a class="icon fa-file" target="_blank" '
        'href="https://ocw.tudelft.nl/wp-content/uploads/Villagers.pdf">'
        '<strong>Villagers General</strong>Villagers.pdf</a>'
        '</div></div></div></div>'
        '</div>'
        '</div></div></div></div>',
    )
    course = site.course()
    course.parse()

    lecture = course.chapters[0]["sequentials"][0]["verticals"][0]
    html_components = [c["content"] for c in lecture["components"] if c["type"] == "html"]

    heading_html = next(h for h in html_components if "Senegal Roleplay material" in h)
    assert "<h2>" in heading_html

    row_html = next(h for h in html_components if "Mission.pdf" in h)
    assert "Villagers.pdf" in row_html
    assert row_html.startswith('<div class="ocw-vc-row">')

    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        files_xml = ET.parse(tar.extractfile("files.xml")).getroot()
        filenames = [f.findtext("filename") for f in files_xml.findall("file")]
    assert filenames.count("Mission.pdf") == 1
    assert filenames.count("Villagers.pdf") == 1


# WP-C3 (negative case)
def test_wp_c3_no_download_css_on_page_without_downloads():
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

    lecture = course.chapters[0]["sequentials"][0]["verticals"][0]
    html_components = [c["content"] for c in lecture["components"] if c["type"] == "html"]
    assert not any(h.startswith("<style>") for h in html_components)


# WP-CC8
def test_wp_cc8_banner_image_registered_as_course_image_and_banner(tmp_path):
    site = WPFixtureSite()
    site.add_home(
        [(SUBJECT_URL, "1. Intro")],
        banner_url="https://ocw.tudelft.nl/wp-content/uploads/featured-Image.jpg",
    )
    site.add_static_file("featured-Image.jpg", content=b"\x89PNG\r\n\x1a\n")
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>'
        ),
    )
    site.add_lecture_page(LECTURE_URL, "<p>content</p>")
    course = site.course()
    course.parse()

    assert course.course_image_path is not None
    assert course.course_image_path.name == "featured-Image.jpg"
    assert course.banner_image_path == course.course_image_path

    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        files_xml = next(
            tar.extractfile(m).read().decode()
            for m in tar.getmembers()
            if m.name == "files.xml"
        ).encode()
        root = ET.fromstring(files_xml)

    overview_files = [
        f
        for f in root.findall("file")
        if f.findtext("component") == "course" and f.findtext("filearea") == "overviewfiles"
    ]
    # Exactly one entry, not one per course_image_path/banner_image_path field: WP registers
    # the same file under both, and a duplicate filename in one area would collide on restore.
    assert len(overview_files) == 1
    assert overview_files[0].findtext("filename") == "featured-Image.jpg"


# WP-CC8
def test_wp_cc8_no_banner_section_leaves_course_image_unset():
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

    assert course.course_image_path is None
    assert course.banner_image_path is None


# WP-CC9
def test_wp_cc9_summary_customfield_is_plain_text(tmp_path):
    site = WPFixtureSite()
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.pages[site.root] += '<article><p>My <b>cool</b> course.</p></article>'
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>'
        ),
    )
    site.add_lecture_page(LECTURE_URL, "<p>content</p>")
    course = site.course()
    course.parse()
    assert course.overview_summary_html == "<p>My <b>cool</b> course.</p>"

    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        course_xml = next(
            tar.extractfile(m).read().decode()
            for m in tar.getmembers()
            if m.name == "course/course.xml"
        )
    assert f"<shortname>summary</shortname>\n      <type>text</type>\n      <value>{esc('My cool course.')}</value>" in course_xml


_LICENSE_SECTION_HTML = (
    '<section class="license">'
    '<a rel="license" href="http://creativecommons.org/licenses/by-nc-sa/4.0/">'
    '<img alt="Creative Commons License" style="border-width:0" '
    'src="https://i.creativecommons.org/l/by-nc-sa/4.0/88x31.png"></a><br>'
    "Some attribution text.<br>"
    'Based on a work at <a href="https://ocw.tudelft.nl/courses/example/" '
    'rel="dct:source">https://ocw.tudelft.nl/courses/example/</a>.'
    "</section>"
)


# WP-CC10
def test_wp_cc10_license_banner_dropped_from_lecture_page_by_default():
    site = WPFixtureSite()
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>'
        ),
    )
    site.add_lecture_page(LECTURE_URL, f"<p>content</p>{_LICENSE_SECTION_HTML}")
    course = site.course()
    course.parse()

    vertical = course.chapters[0]["sequentials"][0]["verticals"][0]
    html = "".join(c["content"] for c in vertical["components"] if c["type"] == "html")
    assert "creativecommons.org" not in html


# WP-CC10
def test_wp_cc10_license_banner_kept_on_lecture_page_when_flag_enabled():
    site = WPFixtureSite()
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_static_file("88x31.png", content=b"\x89PNG\r\n\x1a\n")
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>'
        ),
    )
    site.add_lecture_page(LECTURE_URL, f"<p>content</p>{_LICENSE_SECTION_HTML}")
    course = site.course(include_license_banner=True)
    course.parse()

    vertical = course.chapters[0]["sequentials"][0]["verticals"][0]
    html = "".join(c["content"] for c in vertical["components"] if c["type"] == "html")
    assert "creativecommons.org" in html
    assert "/static/88x31.png" in html
    assert 'style="text-align:center;padding-top:40px;padding-bottom:40px"' in html
    assert "Based on a work at" not in html
    assert "dct:source" not in html


# WP-CC10
def test_wp_cc10_license_banner_dropped_from_reading_page_by_default():
    site = WPFixtureSite()
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--reading" href="{READING_URL}">Reading 1</a></li>'
        ),
    )
    site.add_reading_page(READING_URL, f"<p>content</p>{_LICENSE_SECTION_HTML}")
    course = site.course()
    course.parse()

    vertical = course.reading_pages[0]
    html = "".join(c["content"] for c in vertical["components"] if c["type"] == "html")
    assert "creativecommons.org" not in html


# WP-CC10
def test_wp_cc10_license_banner_kept_on_reading_page_when_flag_enabled():
    site = WPFixtureSite()
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_static_file("88x31.png", content=b"\x89PNG\r\n\x1a\n")
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--reading" href="{READING_URL}">Reading 1</a></li>'
        ),
    )
    site.add_reading_page(READING_URL, f"<p>content</p>{_LICENSE_SECTION_HTML}")
    course = site.course(include_license_banner=True)
    course.parse()

    vertical = course.reading_pages[0]
    html = "".join(c["content"] for c in vertical["components"] if c["type"] == "html")
    assert "creativecommons.org" in html
    assert "/static/88x31.png" in html
    assert 'style="text-align:center;padding-top:40px;padding-bottom:40px"' in html
    assert "Based on a work at" not in html
    assert "dct:source" not in html
