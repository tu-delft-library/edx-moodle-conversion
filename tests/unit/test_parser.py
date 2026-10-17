from pathlib import Path
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET

import pytest
from tests.builders import (
    Chapter,
    HtmlComponent,
    OLXFixtureBuilder,
    PdfTextbook,
    Sequential,
    StaticTab,
    Vertical,
    VideoComponent,
)
from ocw.parser.olx import Course
from tests.download_tool_pages import tool_page_html


def _minimal_builder(tmp_path) -> OLXFixtureBuilder:
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [Chapter("ch1", "Ch 1", [Sequential("s1", "S1", [Vertical("v1", "V1", [HtmlComponent("pg1", "Page 1")])])])]
    return b


class _FakeFetcher:
    def __init__(self, path: Path | None):
        self._path = path
        self.calls: list[str] = []

    def fetch(self, url: str) -> Path | None:
        self.calls.append(url)
        return self._path


def test_missing_chapter_xml_raises(tmp_path):
    root = _minimal_builder(tmp_path).build()
    (root / "chapter" / "ch1.xml").unlink()
    with pytest.raises(FileNotFoundError, match="Missing Chapter XML"):
        Course(root).parse()


def test_missing_sequential_xml_raises(tmp_path):
    root = _minimal_builder(tmp_path).build()
    (root / "sequential" / "s1.xml").unlink()
    with pytest.raises(FileNotFoundError, match="Missing Sequential XML"):
        Course(root).parse()


def test_missing_vertical_xml_raises(tmp_path):
    root = _minimal_builder(tmp_path).build()
    (root / "vertical" / "v1.xml").unlink()
    with pytest.raises(FileNotFoundError, match="Missing Vertical XML"):
        Course(root).parse()


def test_missing_html_xml_raises(tmp_path):
    root = _minimal_builder(tmp_path).build()
    (root / "html" / "pg1.xml").unlink()
    with pytest.raises(FileNotFoundError, match="Missing HTML XML"):
        Course(root).parse()


@pytest.mark.parametrize("real_name,sanitized_name", [
    ("become a contributor!.png", "become_a_contributor_.png"),
    ("Congrats - Open edX intro (1080 × 608 px).png", "Congrats_-_Open_edX_intro__1080___608_px_.png"),
])
def test_static_files_indexed_by_sanitized_name(tmp_path, real_name, sanitized_name):
    """OpenEdX references static files with punctuation/spaces replaced by
    underscores in the URL, while the file on disk keeps its original name."""
    b = _minimal_builder(tmp_path)
    b.static_files = {real_name: b"fake-png-bytes"}
    course = Course(b.build())
    course.parse()
    assert course.static_files[real_name].name == real_name
    assert course.static_files[sanitized_name].name == real_name


def test_metadata_fields_populated(tmp_path):
    """org/language/license come off course.xml/run.xml attrs (plan.md §2),
    summary_html from about/short_description.html, instructors from
    policy.json's instructor_info (plan.md §1)."""
    b = _minimal_builder(tmp_path)
    b.org = "TUDelftX"
    b.language = "en"
    b.license = "creative-commons: ver=4.0 BY NC SA"
    b.summary_html = "<p>Course summary</p>"
    b.instructors = [{"name": "Dr. Jane Doe", "title": "Professor"}]
    course = Course(b.build())
    course.parse()
    assert course.org == "TUDelftX"
    assert course.language == "en"
    assert course.license == "creative-commons: ver=4.0 BY NC SA"
    assert course.summary_html == "<p>Course summary</p>"
    assert course.instructors == [{"name": "Dr. Jane Doe", "title": "Professor"}]


def test_syllabus_parsed_when_static_tab_configured(tmp_path):
    b = _minimal_builder(tmp_path)
    b.static_tabs = [StaticTab("Syllabus", "syllabus-slug")]
    b.tabs_files = {"syllabus-slug": "<p>Syllabus content</p>"}
    course = Course(b.build())
    course.parse()
    assert course.syllabus_html == "<p>Syllabus content</p>"
    assert course.syllabus_title == "Syllabus"


