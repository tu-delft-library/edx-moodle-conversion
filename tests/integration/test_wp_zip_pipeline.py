import posixpath
import zipfile
from html.parser import HTMLParser

from ocw.converter.zip_builder import ZipBuilder
from tests.unit.test_zip_builder import _site


class _Refs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.refs.extend(v for k, v in attrs if k in ("href", "src") and v)


def _local(ref: str) -> bool:
    return not ref.startswith(("http://", "https://", "mailto:", "#"))


def test_every_local_reference_in_every_page_resolves_inside_the_zip(tmp_path):
    course = _site().course(keep_all_content=True)
    course.parse()
    out = tmp_path / "course.zip"
    ZipBuilder(course).build(out)

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        pages = [n for n in names if n.endswith(".html")]
        assert len(pages) >= 5
        for page in pages:
            parser = _Refs()
            parser.feed(zf.read(page).decode("utf-8"))
            for ref in filter(_local, parser.refs):
                target = posixpath.normpath(posixpath.join(posixpath.dirname(page), ref))
                assert target in names, f"{page} -> {ref}"


def test_zip_paths_stay_inside_the_course_folder(tmp_path):
    course = _site().course(keep_all_content=True)
    course.parse()
    out = tmp_path / "course.zip"
    ZipBuilder(course).build(out)
    with zipfile.ZipFile(out) as zf:
        assert all(n.startswith("Example_Course/") for n in zf.namelist())
        assert not any(".." in n.split("/") for n in zf.namelist())
