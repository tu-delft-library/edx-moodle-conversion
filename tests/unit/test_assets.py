import pytest

from ocw.assets import asset_name, is_skipped_asset, static_refs


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('<img src="/static/a.png">', ["a.png"]),
        ('<img src="@@PLUGINFILE@@/a.png">', ["a.png"]),
        ('<a href="/static/doc.pdf#page=3">', ["doc.pdf"]),
        ('<a href="@@PLUGINFILE@@/doc.pdf?download=1">', ["doc.pdf"]),
        ("url(@@PLUGINFILE@@/font.woff2)", ["font.woff2"]),
        ("url('@@PLUGINFILE@@/font.woff')", ["font.woff"]),
        ('<img src="/static/a.png"><img src="@@PLUGINFILE@@/b.png">', ["a.png", "b.png"]),
        ('<img src="https://example.org/a.png">', []),
    ],
)
def test_static_refs_stop_at_the_file_name(html, expected):
    assert static_refs(html) == expected


def test_asset_name_replaces_unsafe_characters():
    assert asset_name("a b/c.png") == "a_b_c.png"
    assert asset_name("plain.png") == "plain.png"


def test_skipped_assets_are_the_badge_and_the_featured_image_only():
    assert is_skipped_asset("88x31.png")
    assert is_skipped_asset("featured-Image.jpg")
    assert not is_skipped_asset("Course_bundle.zip")
    assert not is_skipped_asset("ct530801.pdf")
    assert not is_skipped_asset("fontawesome-webfont.woff2")
    assert not is_skipped_asset("diagram.png")
