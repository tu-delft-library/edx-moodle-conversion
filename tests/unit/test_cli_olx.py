import pytest

from ocw.cli import olx as cli_olx


class _FakeCourse:
    def __init__(self, path, fetcher=None):
        self.path = path
        self.fetcher = fetcher

    def parse(self):
        pass


class _FakeBuilder:
    def __init__(self, course, sequential_sections=False, disable_custom_fields=False):
        self.course = course
        self.sequential_sections = sequential_sections
        self.disable_custom_fields = disable_custom_fields

    def build(self, output):
        output.write_text("mbz")


@pytest.fixture(autouse=True)
def _quiet_logging(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)


def test_main_builds_mbz_from_olx_directory(monkeypatch, tmp_path):
    olx_dir = tmp_path / "course"
    olx_dir.mkdir()
    output = tmp_path / "out.mbz"
    monkeypatch.setattr(cli_olx, "Course", _FakeCourse)
    monkeypatch.setattr(cli_olx, "MBZBuilder", _FakeBuilder)
    monkeypatch.setattr(cli_olx, "log_hybrid_checks", lambda *a, **k: None)
    monkeypatch.setattr(
        "sys.argv", ["ocw", str(olx_dir), "--output", str(output), "--no-fetch-external-assets"]
    )
    cli_olx.main()
    assert list(tmp_path.glob("out_*.mbz"))


def test_main_extracts_gz_archive(monkeypatch, tmp_path):
    import tarfile

    course_dir = tmp_path / "course_src" / "course"
    course_dir.mkdir(parents=True)
    (course_dir / "marker.txt").write_text("x")
    archive = tmp_path / "course.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(course_dir, arcname="course")

    seen_marker_exists = []

    class _RecordingCourse(_FakeCourse):
        def __init__(self, path, fetcher=None):
            seen_marker_exists.append((path / "marker.txt").exists())
            super().__init__(path, fetcher)

    output = tmp_path / "out.mbz"
    monkeypatch.setattr(cli_olx, "Course", _RecordingCourse)
    monkeypatch.setattr(cli_olx, "MBZBuilder", _FakeBuilder)
    monkeypatch.setattr(cli_olx, "log_hybrid_checks", lambda *a, **k: None)
    monkeypatch.setattr(
        "sys.argv", ["ocw", str(archive), "--output", str(output), "--no-fetch-external-assets"]
    )
    cli_olx.main()
    assert list(tmp_path.glob("out_*.mbz"))
    assert seen_marker_exists == [True]


def test_main_exits_nonzero_and_prints_error_on_failure(monkeypatch, tmp_path, capsys):
    olx_dir = tmp_path / "course"
    olx_dir.mkdir()

    class _BoomCourse(_FakeCourse):
        def parse(self):
            raise ValueError("bad course")

    monkeypatch.setattr(cli_olx, "Course", _BoomCourse)
    monkeypatch.setattr(cli_olx, "MBZBuilder", _FakeBuilder)
    monkeypatch.setattr(
        "sys.argv", ["ocw", str(olx_dir), "--no-fetch-external-assets"]
    )
    with pytest.raises(SystemExit) as exc_info:
        cli_olx.main()
    assert exc_info.value.code == 1
    assert "error: bad course" in capsys.readouterr().err


def test_main_creates_fetcher_when_fetch_external_assets_enabled(monkeypatch, tmp_path):
    olx_dir = tmp_path / "course"
    olx_dir.mkdir()
    output = tmp_path / "out.mbz"
    seen_fetchers = []

    class _RecordingCourse(_FakeCourse):
        def __init__(self, path, fetcher=None):
            seen_fetchers.append(fetcher)
            super().__init__(path, fetcher)

    monkeypatch.setattr(cli_olx, "Course", _RecordingCourse)
    monkeypatch.setattr(cli_olx, "MBZBuilder", _FakeBuilder)
    monkeypatch.setattr(cli_olx, "log_hybrid_checks", lambda *a, **k: None)
    monkeypatch.setattr("sys.argv", ["ocw", str(olx_dir), "--output", str(output)])
    cli_olx.main()
    assert seen_fetchers[0] is not None
