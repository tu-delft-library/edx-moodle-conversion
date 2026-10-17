import requests

from ocw import fetcher as fetcher_module
from ocw.fetcher import AssetFetcher, HostThrottle
from ocw.parser import wp as wp_module


class _FakeResponse:
    def __init__(self, content=b"%PDF-1.4", content_type="application/pdf", status_ok=True):
        self.content = content
        self.text = content.decode()
        self.headers = {"content-type": content_type}
        self._status_ok = status_ok

    def raise_for_status(self):
        if not self._status_ok:
            raise requests.HTTPError("boom")


class _FakeSession:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        if self._exc is not None:
            raise self._exc
        return self._response


def _fetcher(tmp_path, session) -> AssetFetcher:
    fetcher = AssetFetcher(tmp_path)
    fetcher._session = session
    return fetcher


def test_unsupported_extension_returns_none_without_request(tmp_path):
    session = _FakeSession(response=_FakeResponse())
    fetcher = _fetcher(tmp_path, session)
    assert fetcher.fetch("https://x/file.mp4") is None
    assert session.calls == []


def test_pdf_fetch_writes_file_and_returns_path(tmp_path):
    session = _FakeSession(response=_FakeResponse(content=b"%PDF-data"))
    fetcher = _fetcher(tmp_path, session)
    path = fetcher.fetch("https://x/notes.pdf")
    assert path is not None
    assert path.read_bytes() == b"%PDF-data"
    assert path.parent == tmp_path


def test_mp3_fetch_expects_audio_mpeg(tmp_path):
    session = _FakeSession(response=_FakeResponse(content=b"ID3", content_type="audio/mpeg"))
    path = _fetcher(tmp_path, session).fetch("https://x/podcast.mp3")
    assert path is not None
    assert path.read_bytes() == b"ID3"


def test_fetch_result_is_cached_and_not_refetched(tmp_path):
    session = _FakeSession(response=_FakeResponse())
    fetcher = _fetcher(tmp_path, session)
    fetcher.fetch("https://x/notes.pdf")
    fetcher.fetch("https://x/notes.pdf")
    assert session.calls == ["https://x/notes.pdf"]


def test_existing_file_in_dest_dir_is_reused_without_request(tmp_path):
    (tmp_path / "notes.pdf").write_bytes(b"%PDF-old")
    session = _FakeSession(response=_FakeResponse())
    fetcher = _fetcher(tmp_path, session)
    path = fetcher.fetch("https://x/notes.pdf")
    assert path == tmp_path / "notes.pdf"
    assert path.read_bytes() == b"%PDF-old"
    assert session.calls == []


def test_name_saves_extensionless_url_and_sets_expected_type(tmp_path):
    session = _FakeSession(response=_FakeResponse(content=b"%PDF-guide"))
    fetcher = _fetcher(tmp_path, session)
    path = fetcher.fetch("https://x/DaCG", name="DaCG.pdf")
    assert path == tmp_path / "DaCG.pdf"
    assert path.read_bytes() == b"%PDF-guide"


def test_name_type_mismatch_returns_none(tmp_path):
    session = _FakeSession(response=_FakeResponse(content_type="text/html"))
    fetcher = _fetcher(tmp_path, session)
    assert fetcher.fetch("https://x/DaCG", name="DaCG.pdf") is None


def test_request_exception_returns_none_and_is_cached(tmp_path, caplog):
    session = _FakeSession(exc=requests.ConnectionError("down"))
    fetcher = _fetcher(tmp_path, session)
    with caplog.at_level("WARNING"):
        result = fetcher.fetch("https://x/notes.pdf")
    assert result is None
    assert "Failed to fetch" in caplog.text
    fetcher.fetch("https://x/notes.pdf")
    assert session.calls == ["https://x/notes.pdf"]


def test_wrong_content_type_returns_none(tmp_path, caplog):
    session = _FakeSession(response=_FakeResponse(content_type="text/html"))
    fetcher = _fetcher(tmp_path, session)
    with caplog.at_level("WARNING"):
        result = fetcher.fetch("https://x/notes.pdf")
    assert result is None
    assert "returned content-type" in caplog.text


def test_http_error_status_returns_none(tmp_path, caplog):
    session = _FakeSession(response=_FakeResponse(status_ok=False))
    fetcher = _fetcher(tmp_path, session)
    with caplog.at_level("WARNING"):
        result = fetcher.fetch("https://x/notes.pdf")
    assert result is None


def test_fetch_text_returns_page_text_and_caches(tmp_path):
    session = _FakeSession(response=_FakeResponse(content=b"<div>tool</div>", content_type="text/html"))
    fetcher = _fetcher(tmp_path, session)
    assert fetcher.fetch_text("https://x/tool.php?path=a") == "<div>tool</div>"
    fetcher.fetch_text("https://x/tool.php?path=a")
    assert session.calls == ["https://x/tool.php?path=a"]


def test_fetch_text_failure_returns_none_and_is_cached(tmp_path, caplog):
    session = _FakeSession(exc=requests.ConnectionError("down"))
    fetcher = _fetcher(tmp_path, session)
    with caplog.at_level("WARNING"):
        assert fetcher.fetch_text("https://x/tool.php") is None
    fetcher.fetch_text("https://x/tool.php")
    assert "Failed to fetch page" in caplog.text
    assert session.calls == ["https://x/tool.php"]


class _FakeClock:
    def __init__(self):
        self.now = 100.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(round(seconds, 3))
        self.now += seconds


def test_host_throttle_spaces_requests_per_host(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(fetcher_module.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(fetcher_module.time, "sleep", clock.sleep)
    throttle = HostThrottle(1.0)

    throttle.wait("https://ocw.tudelft.nl/a")
    throttle.wait("https://delftxdownloads.tudelft.nl/x.pdf")
    clock.now += 0.25
    throttle.wait("https://ocw.tudelft.nl/b")
    clock.now += 2.0
    throttle.wait("https://ocw.tudelft.nl/c")

    assert clock.sleeps == [0.75]


def test_wp_pages_and_assets_share_one_throttle():
    assert wp_module.THROTTLE is fetcher_module.THROTTLE
