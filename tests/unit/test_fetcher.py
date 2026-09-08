import requests

from ocw.fetcher import AssetFetcher


class _FakeResponse:
    def __init__(self, content=b"%PDF-1.4", content_type="application/pdf", status_ok=True):
        self.content = content
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


def test_fetch_result_is_cached_and_not_refetched(tmp_path):
    session = _FakeSession(response=_FakeResponse())
    fetcher = _fetcher(tmp_path, session)
    fetcher.fetch("https://x/notes.pdf")
    fetcher.fetch("https://x/notes.pdf")
    assert session.calls == ["https://x/notes.pdf"]


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
