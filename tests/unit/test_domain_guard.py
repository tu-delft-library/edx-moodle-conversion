from tests.domain_guard import ALLOWED_ASSET_HOSTS, asset_hosts, foreign_asset_hosts


def test_img_src_on_a_foreign_host_is_flagged():
    html = '<img src="https://example.org/photo.jpg">'
    assert foreign_asset_hosts(html) == {"example.org"}


def test_href_on_the_same_foreign_host_is_not_flagged():
    """A plain anchor is a content link (a deliberate outbound reference), not an asset the
    converter was ever meant to fetch -- it's fine for it to point anywhere."""
    html = '<a href="https://example.org/paper.pdf">cite</a>'
    assert foreign_asset_hosts(html) == set()


def test_local_static_src_is_not_flagged():
    assert foreign_asset_hosts('<img src="/static/photo.jpg">') == set()
    assert foreign_asset_hosts('<img src="@@PLUGINFILE@@/photo.jpg">') == set()


def test_youtube_iframe_src_is_allowed():
    html = '<iframe src="https://www.youtube.com/embed/abc123"></iframe>'
    assert foreign_asset_hosts(html) == set()
    assert asset_hosts(html) == {"www.youtube.com"}


def test_collegerama_iframe_src_is_allowed():
    html = '<iframe src="https://collegerama.tudelft.nl/Mediasite/Play/abc"></iframe>'
    assert foreign_asset_hosts(html) == set()


def test_delftxdownloads_widget_iframe_src_is_flagged():
    html = (
        '<iframe src="https://delftxdownloads.tudelft.nl/_tools/dl/TUD_download_tool.php'
        '?src=ocw&amp;path=a&amp;lang=en&amp;ft=mp4"></iframe>'
    )
    assert foreign_asset_hosts(html) == {"delftxdownloads.tudelft.nl"}


def test_delftxdownloads_video_href_is_not_flagged():
    html = '<a href="https://delftxdownloads.tudelft.nl/a/b-video.mp4">High</a>'
    assert foreign_asset_hosts(html) == set()


def test_srcset_candidate_on_a_foreign_host_is_flagged():
    html = '<img src="/static/a.jpg" srcset="https://example.org/a-2x.jpg 2x, /static/a.jpg 1x">'
    assert foreign_asset_hosts(html) == {"example.org"}


def test_css_background_url_on_a_foreign_host_is_flagged():
    html = '<section style="background-image: url(\'https://example.org/bg.jpg\')"></section>'
    assert foreign_asset_hosts(html) == {"example.org"}


def test_mixed_allowed_and_foreign_hosts_only_flags_the_foreign_one():
    html = (
        '<iframe src="https://www.youtube.com/embed/abc"></iframe>'
        '<img src="https://example.org/leaked.png">'
    )
    assert foreign_asset_hosts(html) == {"example.org"}
    assert ALLOWED_ASSET_HOSTS.isdisjoint(foreign_asset_hosts(html))
