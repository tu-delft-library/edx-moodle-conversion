import posixpath
import zipfile

from bs4 import BeautifulSoup
from docx import Document

from ocw.converter.zip_builder import ZipBuilder
from tests.unit.test_zip_builder import _site


def _build(tmp_path, keep_all_content: bool = True) -> zipfile.ZipFile:
    course = _site().course(keep_all_content=keep_all_content)
    course.parse()
    out = tmp_path / "course.zip"
    ZipBuilder(course).build(out)
    return zipfile.ZipFile(out)


def _relative(zf: zipfile.ZipFile) -> list[str]:
    return [n.split("/", 1)[1] for n in zf.namelist() if "/" in n]


def _read(zf: zipfile.ZipFile, relative: str) -> str:
    name = next(n for n in zf.namelist() if n.split("/", 1)[1:] == [relative])
    return zf.read(name).decode("utf-8")


# WP-ZIP1
def test_zip_has_root_index_and_chapter_index(tmp_path):
    with _build(tmp_path) as zf:
        names = _relative(zf)
        assert "index.html" in names
        assert sum(n.endswith("/index.html") for n in names) >= 1


# WP-ZIP2
def test_zip_contains_content_page_for_each_activity(tmp_path):
    with _build(tmp_path) as zf:
        names = _relative(zf)
        assert any(n.startswith("01_1._Intro/") and n.endswith("Lecture_1.html") for n in names)
        assert any(n.startswith("readings/") for n in names)


# WP-ZIP3
def test_zip_strips_scripts_and_inline_handlers(tmp_path):
    with _build(tmp_path) as zf:
        pages = [n for n in zf.namelist() if n.endswith(".html")]
        for page in pages:
            html = zf.read(page).decode("utf-8")
            assert "<script" not in html
            assert "steal()" not in html


# WP-ZIP4
def test_zip_always_includes_course_docx(tmp_path):
    with _build(tmp_path) as zf:
        assert "course.docx" in _relative(zf)
        assert "course.docx" in _read(zf, "index.html")


# WP-ZIP5
def test_keep_all_content_retains_exercise_pages(tmp_path):
    with _build(tmp_path, keep_all_content=True) as zf:
        assert "Exercise 1" in "".join(zf.read(n).decode("utf-8") for n in zf.namelist() if n.endswith(".html"))


# WP-ZIP6
def test_zip_entries_all_under_course_folder(tmp_path):
    with _build(tmp_path) as zf:
        assert all(n.startswith("Example_Course/") for n in zf.namelist())


# WP-ZIP8
def test_blacklisted_asset_and_its_references_are_dropped(tmp_path):
    with _build(tmp_path) as zf:
        names = _relative(zf)
        assert "assets/88x31.png" not in names
        assert "88x31" not in _read(zf, "01_1._Intro/01_1.1_Basics/01_Lecture_1.html")
        assert "assets/diagram.png" in names
        assert "assets/fontawesome-webfont.woff2" in names


# WP-ZIP9
def test_docx_in_zip_has_row_for_copied_local_file(tmp_path):
    with _build(tmp_path) as zf:
        docx_name = next(n for n in zf.namelist() if n.endswith("course.docx"))
        docx_bytes = zf.read(docx_name)
    docx_path = tmp_path / "course.docx"
    docx_path.write_bytes(docx_bytes)
    table = Document(docx_path).tables[0]
    rows = [[c.text for c in row.cells] for row in table.rows]
    assert any(row[0] == "diagram.png" and row[4] == "copied" for row in rows[1:])


# WP-ZIP7
def test_every_local_link_resolves(tmp_path):
    course = _site(empty_lecture=True).course(keep_all_content=True)
    course.parse()
    out = tmp_path / "course.zip"
    ZipBuilder(course).build(out)
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        for name in names:
            if not name.endswith(".html"):
                continue
            soup = BeautifulSoup(zf.read(name).decode("utf-8"), "html.parser")
            for tag in soup.find_all("a", href=True):
                href = tag["href"]
                if "://" in href or href.startswith("#"):
                    continue
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), href))
                assert target in names, f"{name} links to missing {href}"
