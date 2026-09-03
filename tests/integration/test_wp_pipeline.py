import re
import tarfile
from xml.etree import ElementTree as ET

from ocw.converter import MBZBuilder
from tests.wp_builders import WPFixtureSite


def _minimal_wp_site() -> WPFixtureSite:
    site = WPFixtureSite()
    site.add_home([(f"{site.root}subjects/1-intro/", "1. Intro")])
    site.add_subject_page(
        f"{site.root}subjects/1-intro/",
        """
        <ul class="activities">
        <li>
        <h4 class="expand expand--showing"><span class="icon fa-minus course-title">1.1 Basics</span></h4>
        <ul>
        <li><a class="icon icon--lecture" href="https://ocw.tudelft.nl/course-lectures/lec1/">Lecture 1</a></li>
        <li><a class="icon icon--reading" href="https://ocw.tudelft.nl/course-readings/read1/">Reading 1</a></li>
        </ul>
        </li>
        </ul>
        """,
    )
    site.add_lecture_page(
        "https://ocw.tudelft.nl/course-lectures/lec1/",
        '<iframe src="https://www.youtube.com/embed/abc123"></iframe>',
    )
    site.add_reading_page(
        "https://ocw.tudelft.nl/course-readings/read1/",
        '<div class="vc_download"><a class="icon fa-file" '
        'href="https://ocw.tudelft.nl/wp-content/uploads/Chapter.pdf">'
        "<strong>Chapter</strong></a></div>",
        pdf_name="Chapter.pdf",
    )
    return site


def _build(tmp_path):
    course = _minimal_wp_site().course()
    course.parse()
    out = tmp_path / "wp_course.mbz"
    MBZBuilder(course).build(out)
    return out


def test_wpcourse_produces_valid_mbz_tarball(tmp_path):
    out = _build(tmp_path)
    assert tarfile.is_tarfile(out)


def test_section_sequence_ids_have_activity_dirs(tmp_path):
    out = _build(tmp_path)
    with tarfile.open(out) as tar:
        names = set(tar.getnames())
        section_paths = [n for n in names if re.match(r"sections/section_\d+/section\.xml", n)]
        for path in section_paths:
            seq = ET.parse(tar.extractfile(path)).getroot().findtext("sequence") or ""
            for mod_id in filter(None, (s.strip() for s in seq.split(","))):
                assert any(
                    n.startswith(f"activities/page_{mod_id}/")
                    or n.startswith(f"activities/subsection_{mod_id}/")
                    or n.startswith(f"activities/resource_{mod_id}/")
                    or n.startswith(f"activities/url_{mod_id}/")
                    for n in names
                ), f"section sequence references mod {mod_id} but no matching activity dir"


def test_backup_manifest_activity_dirs_exist(tmp_path):
    out = _build(tmp_path)
    with tarfile.open(out) as tar:
        names = set(tar.getnames())
        backup = ET.parse(tar.extractfile("moodle_backup.xml")).getroot()
    for activity in backup.findall(".//contents/activities/activity"):
        d = activity.findtext("directory")
        assert any(n.startswith(d + "/") for n in names)


def test_lecture_video_becomes_vidrouter_block(tmp_path):
    out = _build(tmp_path)
    with tarfile.open(out) as tar:
        names = tar.getnames()
        page_xml = next(
            n
            for n in names
            if re.match(r"activities/page_\d+/page\.xml", n)
            and "[[vid:" in tar.extractfile(n).read().decode()
        )
    assert page_xml


def test_reading_pdf_becomes_page_with_download_box_and_file_entry(tmp_path):
    out = _build(tmp_path)
    with tarfile.open(out) as tar:
        names = set(tar.getnames())
        page_xml = next(
            n
            for n in names
            if re.match(r"activities/page_\d+/page\.xml", n)
            and "PLUGINFILE@@/Chapter.pdf" in tar.extractfile(n).read().decode()
        )
        assert page_xml
        files_xml = ET.parse(tar.extractfile("files.xml")).getroot()
        file_entry = next(
            f for f in files_xml.findall("file") if f.findtext("filename") == "Chapter.pdf"
        )
        sha1 = file_entry.findtext("contenthash")
        assert f"files/{sha1[:2]}/{sha1}" in names


def test_reading_linked_from_two_subjects_redirects_via_url_activity(tmp_path):
    site = WPFixtureSite()
    site.add_home(
        [
            (f"{site.root}subjects/1-intro/", "1. Intro"),
            (f"{site.root}subjects/2-more/", "2. More"),
        ]
    )
    for slug, name in [("1-intro", "1.1 Basics"), ("2-more", "2.1 Extra")]:
        site.add_subject_page(
            f"{site.root}subjects/{slug}/",
            f"""
            <ul class="activities">
            <li>
            <h4 class="expand expand--showing"><span class="icon fa-minus course-title">{name}</span></h4>
            <ul>
            <li><a class="icon icon--reading" href="https://ocw.tudelft.nl/course-readings/read1/">Reading 1</a></li>
            </ul>
            </li>
            </ul>
            """,
        )
    site.add_reading_page(
        "https://ocw.tudelft.nl/course-readings/read1/",
        "<p>Some descriptive reading text.</p>"
        '<div class="vc_download"><a class="icon fa-file" '
        'href="https://ocw.tudelft.nl/wp-content/uploads/Chapter.pdf">'
        "<strong>Chapter</strong></a></div>",
        pdf_name="Chapter.pdf",
    )
    course = site.course()
    course.parse()
    out = tmp_path / "wp_course.mbz"
    MBZBuilder(course).build(out)

    with tarfile.open(out) as tar:
        names = set(tar.getnames())
        page_xmls = {
            n: tar.extractfile(n).read().decode()
            for n in names
            if re.match(r"activities/page_\d+/page\.xml", n)
        }
        canonical = [
            (n, content)
            for n, content in page_xmls.items()
            if "Some descriptive reading text" in content
        ]
        assert len(canonical) == 1
        canonical_name, canonical_content = canonical[0]
        canonical_id = re.search(r"page_(\d+)/", canonical_name).group(1)
        assert "PLUGINFILE@@/Chapter.pdf" in canonical_content

        url_xmls = {
            n: tar.extractfile(n).read().decode()
            for n in names
            if re.match(r"activities/url_\d+/url\.xml", n)
        }
        link_stubs = [
            content
            for content in url_xmls.values()
            if f"$@PAGEVIEWBYID*{canonical_id}@$" in content
        ]
        assert len(link_stubs) == 2  # both subjects link, including the first occurrence
        assert all("<display>5</display>" in content for content in link_stubs)

        section_xmls = [
            tar.extractfile(n).read().decode()
            for n in names
            if re.match(r"sections/section_\d+/section\.xml", n)
        ]
        readings_sections = [s for s in section_xmls if "<name>Readings</name>" in s]
        assert len(readings_sections) == 1
        assert canonical_id in readings_sections[0]

        files_xml = ET.parse(tar.extractfile("files.xml")).getroot()
        chapter_files = [
            f for f in files_xml.findall("file") if f.findtext("filename") == "Chapter.pdf"
        ]
        assert len(chapter_files) == 1  # fetched/stored once, not once per occurrence
