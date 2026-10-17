import tarfile
import zipfile
from xml.etree import ElementTree as ET

import pytest

from ocw.converter import MBZBuilder
from ocw.converter.zip_builder import ZipBuilder
from tests.unit.test_zip_builder import LECTURE_URL, SUBJECT_URL, _site

ZIP_ONLY_SKIPS = frozenset({"88x31.png", "featured-Image.jpg"})
DOWNLOAD_ID = "Example/Module_1/1.1_Intro"
DOWNLOAD_BOX = (
    f'<div class="wpb_raw_code"><div class="TUD_box_download" data-downloadid="{DOWNLOAD_ID}" '
    'data-youtubeid="abc123" data-videotype=".mp4"></div></div>'
)


def _parity_site():
    site = _site()
    site.add_home(
        [(SUBJECT_URL, "1. Intro")],
        banner_url="https://ocw.tudelft.nl/wp-content/uploads/featured-Image.jpg",
    )
    site.add_static_file("featured-Image.jpg", b"banner")
    site.pages[LECTURE_URL] = site.pages[LECTURE_URL].replace("</article>", f"{DOWNLOAD_BOX}</article>")
    site.add_download_tool_page(DOWNLOAD_ID)
    for name in ("1.1_Intro-slides.pdf", "icon_video_blanc_36.png", "icon_subtitles_blanc_36.png"):
        site.add_static_file(name)
    return site


def _mbz_names(path) -> set[str]:
    with tarfile.open(path) as tar:
        root = ET.parse(tar.extractfile("files.xml")).getroot()
    return {f.findtext("filename") for f in root.findall("file")} - {"."}


def _zip_names(path) -> set[str]:
    with zipfile.ZipFile(path) as zf:
        parts = [n.split("/") for n in zf.namelist() if not n.endswith("/")]
        return {p[-1] for p in parts if p[1:2] == ["assets"]}


@pytest.fixture
def shipped(tmp_path):
    site = _parity_site()
    mbz_course = site.course()
    mbz_course.parse()
    zip_course = site.course(keep_all_content=True)
    zip_course.parse()
    MBZBuilder(mbz_course).build(tmp_path / "course.mbz")
    ZipBuilder(zip_course).build(tmp_path / "course.zip")
    return _mbz_names(tmp_path / "course.mbz"), _zip_names(tmp_path / "course.zip")


def test_zip_and_mbz_ship_the_same_static_files(shipped):
    mbz_names, zip_names = shipped
    assert zip_names == mbz_names - ZIP_ONLY_SKIPS


def test_zip_only_skips_are_shipped_by_the_mbz_and_not_by_the_zip(shipped):
    mbz_names, zip_names = shipped
    assert ZIP_ONLY_SKIPS <= mbz_names
    assert not ZIP_ONLY_SKIPS & zip_names


def test_parity_site_exercises_every_asset_kind(shipped):
    mbz_names, _ = shipped
    assert {"diagram.png", "Chapter.pdf", "1.1_Intro-slides.pdf", "icon_video_blanc_36.png"} <= mbz_names
