import pytest
from tests.builders import (
    Chapter,
    HtmlComponent,
    OLXFixtureBuilder,
    PdfTextbook,
    Sequential,
    StaticTab,
    Vertical,
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
