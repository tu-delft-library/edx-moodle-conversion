import pytest

from ocw.utils import _Counter, esc, normalise_license, rewrite_static_urls, sha1_of


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


def test_normalise_license_all_rights_reserved():
    assert normalise_license("all-rights-reserved") == "alle rechten voorbehouden"


def test_normalise_license_empty_string():
    assert normalise_license("") == "alle rechten voorbehouden"


@pytest.mark.parametrize(
    "raw",
    [
        "creative-commons: ver=4.0 BY NC SA",
        "creative-commons: ver=4.0 BY SA NC",
    ],
)
def test_normalise_license_cc_token_order_independent(raw):
    """Real archives use both token orders for the same license (plan.md §4
    subagent scan) — normalise_license must land on the same canonical slug
    regardless of the order edX happened to write the tokens in."""
    assert normalise_license(raw) == "cc-by-nc-sa"