def test_syllabus_none_when_no_static_tab(tmp_path):
    course = Course(_minimal_builder(tmp_path).build())
    course.parse()
    assert course.syllabus_html is None


def test_syllabus_none_when_tabs_file_missing(tmp_path):
    b = _minimal_builder(tmp_path)
    b.static_tabs = [StaticTab("Syllabus", "syllabus-slug")]
    course = Course(b.build())
    course.parse()
    assert course.syllabus_html is None


def test_syllabus_none_when_static_tab_has_no_url_slug(tmp_path):
    b = _minimal_builder(tmp_path)
    b.static_tabs = [StaticTab("Syllabus", "")]
    course = Course(b.build())
    course.parse()
    assert course.syllabus_html is None


def test_readings_parsed_when_pdf_textbooks_configured(tmp_path):
    b = _minimal_builder(tmp_path)
    b.static_files = {"reading1.pdf": b"fake-pdf-bytes"}
    b.pdf_textbooks = [
        PdfTextbook("Readings", [{"title": "Reading One", "url": "/static/reading1.pdf"}])
    ]
    course = Course(b.build())
    course.parse()
    assert course.readings == [{"title": "Reading One", "name": "reading1.pdf"}]


def test_readings_flattened_across_multiple_pdf_textbooks_entries(tmp_path):
    """pdf_textbooks is schematically a list — merge every entry's chapters
    into one flat list rather than one section per entry (plan.md decision)."""
    b = _minimal_builder(tmp_path)
    b.static_files = {"a.pdf": b"a", "b.pdf": b"b"}
    b.pdf_textbooks = [
        PdfTextbook("Readings", [{"title": "A", "url": "/static/a.pdf"}]),
        PdfTextbook("Engineering Guidelines", [{"title": "B", "url": "/static/b.pdf"}]),
    ]
    course = Course(b.build())
    course.parse()
    assert course.readings == [
        {"title": "A", "name": "a.pdf"},
        {"title": "B", "name": "b.pdf"},
    ]


def test_readings_resolved_for_relative_asset_v1_url(tmp_path):
    """pdf_textbooks chapter URLs may reference assets via the relative asset-v1 form (no
    leading /static/, no http host) rather than the /static/ form — the same relative form
    rewrite_static_urls() already handles via _RELATIVE_ASSET_RE. resolve_asset_name() must
    resolve this form to the bare filename too, or a locally present PDF is wrongly reported
    as missing and the reading is dropped."""
    b = _minimal_builder(tmp_path)
    b.static_files = {"handbook.pdf": b"fake-pdf-bytes"}
    b.pdf_textbooks = [
        PdfTextbook(
            "Readings",
            [
                {
                    "title": "Handbook",
                    "url": "/asset-v1:DelftX+Course+2021+type@asset+block@handbook.pdf",
                }
            ],
        )
    ]
    course = Course(b.build())
    course.parse()
    assert course.readings == [{"title": "Handbook", "name": "handbook.pdf"}]


def test_readings_fetched_externally_when_not_packaged(tmp_path):
    b = _minimal_builder(tmp_path)
    b.pdf_textbooks = [
        PdfTextbook(
            "Readings",
            [
                {
                    "title": "Handbook",
                    "url": (
                        "https://prod-edxapp.edx.org/asset-v1:DelftX+course+2021"
                        "+type@asset+block@handbook.pdf"
                    ),
                }
            ],
        )
    ]
    fetcher = _FakeFetcher(Path("/tmp/dest/handbook.pdf"))
    course = Course(b.build(), fetcher=fetcher)
    course.parse()
    assert course.readings == [{"title": "Handbook", "name": "handbook.pdf"}]
    assert course.static_files["handbook.pdf"] == Path("/tmp/dest/handbook.pdf")
    assert fetcher.calls


def test_readings_empty_when_no_pdf_textbooks(tmp_path):
    course = Course(_minimal_builder(tmp_path).build())
    course.parse()
    assert course.readings == []


def test_readings_entry_dropped_when_pdf_missing(tmp_path, caplog):
    b = _minimal_builder(tmp_path)
    b.pdf_textbooks = [
        PdfTextbook("Readings", [{"title": "Missing", "url": "/static/missing.pdf"}])
    ]
    course = Course(b.build())
    with caplog.at_level("WARNING"):
        course.parse()
    assert course.readings == []
    assert "Missing" in caplog.text


