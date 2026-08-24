from ocw.converter.html import (
    CLASS_BLACKLIST,
    constrain_img_size,
    constrain_table_size,
    mark_hyperlinks_nomediaplugin,
    strip_blacklisted_classes,
    strip_templated_iframes,
    style_figcaption,
)


def test_strip_blacklisted_classes_noop_when_blacklist_empty():
    assert not CLASS_BLACKLIST
    html = '<div class="whatever">keep</div>'
    assert strip_blacklisted_classes(html) == html


def test_strip_blacklisted_classes_removes_matching_div(monkeypatch):
    monkeypatch.setattr("ocw.converter.html.CLASS_BLACKLIST", ["drop-me"])
    html = '<p>before</p><div class="a drop-me b">gone</div><p>after</p>'
    result = strip_blacklisted_classes(html)
    assert "gone" not in result
    assert "<p>before</p>" in result
    assert "<p>after</p>" in result


def test_strip_templated_iframes_drops_unresolved_placeholder():
    html = '<iframe src="https://x/%%LMS_URL%%/embed"></iframe>'
    assert strip_templated_iframes(html) == ""


def test_strip_templated_iframes_keeps_resolved_src():
    html = '<iframe src="https://x/embed/abc"></iframe>'
    assert strip_templated_iframes(html) == html


def test_constrain_img_size_adds_style_when_absent():
    html = '<img src="a.png">'
    result = constrain_img_size(html)
    assert 'style="max-width:100%;height:auto;"' in result
    assert 'src="a.png"' in result


def test_constrain_img_size_prepends_to_existing_style():
    html = '<img src="a.png" style="border:1px solid red;">'
    result = constrain_img_size(html)
    assert 'style="max-width:100%;height:auto;border:1px solid red;"' in result


def test_constrain_table_size_adds_style_when_absent():
    html = '<table border="1"><tr><td>x</td></tr></table>'
    result = constrain_table_size(html)
    assert '<table style="max-width:100%" border="1">' in result


def test_constrain_table_size_prepends_to_existing_style():
    html = '<table style="width:900px;">'
    result = constrain_table_size(html)
    assert 'style="max-width:100%;width:900px;"' in result


def test_mark_hyperlinks_nomediaplugin_adds_class_when_absent():
    html = '<a href="https://example.com/video.mp4">watch</a>'
    result = mark_hyperlinks_nomediaplugin(html)
    assert 'class="nomediaplugin"' in result


def test_mark_hyperlinks_nomediaplugin_prepends_to_existing_class():
    html = '<a href="https://x" class="external">watch</a>'
    result = mark_hyperlinks_nomediaplugin(html)
    assert 'class="nomediaplugin external"' in result


def test_style_figcaption_styles_heading_without_style():
    html = "<figcaption><h4>Caption text</h4></figcaption>"
    result = style_figcaption(html)
    assert '<h4 style="font-size:0.75em;font-weight:normal;">Caption text</h4>' in result


def test_style_figcaption_prepends_to_existing_heading_style():
    html = '<figcaption><h4 style="color:red;">Caption text</h4></figcaption>'
    result = style_figcaption(html)
    assert 'style="font-size:0.75em;font-weight:normal;color:red;"' in result


def test_style_figcaption_ignores_headings_outside_figcaption():
    html = "<h4>Not a caption</h4>"
    assert style_figcaption(html) == html
