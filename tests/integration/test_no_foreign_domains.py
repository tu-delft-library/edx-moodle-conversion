"""Regression guard: nothing in a built MBZ should reference a foreign domain except inside a
plain content link (`<a href>`) or on one of the accepted video/subtitle hosts. See
`tests/domain_guard.py` for the rule and `fix_claudes_massive_fuckup.md` for why it's accepted
for those hosts specifically to stay external.

These are integration-level, end to end through the real parser + builder pipeline (not just the
pure guard-logic unit tests in `tests/unit/test_domain_guard.py`), covering both WP and OLX, so a
future asset type that forgets to fetch-and-rewrite gets caught here rather than shipped.
"""

import tarfile
import tempfile
from pathlib import Path

from tests.builders import Chapter, HtmlComponent, OLXFixtureBuilder, Sequential, Vertical, VideoComponent
from tests.domain_guard import foreign_asset_hosts
from tests.download_tool_pages import tool_page_html
from ocw.url_audit import audit_mbz, report
from tests.wp_builders import WPFixtureSite
from ocw.converter import MBZBuilder
from ocw.parser.olx import Course

SUBJECT_URL = "https://ocw.tudelft.nl/subjects/1-intro/"
LECTURE_URL = "https://ocw.tudelft.nl/course-lectures/lec1/"


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


def _all_text(mbz_path: Path) -> list[str]:
    """Every `.xml` file's content inside a built MBZ, each unescaped once to recover literal
    HTML from the XML `esc()` wrapping (see `ocw/utils.py:esc`). Skips the packaged binary
    static files themselves (images, PDFs) -- their *names* are already covered by the `files`
    directory's own XML manifest, their bytes aren't HTML to scan."""
    import html

    with tarfile.open(mbz_path) as tar:
        return [
            html.unescape(tar.extractfile(m).read().decode())
            for m in tar.getmembers()
            if m.isfile() and m.name.endswith(".xml")
        ]


def test_wp_export_has_no_foreign_asset_domains(tmp_path):
    """A WP course exercising every asset type this parser fetches (image, PDF download,
    download-widget icons and slides) plus a YouTube video and a plain content link to an
    arbitrary foreign site -- only `href`s and the accepted video hosts may reference an
    external domain by the time the MBZ is built."""
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
        (
            '<img src="https://ocw.tudelft.nl/wp-content/uploads/diagram.png">'
            '<p>See <a href="https://example.org/some-external-paper">this paper</a> for more.</p>'
            '<div class="wpb_wrapper"><div class="vc_download">'
            '<a class="icon fa-file" href="https://ocw.tudelft.nl/handouts/notes.pdf">'
            "<strong>Notes</strong>notes.pdf</a></div></div>"
            '<iframe src="https://www.youtube.com/embed/abc123"></iframe>'
            '<div class="TUD_box_download" data-downloadid="Course/Week_1/Course_lec" '
            'data-videotype=".mp4"></div>'
        ),
    )
    site.add_static_file("diagram.png", content=b"\x89PNG\r\n\x1a\n")
    site.add_static_file("notes.pdf")
    site.add_static_file("Course_lec-slides.pdf")
    site.add_static_file("icon_video_blanc_36.png", content=b"\x89PNG\r\n\x1a\n")
    site.add_static_file("icon_subtitles_blanc_36.png", content=b"\x89PNG\r\n\x1a\n")
    site.add_download_tool_page("Course/Week_1/Course_lec")
    course = site.course()
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)

    texts = _all_text(out)
    all_foreign = set()
    for text in texts:
        all_foreign |= foreign_asset_hosts(text)
    assert all_foreign == set()
    assert audit_mbz(out) == [], report(audit_mbz(out))

    # Sanity check the guard isn't vacuously true: the content link itself really did survive,
    # untouched, pointing at its original foreign host.
    assert any("https://example.org/some-external-paper" in t for t in texts)


def test_olx_export_has_no_foreign_asset_domains(tmp_path):
    """Same guarantee for OLX: a packaged `/static/` image, an absolute edX asset-v1 image
    (the one external-image shape OLX does fetch), a YouTube video, a dframe + its slide deck,
    and a plain content link to an arbitrary foreign site in the raw html component body."""
    root = tmp_path / "course"
    b = OLXFixtureBuilder(root)
    b.static_files = {"local.png": b"\x89PNG\r\n\x1a\n"}
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
                                        '<img src="/static/local.png">'
                                        '<img src="https://prod-edxapp.edx.org/'
                                        "asset-v1:DelftX+course+2021+type@asset+block@"
                                        'diagram.png">'
                                        '<p>See <a href="https://example.org/some-external-paper">'
                                        "this paper</a> for more.</p>"
                                        '<p>Read the <a href="https://support.edx.org/hc/'
                                        'en-us/sections/1-Financial-Assistance">edX help</a>.</p>'
                                        '<iframe class="dframe" data-downloadid="NGI101x-3.1">'
                                        "</iframe>"
                                    ),
                                ),
                                VideoComponent("vid1", "Video 1", youtube_id="abc123"),
                            ],
                        )
                    ],
                )
            ],
        )
    ]

    class _FakeFetcher:
        def __init__(self) -> None:
            self._dir = Path(tempfile.mkdtemp())
            self._files = {
                "diagram.png": b"fake-png",
                "NGI101x-3.1-slides.pdf": b"%PDF-1.4 fake",
                "icon_video_blanc_36.png": b"fake-png",
                "icon_subtitles_blanc_36.png": b"fake-png",
            }

        def fetch_text(self, url: str) -> str | None:
            return tool_page_html("NGI101x-3.1") if "path=NGI101x-3.1&" in url else None

        def fetch(self, url: str) -> Path | None:
            for candidate, content in self._files.items():
                if url.endswith(candidate):
                    dest = self._dir / candidate
                    dest.write_bytes(content)
                    return dest
            return None

    course = Course(b.build(), fetcher=_FakeFetcher())
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)

    texts = _all_text(out)
    all_foreign = set()
    for text in texts:
        all_foreign |= foreign_asset_hosts(text)
    assert all_foreign == set()
    assert audit_mbz(out) == [], report(audit_mbz(out))
    assert any("https://example.org/some-external-paper" in t for t in texts)
    assert any("<p>Read the edX help.</p>" in t for t in texts)
