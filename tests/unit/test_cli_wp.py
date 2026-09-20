import pytest

from ocw.cli import wp as cli_wp


class _FakeCourse:
    def __init__(self, root, fetcher=None, include_license_banner=False):
        self.root = root
        self.fetcher = fetcher
        self.include_license_banner = include_license_banner

    def parse(self):
        pass


class _FakeBuilder:
    def __init__(
        self, course, sequential_sections=False, disable_custom_fields=False, authora=True
    ):
        self.course = course
        self.authora = authora

    def build(self, output):
        output.write_text("mbz")


@pytest.fixture(autouse=True)
def _cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)


def test_main_builds_mbz_from_site_url(monkeypatch, tmp_path):
    output = tmp_path / "out.mbz"
    monkeypatch.setattr(cli_wp, "WPCourse", _FakeCourse)
    monkeypatch.setattr(cli_wp, "MBZBuilder", _FakeBuilder)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ocw-wp",
            "https://ocw.tudelft.nl/courses/example/",
            "--output",
            str(output),
            "--no-fetch-external-assets",
        ],
    )
    cli_wp.main()
    assert list(tmp_path.glob("out_*.mbz"))


def test_main_creates_fetcher_when_enabled(monkeypatch, tmp_path):
    output = tmp_path / "out.mbz"
    seen_fetchers = []

    class _RecordingCourse(_FakeCourse):
        def __init__(self, root, fetcher=None, include_license_banner=False):
            seen_fetchers.append(fetcher)
            super().__init__(root, fetcher, include_license_banner)

    monkeypatch.setattr(cli_wp, "WPCourse", _RecordingCourse)
    monkeypatch.setattr(cli_wp, "MBZBuilder", _FakeBuilder)
    monkeypatch.setattr(
        "sys.argv", ["ocw-wp", "https://x/", "--output", str(output)]
    )
    cli_wp.main()
    assert seen_fetchers[0] is not None


def test_main_passes_include_license_banner_flag(monkeypatch, tmp_path):
    output = tmp_path / "out.mbz"
    seen = []

    class _RecordingCourse(_FakeCourse):
        def __init__(self, root, fetcher=None, include_license_banner=False):
            seen.append(include_license_banner)
            super().__init__(root, fetcher, include_license_banner)

    monkeypatch.setattr(cli_wp, "WPCourse", _RecordingCourse)
    monkeypatch.setattr(cli_wp, "MBZBuilder", _FakeBuilder)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ocw-wp",
            "https://x/",
            "--output",
            str(output),
            "--no-fetch-external-assets",
            "--include-license-banner",
        ],
    )
    cli_wp.main()
    assert seen == [True]


def test_main_exits_nonzero_and_prints_error_on_failure(monkeypatch, capsys):
    class _BoomCourse(_FakeCourse):
        def parse(self):
            raise ValueError("site unreachable")

    monkeypatch.setattr(cli_wp, "WPCourse", _BoomCourse)
    monkeypatch.setattr(cli_wp, "MBZBuilder", _FakeBuilder)
    monkeypatch.setattr(
        "sys.argv", ["ocw-wp", "https://x/", "--no-fetch-external-assets"]
    )
    with pytest.raises(SystemExit) as exc_info:
        cli_wp.main()
    assert exc_info.value.code == 1
    assert "error: site unreachable" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("extra_args", "expected"),
    [([], True), (["--authora"], True), (["--no-authora"], False)],
)
def test_main_passes_authora_flag_to_builder(monkeypatch, tmp_path, extra_args, expected):
    built = []

    class _RecordingBuilder(_FakeBuilder):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            built.append(self.authora)

    monkeypatch.setattr(cli_wp, "WPCourse", _FakeCourse)
    monkeypatch.setattr(cli_wp, "MBZBuilder", _RecordingBuilder)
    monkeypatch.setattr(
        "sys.argv",
        [
            "ocw-wp",
            "https://ocw.tudelft.nl/courses/example/",
            "--output",
            str(tmp_path / "out.mbz"),
            "--no-fetch-external-assets",
            *extra_args,
        ],
    )
    cli_wp.main()
    assert built == [expected]
