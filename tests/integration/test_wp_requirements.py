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
    '<div id="download_tool"><div class="wpb_wrapper">'
    '<div class="TUD_box_download" data-DownloadID="Course/Week_1/Course_lec" '
    'data-YoutubeID="abc123" data-VideoType=".mp4">'
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


# WP-CC7
def test_wp_cc7_download_tool_widget_host_check_forced_rest_untouched(tmp_path):
    """The `#download_tool` widget's own bootstrap script only takes its self-contained branch
    (loads jQuery itself, then the real `TUD_download_tool.js`) when `location.href` contains
    "ocw.tudelft.nl"."""
    site = WPFixtureSite()
    site.add_home([(SUBJECT_URL, "1. Intro")])
    site.add_subject_page(
        SUBJECT_URL,
        _activities_html(
            f'<li><a class="icon icon--lecture" href="{LECTURE_URL}">Lecture 1</a></li>'
        ),
    )
    site.add_lecture_page(LECTURE_URL, f"<p>content</p>{_DOWNLOAD_TOOL_HTML}")
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
    assert esc(_TUD_HOST_CHECK) not in page_xml
    assert "if(true){" in page_xml
    assert "TUD_box_download" in page_xml
    assert "TUD_High_Video" in page_xml
    assert "icon_grey1_video_blanc_36.png" in page_xml
    assert (
        "https://delftxdownloads.tudelft.nl/download-tool/OCW/TUD_download_tool.js"
        in page_xml
    )
    assert "@@PLUGINFILE@@/TUD_download_tool.js" in page_xml
    assert esc('data-downloadid="Course/Week_1/Course_lec"') in page_xml


# WP-CC7 (negative case)
def test_wp_cc7_no_download_tool_widget_is_a_no_op():
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
    html_components = [
        c["content"] for c in lecture["components"] if c["type"] == "html"
    ]
    assert any("content" in html for html in html_components)


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
