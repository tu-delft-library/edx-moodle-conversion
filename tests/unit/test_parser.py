import pytest
from tests.builders import Chapter, HtmlComponent, OLXFixtureBuilder, Sequential, Vertical
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
