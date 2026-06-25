from ocw.utils import _Counter, esc, rewrite_static_urls, sha1_of


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