def test_parse_video_vidkey_from_edx_video_id(tmp_path):
    """vidkey/edxvideoid mirror edx_video_id when present; youtubeid comes
    from youtube_id_1_0 (plan.md §1.3)."""
    b = _minimal_builder(tmp_path)
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
                                VideoComponent(
                                    "vid1",
                                    "Video 1",
                                    youtube_id="_tX7iFAJvZY",
                                    edx_video_id="d54b76a4-c214-49ea-a4da-161e7f8520a3",
                                )
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    course = Course(b.build())
    course.parse()
    assert len(course.videos) == 1
    video = course.videos[0]
    assert video["vidkey"] == "d54b76a4-c214-49ea-a4da-161e7f8520a3"
    assert video["edxvideoid"] == "d54b76a4-c214-49ea-a4da-161e7f8520a3"
    assert video["youtubeid"] == "_tX7iFAJvZY"
    assert video["collegeramaid"] is None
    assert video["urlname"] == "vid1"
    assert video["videopagepath"] == "Ch 1 > S1 > V1"


def test_parse_video_legacy_youtube_attribute(tmp_path):
    """youtube="1.00:{id}" is a fallback when youtube_id_1_0 is absent."""
    b = _minimal_builder(tmp_path)
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
                                VideoComponent(
                                    "vid1",
                                    "Video 1",
                                    youtube_id="_tX7iFAJvZY",
                                    legacy_youtube_attr=True,
                                )
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    course = Course(b.build())
    course.parse()
    assert course.videos[0]["youtubeid"] == "_tX7iFAJvZY"


def test_parse_video_no_source_falls_back_to_url_name(tmp_path):
    """No edx_video_id/youtube anywhere → vidkey falls back to url_name,
    youtubeid stays None (findings_video.md §4.1 pattern 3, dead-end)."""
    b = _minimal_builder(tmp_path)
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1",
                    "S1",
                    [Vertical("v1", "V1", [VideoComponent("vid1", "Video 1", youtube_id=None)])],
                )
            ],
        )
    ]
    course = Course(b.build())
    course.parse()
    video = course.videos[0]
    assert video["vidkey"] == "vid1"
    assert video["youtubeid"] is None
    assert video["edxvideoid"] is None


def test_attach_video_download_ids_paired(tmp_path):
    """One dframe + one video in the same vertical → paired positionally
    (plan.md §1.4 sibling-scan)."""
    b = _minimal_builder(tmp_path)
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
                                    content='<iframe class="dframe" data-downloadid="NGI101x-3.1"></iframe>',
                                ),
                                VideoComponent("vid1", "Video 1"),
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    course = Course(b.build())
    course.parse()
    assert course.videos[0]["tuddownloadid"] == "NGI101x-3.1"


def test_attach_video_download_ids_ambiguous_multiple_dframes(tmp_path, caplog):
    """More than one dframe candidate → ambiguous, logged, left unpaired."""
    b = _minimal_builder(tmp_path)
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
                                        '<iframe class="dframe" data-downloadid="a"></iframe>'
                                        '<iframe class="dframe" data-downloadid="b"></iframe>'
                                    ),
                                ),
                                VideoComponent("vid1", "Video 1"),
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    course = Course(b.build())
    with caplog.at_level("WARNING"):
        course.parse()
    assert course.videos[0]["tuddownloadid"] is None
    assert "Ambiguous" in caplog.text


class _ToolFetcher:
    """Serves a fake tool page per download id, and a local path for every asset."""

    def __init__(self, slides: bool = True):
        self._slides = slides
        self.text_calls: list[str] = []

    def fetch_text(self, url: str) -> str | None:
        self.text_calls.append(url)
        download_id = parse_qs(urlparse(url).query)["path"][0]
        return tool_page_html(download_id, slides=self._slides)

    def fetch(self, url: str) -> Path | None:
        return Path(f"/tmp/dest/{url.rsplit('/', 1)[-1]}")


