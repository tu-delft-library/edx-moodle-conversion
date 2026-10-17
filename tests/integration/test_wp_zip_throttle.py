import posixpath
from pathlib import Path
from urllib.parse import urlparse

import pytest
import requests

from ocw.converter.zip_builder import ZipBuilder
from ocw.fetcher import _CONTENT_TYPE_BY_EXT, THROTTLE, AssetFetcher
from ocw.parser.wp import WPCourse
from tests.integration.test_wp_zip_parity import _parity_site


class _Response:
    def __init__(self, text: str = "", content: bytes = b"", content_type: str = "text/html") -> None:
        self.text = text
        self.content = content
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        pass


class _RecordingSession:
    def __init__(self, site, events: list) -> None:
        self._site = site
        self._events = events

    def get(self, url: str, timeout: float) -> _Response:
        self._events.append(("get", url))
        if url in self._site.pages:
            return _Response(text=self._site.pages[url])
        name = posixpath.basename(urlparse(url).path)
        if name in self._site.pdf_files:
            return _Response(content=self._site.pdf_files[name], content_type=_CONTENT_TYPE_BY_EXT[Path(name).suffix])
        raise requests.ConnectionError(url)


@pytest.fixture
def events(monkeypatch):
    recorded: list[tuple[str, str]] = []
    monkeypatch.setattr(THROTTLE, "wait", lambda url: recorded.append(("wait", url)))
    return recorded


def test_every_request_of_the_zip_path_waits_on_the_shared_throttle(events, tmp_path):
    site = _parity_site()
    fetcher = AssetFetcher(tmp_path / "cache")
    fetcher.dest_dir.mkdir()
    course = WPCourse(site.root, fetcher=fetcher, keep_all_content=True)
    session = _RecordingSession(site, events)
    course._session = session
    fetcher._session = session

    course.parse()
    parsed = len(events)
    ZipBuilder(course).build(tmp_path / "course.zip")

    gets = [(i, url) for i, (kind, url) in enumerate(events) if kind == "get"]
    assert gets
    assert all(i > 0 and events[i - 1] == ("wait", url) for i, url in gets)
    assert len(events) == parsed
