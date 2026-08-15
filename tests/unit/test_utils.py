from ocw.utils import (
    _Counter,
    _EDX_HOST_RE,
    esc,
    rewrite_static_urls,
    sha1_of,
    warn_external_edx_urls,
)


def test_esc_encodes_html_special_chars():
    assert esc('a & <b> "c"') == "a &amp; &lt;b&gt; &quot;c&quot;"


def test_esc_returns_empty_string_for_none():
    assert esc(None) == ""


def test_rewrite_static_urls_replaces_static_prefix():
    assert (
        rewrite_static_urls('<img src="/static/x.png"/>')
        == '<img src="@@PLUGINFILE@@/x.png"/>'
    )


def test_rewrite_static_urls_no_change_when_no_match():
    assert rewrite_static_urls("<p>hello</p>") == "<p>hello</p>"


def test_sha1_of_returns_40char_hex(tmp_path):
    f = tmp_path / "f.txt"
    f.write_bytes(b"hello")
    assert len(sha1_of(f)) == 40


def test_counter_increments_from_start():
    c = _Counter(start=5)
    assert c.next() == 5
    assert c.next() == 6


def test_warn_external_edx_urls_logs_on_edx_host(caplog):
    with caplog.at_level("WARNING", logger="ocw.converter"):
        warn_external_edx_urls('<img src="https://courses.edx.org/asset-v1:x.png"/>')
    assert "still hosted on edX" in caplog.text


def test_warn_external_edx_urls_silent_on_www_edx_org():
    """www.edx.org is deliberately excluded — generic marketing/FAQ links,
    not asset dependencies (plan_2.md "Survey findings")."""
    assert _EDX_HOST_RE.findall('<a href="https://www.edx.org/about">') == []


def test_warn_external_edx_urls_silent_on_local_content(caplog):
    with caplog.at_level("WARNING", logger="ocw.converter"):
        warn_external_edx_urls('<img src="@@PLUGINFILE@@/x.png"/>')
    assert caplog.text == ""