def _dframe_course(tmp_path, content: str, videos: list[VideoComponent], fetcher) -> Course:
    b = _minimal_builder(tmp_path)
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1",
                    "S1",
                    [Vertical("v1", "V1", [HtmlComponent("pg1", "Page 1", content=content), *videos])],
                )
            ],
        )
    ]
    course = Course(b.build(), fetcher=fetcher)
    course.parse()
    return course


def _html_contents(course: Course) -> str:
    vertical = course.chapters[0]["sequentials"][0]["verticals"][0]
    return "".join(c["content"] for c in vertical["components"] if c["type"] == "html")


_DFRAME = (
    '<iframe class="dframe"\n  data-downloadid="NGI101x-3.1"\n  data-youtubeid="abc">\n</iframe>'
    '<script src="https://delftxdownloads.tudelft.nl/_tools/dl/js/builder.js"></script>'
)


def test_inline_download_tool_replaces_dframe_with_widget(tmp_path):
    """The dframe and its builder.js loader become the inlined tool page widget, with the
    "Other" tab's slides bundled locally and Video/Subtitles left on delftxdownloads."""
    fetcher = _ToolFetcher()
    course = _dframe_course(tmp_path, _DFRAME, [VideoComponent("vid1", "Video 1")], fetcher)
    html = _html_contents(course)

    assert "dframe" not in html
    assert "builder.js" not in html
    assert '<details class="tud-button tud-float other-download"' in html
    assert 'href="/static/NGI101x-3.1-slides.pdf"' in html
    assert 'href="https://delftxdownloads.tudelft.nl/NGI101x-3.1-video.mp4"' in html
    assert 'src="/static/icon_video_blanc_36.png"' in html
    assert course.static_files["NGI101x-3.1-slides.pdf"] == Path("/tmp/dest/NGI101x-3.1-slides.pdf")
    assert "src=edx&path=NGI101x-3.1&lang=en&ft=mp4&ccSA=y&ccNC=y" in fetcher.text_calls[0]
    assert course.videos[0]["tuddownloadid"] == "NGI101x-3.1"


def test_inline_download_tool_honours_dframe_data_attrs(tmp_path):
    fetcher = _ToolFetcher()
    content = (
        '<iframe class="dframe" data-downloadid="NGI101x-3.1" data-lang="nl" '
        'data-filetype="webm" data-ccSA="n" data-ccNC="n"></iframe>'
    )
    _dframe_course(tmp_path, content, [], fetcher)

    assert "lang=nl&ft=webm&ccSA=n&ccNC=n" in fetcher.text_calls[0]


def test_inline_download_tool_no_slide_deck(tmp_path):
    """Lectures without a deck get no Other tab from the tool page, so none is rendered."""
    course = _dframe_course(tmp_path, _DFRAME, [], _ToolFetcher(slides=False))
    html = _html_contents(course)

    assert "video-download" in html
    assert "other-download" not in html
    assert "Slides" not in html


def test_inline_download_tool_independent_of_ambiguous_video_pairing(tmp_path):
    """Two dframes and two videos is ambiguous for `tuddownloadid`, but both widgets are
    still inlined."""
    content = (
        '<iframe class="dframe" data-downloadid="a"></iframe>'
        '<iframe class="dframe" data-downloadid="b"></iframe>'
    )
    course = _dframe_course(
        tmp_path,
        content,
        [VideoComponent("vid1", "Video 1"), VideoComponent("vid2", "Video 2", youtube_id="other")],
        _ToolFetcher(),
    )
    html = _html_contents(course)

    assert 'href="/static/a-slides.pdf"' in html
    assert 'href="/static/b-slides.pdf"' in html
    assert course.videos[0]["tuddownloadid"] is None
    assert course.videos[1]["tuddownloadid"] is None


def test_inline_download_tool_skipped_without_fetcher(tmp_path):
    course = _dframe_course(tmp_path, _DFRAME, [], None)

    assert 'class="dframe"' in _html_contents(course)


def test_inline_download_tool_keeps_dframe_when_tool_page_unavailable(tmp_path):
    class _NoPages(_ToolFetcher):
        def fetch_text(self, url: str) -> str | None:
            return None

    course = _dframe_course(tmp_path, _DFRAME, [], _NoPages())

    assert 'class="dframe"' in _html_contents(course)


