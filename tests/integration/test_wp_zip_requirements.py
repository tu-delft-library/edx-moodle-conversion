import zipfile

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
        assert any(n.startswith("01_1_Intro/") and n.endswith("Lecture_1.html") for n in names)
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
def test_zip_always_includes_external_content_docx(tmp_path):
    with _build(tmp_path) as zf:
        assert "external_content.docx" in _relative(zf)
        assert "external_content.docx" in _read(zf, "index.html")


# WP-ZIP5
def test_keep_all_content_retains_exercise_pages(tmp_path):
    with _build(tmp_path, keep_all_content=True) as zf:
        assert "Exercise 1" in "".join(zf.read(n).decode("utf-8") for n in zf.namelist() if n.endswith(".html"))


# WP-ZIP6
def test_zip_entries_all_under_course_folder(tmp_path):
    with _build(tmp_path) as zf:
        assert all(n.startswith("Example_Course/") for n in zf.namelist())
