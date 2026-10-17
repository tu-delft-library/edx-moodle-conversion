import logging
import tarfile
import warnings

from bs4 import XMLParsedAsHTMLWarning

from ocw.url_audit import Hit, audit_html, audit_mbz, log_url_audit

W = "https://delftxdownloads.tudelft.nl/A/b"


def _widget(tab: str, href: str) -> str:
    return (
        f'<div class="TUD_box_download"><details class="tud-button {tab}">'
        f'<a href="{href}">x</a></details></div>'
    )


def test_widget_video_and_subtitle_links_allowed():
    assert audit_html("p", _widget("video-download", f"{W}-video.mp4")) == []
    assert audit_html("p", _widget("subtitle-download", f"{W}-video.srt")) == []


def test_widget_other_tab_external_link_flagged():
    assert audit_html("p", _widget("other-download", f"{W}-slides.pdf")) == [
        Hit("p", "<a href>", f"{W}-slides.pdf")
    ]


def test_widget_icon_left_external_flagged():
    widget = (
        '<div class="TUD_box_download"><details class="tud-button video-download">'
        f'<img src="{W}/img/icon.png"></details></div>'
    )
    assert audit_html("p", widget) == [Hit("p", "<img src>", f"{W}/img/icon.png")]


def test_delftxdownloads_link_outside_widget_flagged():
    assert audit_html("p", f'<a href="{W}-slides.pdf">s</a>')


def test_any_delftx_subdomain_flagged():
    assert audit_html("p", '<a href="https://delftxtools.tudelft.nl/DaCG#page=2">g</a>') == [
        Hit("p", "<a href>", "https://delftxtools.tudelft.nl/DaCG#page=2")
    ]
    assert audit_html("p", '<a href="https://delftxtools.tudelft.nl/map">m</a>')


def test_other_tudelft_hosts_ignored():
    assert audit_html("p", '<a href="https://ocw.tudelft.nl/courses/x/">x</a>') == []


def test_edx_jump_to_link_flagged():
    assert audit_html("p", '<a href="https://courses.edx.org/courses/x/jump_to/y">go</a>')


def test_protocol_relative_edx_url_flagged():
    assert audit_html("p", '<img src="//prod-edxapp.edx-cdn.org/assets/x.png">')


def test_edx_url_in_plain_text_flagged():
    assert audit_html("p", "<p>see https://www.edx.org/course/x</p>") == [
        Hit("p", "text", "https://www.edx.org/course/x")
    ]


def test_edx_cdn_and_docs_hosts_flagged():
    assert audit_html("p", '<img src="https://d2f1egay8yehza.cloudfront.net/x.png">')
    assert audit_html("p", '<a href="https://edx.readthedocs.io/projects/x">d</a>')
    assert audit_html("p", '<a href="http://EDX.readthedocs.org/projects/x">d</a>')


def test_tool_iframe_flagged():
    assert audit_html(
        "p",
        '<iframe src="https://delftxdownloads.tudelft.nl/_tools/dl/TUD_download_tool.php">'
        "</iframe>",
    )


def test_lookalike_host_ignored():
    assert audit_html("p", '<a href="https://notedx.org.example.com/x">x</a>') == []


def test_unrelated_host_ignored():
    assert audit_html("p", '<a href="https://example.org/paper">x</a>') == []


def _mbz(tmp_path, members: dict[str, str]):
    src = tmp_path / "src"
    out = tmp_path / "c.mbz"
    with tarfile.open(out, "w:gz") as tar:
        for name, text in members.items():
            path = src / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            tar.add(path, arcname=name)
    return out


def test_audit_mbz_skips_vidrouter_block_only(tmp_path):
    course_xml = (
        "<course><summary>&lt;a href=&quot;https://courses.edx.org/x&quot;&gt;x&lt;/a&gt;"
        "</summary><plugin_local_vidrouter_course><video>"
        "<edxvideoid>https://edx-video.net/abc.mp4</edxvideoid>"
        "</video></plugin_local_vidrouter_course></course>"
    )
    mbz = _mbz(tmp_path, {"course/course.xml": course_xml, "files/abc": "https://edx.org/bin"})

    assert audit_mbz(mbz) == [Hit("course/course.xml", "<a href>", "https://courses.edx.org/x")]


def test_log_url_audit_warns_per_hit_and_summarises(tmp_path, caplog):
    page = "&lt;a href=&quot;https://courses.edx.org/x&quot;&gt;x&lt;/a&gt;"
    mbz = _mbz(tmp_path, {"activities/page_1/page.xml": f"<page>{page}{page}</page>"})

    with caplog.at_level(logging.INFO, logger="t"):
        log_url_audit(mbz, logging.getLogger("t"))

    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (logging.WARNING, "URL AUDIT: activities/page_1/page.xml <a href> https://courses.edx.org/x"),
        (logging.WARNING, "URL AUDIT: 1 edX/DelftX URL(s) left in c.mbz"),
    ]


def test_log_url_audit_info_when_clean(tmp_path, caplog):
    mbz = _mbz(tmp_path, {"activities/page_1/page.xml": "<page>ok</page>"})

    with caplog.at_level(logging.INFO, logger="t"):
        log_url_audit(mbz, logging.getLogger("t"))

    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (logging.INFO, "URL AUDIT: 0 edX/DelftX URL(s) left in c.mbz")
    ]


def test_audit_mbz_does_not_leak_warning_filter(tmp_path):
    audit_mbz(_mbz(tmp_path, {"course/course.xml": "<course/>"}))

    assert not any(f[2] is XMLParsedAsHTMLWarning for f in warnings.filters)
