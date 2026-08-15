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
from ocw.parser import Course


def _minimal_builder(tmp_path) -> OLXFixtureBuilder:
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [Chapter("ch1", "Ch 1", [Sequential("s1", "S1", [Vertical("v1", "V1", [HtmlComponent("pg1", "Page 1")])])])]
    return b


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
