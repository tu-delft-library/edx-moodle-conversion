import zipfile

import pytest

from ocw.converter.zip_builder import ZipBuilder
from ocw.url_audit import Hit, audit_zip
from tests.unit.test_zip_builder import _site

ROOT = "Example_Course/"
PAGE = f"{ROOT}01_1._Intro/01_1.1_Basics/01_Lecture_1.html"


@pytest.fixture
def built(tmp_path):
    course = _site().course(keep_all_content=True)
    course.parse()
    out = tmp_path / "course.zip"
    ZipBuilder(course).build(out)
    return out


def _rewrite(path, changes: dict[str, str | None]):
    """Replace (or with `None` drop) members of the zip at `path`."""
    with zipfile.ZipFile(path) as zf:
        members = {n: zf.read(n) for n in zf.namelist()}
    for name, content in changes.items():
        if content is None:
            members.pop(name)
        else:
            members[name] = content.encode()
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)


def _append_to_page(path, html: str, page: str = PAGE):
    with zipfile.ZipFile(path) as zf:
        text = zf.read(page).decode()
    _rewrite(path, {page: text.replace("</body>", f"{html}</body>")})


def test_a_clean_zip_has_no_hits(built):
    assert audit_zip(built) == []


def test_ocw_link_is_flagged(built):
    _append_to_page(built, '<a href="https://ocw.tudelft.nl/teachers/x/">t</a>')
    assert Hit(PAGE, "ocw link <a href>", "https://ocw.tudelft.nl/teachers/x/") in audit_zip(built)


def test_ocw_image_and_subdomain_are_flagged(built):
    _append_to_page(
        built, '<img src="https://static.ocw.tudelft.nl/a.png"><img srcset="https://ocw.tudelft.nl/b.png 2x">'
    )
    urls = {h.url for h in audit_zip(built) if h.element.startswith("ocw link")}
    assert urls == {"https://static.ocw.tudelft.nl/a.png", "https://ocw.tudelft.nl/b.png"}


def test_broken_relative_link_is_flagged(built):
    _append_to_page(built, '<a href="../../assets/missing.pdf">m</a><img src="gone.png">')
    broken = {h.url for h in audit_zip(built) if h.element.startswith("broken link")}
    assert broken == {"../../assets/missing.pdf", "gone.png"}


def test_relative_link_with_fragment_and_query_resolves(built):
    _append_to_page(built, '<a href="../../assets/Chapter.pdf#page=3">p</a><a href="../../index.html?x=1">i</a>')
    assert audit_zip(built) == []


def test_fragment_only_and_mailto_links_are_ignored(built):
    _append_to_page(built, '<a href="#top">t</a><a href="mailto:a@b.nl">m</a>')
    assert audit_zip(built) == []


def test_external_url_missing_from_the_table_is_flagged(built):
    _append_to_page(built, '<a href="https://example.org/new">n</a>')
    assert Hit(PAGE, "missing from table", "https://example.org/new") in audit_zip(built)


def test_table_url_not_on_any_page_is_flagged(built):
    _rewrite(built, {PAGE: "<html><body>emptied</body></html>"})
    hits = audit_zip(built)
    assert Hit("external_content.xlsx", "not on any page", "https://www.youtube.com/embed/abc123") in hits


def test_unreferenced_asset_is_flagged(built):
    with zipfile.ZipFile(built, "a") as zf:
        zf.writestr(f"{ROOT}assets/stray.png", b"x")
    assert Hit(f"{ROOT}assets/stray.png", "orphan asset", "stray.png") in audit_zip(built)


def test_asset_used_only_from_a_style_block_is_not_an_orphan(built):
    with zipfile.ZipFile(built, "a") as zf:
        zf.writestr(f"{ROOT}assets/icons.woff2", b"x")
    _append_to_page(built, "<style>@font-face{src:url(../../assets/icons.woff2)}</style>")
    assert audit_zip(built) == []
