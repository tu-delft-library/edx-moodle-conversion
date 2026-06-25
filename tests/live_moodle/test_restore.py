from pathlib import Path

from ocw.parser import Course
from tests.live_moodle.conftest import _ws

MINIMAL = Path(__file__).parent.parent / "fixtures" / "minimal"


def test_course_exists_after_restore(ws_session, restored_course):
    courses = _ws(ws_session, "core_course_get_courses", **{"options[ids][0]": restored_course})
    assert len(courses) == 1


def test_course_fullname(ws_session, restored_course):
    courses = _ws(ws_session, "core_course_get_courses", **{"options[ids][0]": restored_course})
    assert courses[0]["fullname"].startswith("Minimal Course")


def test_section_count_matches(ws_session, restored_course):
    c = Course(MINIMAL)
    c.parse()
    sections = _ws(ws_session, "core_course_get_contents", courseid=restored_course)
    assert len(sections) - 1 == len(c.chapters)  # section 0 is always present in Moodle


def test_section_names_match(ws_session, restored_course):
    c = Course(MINIMAL)
    c.parse()
    expected = [ch["display_name"] for ch in c.chapters]
    sections = _ws(ws_session, "core_course_get_contents", courseid=restored_course)
    actual = [s["name"] for s in sections if s["section"] > 0]
    assert actual == expected


def test_page_count_matches(ws_session, restored_course):
    c = Course(MINIMAL)
    c.parse()
    expected = sum(
        len(v["components"])
        for ch in c.chapters
        for seq in ch["sequentials"]
        for v in seq["verticals"]
    )
    sections = _ws(ws_session, "core_course_get_contents", courseid=restored_course)
    page_count = sum(
        1 for s in sections
        for mod in s.get("modules", [])
        if mod["modname"] == "page"
    )
    assert page_count == expected


def test_page_titles_match(ws_session, restored_course):
    c = Course(MINIMAL)
    c.parse()
    expected = sorted(
        comp["display_name"]
        for ch in c.chapters
        for seq in ch["sequentials"]
        for v in seq["verticals"]
        for comp in v["components"]
    )
    sections = _ws(ws_session, "core_course_get_contents", courseid=restored_course)
    actual = sorted(
        mod["name"]
        for s in sections
        for mod in s.get("modules", [])
        if mod["modname"] == "page"
    )
    assert actual == expected