def test_course_videos_flat_list_matches_video_components(tmp_path):
    b = _minimal_builder(tmp_path)
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
                            [VideoComponent("vid1", "Video 1"), VideoComponent("vid2", "Video 2")],
                        ),
                        Vertical("v2", "V2", [HtmlComponent("pg1", "Page 1")]),
                    ],
                )
            ],
        )
    ]
    course = Course(b.build())
    course.parse()
    total_video_components = sum(
        1
        for ch in course.chapters
        for s in ch["sequentials"]
        for v in s["verticals"]
        for c in v["components"]
        if c["type"] == "video"
    )
    assert len(course.videos) == 2
    assert len(course.videos) == total_video_components


def test_missing_video_xml_raises(tmp_path):
    b = _minimal_builder(tmp_path)
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [Sequential("s1", "S1", [Vertical("v1", "V1", [VideoComponent("vid1", "Video 1")])])],
        )
    ]
    root = b.build()
    (root / "video" / "vid1.xml").unlink()
    with pytest.raises(FileNotFoundError, match="Missing Video XML"):
        Course(root).parse()


def test_blacklisted_component_tag_dropped(tmp_path, caplog):
    course = Course(tmp_path)
    el = ET.fromstring('<problem url_name="p1"/>')
    with caplog.at_level("DEBUG", logger="ocw.parser"):
        result = course._parse_component(tmp_path, el, vertical_name="V1")
    assert result is None
    assert "Skipping unsupported component type 'problem'" in caplog.text


def test_unknown_component_tag_logs_warning_and_is_dropped(tmp_path, caplog):
    course = Course(tmp_path)
    el = ET.fromstring('<some_new_xblock url_name="x1"/>')
    with caplog.at_level("WARNING"):
        result = course._parse_component(tmp_path, el, vertical_name="V1")
    assert result is None
    assert "Unhandled OLX component tag '<some_new_xblock>'" in caplog.text


def test_html_component_fetches_absolute_edx_asset(tmp_path):
    b = _minimal_builder(tmp_path)
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
                                        '<img src="https://prod-edxapp.edx.org/'
                                        "asset-v1:DelftX+course+2021+type@asset+block@"
                                        'diagram.png">'
                                    ),
                                )
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    fetcher = _FakeFetcher(Path("/tmp/dest/diagram.png"))
    course = Course(b.build(), fetcher=fetcher)
    course.parse()
    assert course.static_files["diagram.png"] == Path("/tmp/dest/diagram.png")
    assert fetcher.calls


def test_html_component_skips_already_packaged_absolute_edx_asset(tmp_path):
    b = _minimal_builder(tmp_path)
    b.static_files = {"diagram.png": b"fake-png-bytes"}
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
                                        '<img src="https://prod-edxapp.edx.org/'
                                        "asset-v1:DelftX+course+2021+type@asset+block@"
                                        'diagram.png">'
                                    ),
                                )
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    fetcher = _FakeFetcher(Path("/tmp/should-not-be-used.png"))
    course = Course(b.build(), fetcher=fetcher)
    course.parse()
    assert course.static_files["diagram.png"].name == "diagram.png"
    assert not fetcher.calls


def test_html_component_warns_when_absolute_edx_asset_unfetchable(tmp_path, caplog):
    b = _minimal_builder(tmp_path)
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
                                        '<img src="https://prod-edxapp.edx.org/'
                                        "asset-v1:DelftX+course+2021+type@asset+block@"
                                        'diagram.png">'
                                    ),
                                )
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    fetcher = _FakeFetcher(None)
    course = Course(b.build(), fetcher=fetcher)
    with caplog.at_level("WARNING"):
        course.parse()
    assert "diagram.png" not in course.static_files
    assert "Missing image 'diagram.png'" in caplog.text


class _DaCGFetcher:
    def __init__(self, available: bool = True):
        self._available = available
        self.calls: list[tuple[str, str | None]] = []

    def fetch(self, url: str, name: str | None = None) -> Path | None:
        self.calls.append((url, name))
        return Path(f"/tmp/dest/{name or url.rsplit('/', 1)[-1]}") if self._available else None


