import pytest

from ocw.cli import wp_zip


class _FakeCourse:
    instances: list = []

    def __init__(self, root, fetcher=None, keep_all_content=False):
        self.root = root
        self.fetcher = fetcher
        self.keep_all_content = keep_all_content
        _FakeCourse.instances.append(self)

    def parse(self):
        pass


class _FakeBuilder:
    def __init__(self, course):
        self.course = course

    def build(self, output):
        output.write_text("zip")


@pytest.fixture(autouse=True)
def _cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    _FakeCourse.instances = []


def test_main_builds_zip_from_site_url(monkeypatch, tmp_path):
    monkeypatch.setattr(wp_zip, "WPCourse", _FakeCourse)
    monkeypatch.setattr(wp_zip, "ZipBuilder", _FakeBuilder)
    monkeypatch.setattr(
        "sys.argv",
        ["ocw-wp-zip", "https://ocw.tudelft.nl/courses/example/", "-o", str(tmp_path / "out.zip")],
    )
    wp_zip.main()
    assert list(tmp_path.glob("out_*.zip"))


def test_main_parses_with_all_content_and_a_fetcher(monkeypatch, tmp_path):
    monkeypatch.setattr(wp_zip, "WPCourse", _FakeCourse)
    monkeypatch.setattr(wp_zip, "ZipBuilder", _FakeBuilder)
    monkeypatch.setattr(
        "sys.argv",
        ["ocw-wp-zip", "https://ocw.tudelft.nl/courses/example/", "-o", str(tmp_path / "o.zip")],
    )
    wp_zip.main()
    course = _FakeCourse.instances[0]
    assert course.keep_all_content is True
    assert course.fetcher is not None


def test_main_exits_1_on_error(monkeypatch, tmp_path, capsys):
    class _Boom(_FakeCourse):
        def parse(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(wp_zip, "WPCourse", _Boom)
    monkeypatch.setattr("sys.argv", ["ocw-wp-zip", "https://x/", "-o", str(tmp_path / "o.zip")])
    with pytest.raises(SystemExit) as exc:
        wp_zip.main()
    assert exc.value.code == 1
    assert "boom" in capsys.readouterr().err
