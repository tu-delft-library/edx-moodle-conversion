import importlib.util
import io
import tarfile
import threading
from html import escape
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "link_scan", Path(__file__).resolve().parents[2] / "scripts" / "link_scan.py"
)
link_scan = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(link_scan)

NAV = '<a class="vc_general vc_btn3" href="https://ocw.tudelft.nl/course-readings/x/">Previous</a>'
NAV_PREVIEW = (
    '<a class="vc_btn3" href="https://ocw.tudelft.nl/?p=1&amp;preview=true">Next</a>'
)
TEACHER = '<a href="https://ocw.tudelft.nl/teachers/jane/">Jane</a>'
OTHER = '<a href="https://ocw.tudelft.nl/course-lectures/y/">Lecture</a>'
IMAGE = '<img src="https://ocw.tudelft.nl/wp-content/uploads/a.png">'
FOREIGN = '<a href="https://example.org/">x</a>'


def _page(body: str) -> str:
    return f"<page><content>{escape(body)}</content></page>"


def _archive(path: Path, members: dict[str, str]) -> Path:
    with tarfile.open(path, "w:gz") as tar:
        for name, xml in members.items():
            data = xml.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def _scan(tmp_path, body):
    path = _archive(tmp_path / "c.tar.gz", {"activities/page_1/page.xml": _page(body)})
    return link_scan.scan_archive(path, threading.Event())


def test_each_ocw_mention_lands_in_exactly_one_group(tmp_path):
    result = _scan(tmp_path, NAV + TEACHER + OTHER + IMAGE + FOREIGN)
    assert (result.count("nav"), result.count("teacher"), result.count("other")) == (
        1,
        1,
        2,
    )
    assert (result.pages, result.nav_pages) == (1, 1)


def test_nav_button_with_escaped_ampersand_is_still_nav(tmp_path):
    result = _scan(tmp_path, NAV_PREVIEW)
    assert (result.count("nav"), result.count("other")) == (1, 0)


def test_relative_links_are_counted_but_not_placeholders_or_other_schemes(tmp_path):
    body = (
        '<a href="/courses/x/">a</a><a href="lecture-3/">b</a><a href="/teachers/jane/">c</a>'
        '<a class="vc_btn3" href="/prev/">Previous</a><a href="@@PLUGINFILE@@/a.pdf">d</a>'
        '<a href="#top">e</a><a href="mailto:a@b.nl">f</a><a href="//cdn.example.org/x">g</a>'
    )
    result = _scan(tmp_path, body)
    assert (result.count("nav"), result.count("teacher"), result.count("other")) == (
        1,
        1,
        2,
    )


def test_lookalike_hosts_are_ignored(tmp_path):
    result = _scan(
        tmp_path, '<a href="https://xocw.tudelft.nl/a">x</a> ocw.tudelft.nlx'
    )
    assert not result.findings


def test_course_name_is_read_from_course_xml(tmp_path):
    path = _archive(
        tmp_path / "c.tar.gz",
        {"course/course.xml": "<course><fullname>Delft Design</fullname></course>"},
    )
    assert link_scan.scan_archive(path, threading.Event()).course == "Delft Design"


def test_truncated_archive_reports_error_and_does_not_raise(tmp_path):
    path = _archive(tmp_path / "c.tar.gz", {"activities/page_1/page.xml": _page(NAV)})
    path.write_bytes(path.read_bytes()[:30])
    assert link_scan.scan_archive(path, threading.Event()).error


def test_only_archives_in_the_folder_are_found(tmp_path):
    (tmp_path / "a.tar.gz").write_bytes(b"")
    (tmp_path / "b.mbz").write_bytes(b"")
    (tmp_path / "notes.txt").write_text("x")
    assert [p.name for p in link_scan.find_archives(tmp_path)] == ["a.tar.gz", "b.mbz"]


def test_missing_archive_reports_error_and_does_not_raise(tmp_path):
    assert link_scan.scan_archive(tmp_path / "gone.tar.gz", threading.Event()).error