def _dacg_course(tmp_path, fetcher) -> Course:
    b = _minimal_builder(tmp_path)
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
                                    content='<a href="https://delftxtools.tudelft.nl/DaCG#page=2">'
                                    "Forum Guidelines</a>",
                                )
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    b.static_tabs = [StaticTab("Syllabus", "syllabus-slug")]
    b.tabs_files = {
        "syllabus-slug": '<a href="https://delftxtools.tudelft.nl/DaCG" target=_new>Guidelines</a>'
        '<a href="https://delftxtools.tudelft.nl/map">map</a>'
    }
    course = Course(b.build(), fetcher=fetcher)
    course.parse()
    return course


def test_dacg_bundled_once_and_links_keep_page_fragment(tmp_path):
    fetcher = _DaCGFetcher()
    course = _dacg_course(tmp_path, fetcher)

    assert _html_contents(course) == '<a href="/static/DaCG.pdf#page=2">Forum Guidelines</a>'
    assert '<a href="/static/DaCG.pdf" target=_new>Guidelines</a>' in course.syllabus_html
    assert 'href="https://delftxtools.tudelft.nl/map"' in course.syllabus_html
    assert course.static_files["DaCG.pdf"] == Path("/tmp/dest/DaCG.pdf")
    assert set(fetcher.calls) == {("https://delftxtools.tudelft.nl/DaCG", "DaCG.pdf")}


def test_dacg_links_untouched_when_unavailable(tmp_path):
    course = _dacg_course(tmp_path, _DaCGFetcher(available=False))

    assert "https://delftxtools.tudelft.nl/DaCG#page=2" in _html_contents(course)
    assert "DaCG.pdf" not in course.static_files


def test_dacg_links_untouched_without_fetcher(tmp_path):
    course = _dacg_course(tmp_path, None)

    assert "https://delftxtools.tudelft.nl/DaCG#page=2" in _html_contents(course)


_DELFTX_EXTRAS = (
    '<link rel="stylesheet" href="https://delftxdownloads.tudelft.nl/download-tool/data/'
    'edx-styles.css" type="text/css" />'
    '<a href="https://delftxdownloads.tudelft.nl/_tools/syllabus/MOOC_Forum_Guidelines.pdf">'
    "forum</a>"
    "<script src='https://delftxdownloads.tudelft.nl/_tools/dl/js/builder.js'></script>"
    '<p><input type="button" value="Verify for this course ($49)" '
    "onclick=\"window.location.href='https://ecommerce.edx.org/basket/add/?sku=F064C6D'\" /></p>"
    '<div data-block-type="video" authoring_mfe_base_url="https://course-authoring.edx.org/'
    'course/course-v1:DelftX+MECH1x+2T2025/editor" use-new-editor-video="True">v</div>'
)


def _single_page_course(tmp_path, content: str, fetcher) -> Course:
    b = _minimal_builder(tmp_path)
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [Sequential("s1", "S1", [Vertical("v1", "V1", [HtmlComponent("pg1", "P", content=content)])])],
        )
    ]
    course = Course(b.build(), fetcher=fetcher)
    course.parse()
    return course


def test_delftx_pdf_bundled_and_widget_stylesheet_dropped(tmp_path):
    course = _single_page_course(tmp_path, _DELFTX_EXTRAS, _DaCGFetcher())

    assert _html_contents(course) == (
        '<a href="/static/MOOC_Forum_Guidelines.pdf">forum</a><p></p>'
        '<div data-block-type="video" use-new-editor-video="True">v</div>'
    )
    assert course.static_files["MOOC_Forum_Guidelines.pdf"] == Path(
        "/tmp/dest/MOOC_Forum_Guidelines.pdf"
    )


def test_platform_markup_dropped_without_fetcher(tmp_path):
    html = _html_contents(_single_page_course(tmp_path, _DELFTX_EXTRAS, None))

    assert "<link" not in html
    assert "builder.js" not in html
    assert "ecommerce.edx.org" not in html
    assert "authoring_mfe_base_url" not in html
    assert "_tools/syllabus/MOOC_Forum_Guidelines.pdf" in html
