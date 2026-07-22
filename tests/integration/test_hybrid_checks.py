import tarfile
import xml.etree.ElementTree as ET

from ocw.parser import Course



def _expected_counts(olx_path):
    course = Course(olx_path)
    course.parse()
    pages = sum(
        1
        for ch in course.chapters
        for seq in ch["sequentials"]
        for vert in seq["verticals"]
        if any(c["type"] == "html" for c in vert["components"])
    )
    seqs = sum(len(ch["sequentials"]) for ch in course.chapters)
    # Adds overview page to the count if it exists
    overview = 1 if course.syllabus_html is not None else 0
    # Readings section is chapter-shaped (SECTION_XML, not CHILD_SECTION_XML)
    # in the MBZ output, so it counts toward the chapter/section total too.
    readings = 1 if course.readings else 0
    return len(course.chapters) + overview + readings, seqs, pages + overview


def _iter_section_xmls(tar):
    for m in tar.getmembers():
        if m.name.startswith("sections/") and m.name.endswith("section.xml"):
            yield ET.parse(tar.extractfile(m)).getroot()



#NOTE: Double check that the number of high level sections in the OLX export is the same as the high level chapters in the MBZ import
def test_chapter_section_count_parity(hybrid_olx_path, hybrid_mbz_path):
    expected_chapters, _, _ = _expected_counts(hybrid_olx_path)
    with tarfile.open(hybrid_mbz_path) as tar:
        actual = sum(1 for root in _iter_section_xmls(tar) if root.findtext("component") != "mod_subsection")
    assert actual == expected_chapters


#NOTE: Double check that the number of sub-sections in the OLX export is the same as sub-sections in the MBZ import
def test_sequential_subsection_count_parity(hybrid_olx_path, hybrid_mbz_path):
    _, expected_seqs, _ = _expected_counts(hybrid_olx_path)
    with tarfile.open(hybrid_mbz_path) as tar:
        actual = sum(1 for root in _iter_section_xmls(tar) if root.findtext("component") == "mod_subsection")
    assert actual == expected_seqs

#NOTE: Double check that the number of html files in the OLX export (which is where content is stored)
def test_page_count_parity(hybrid_olx_path, hybrid_mbz_path):
    _, _, expected_pages = _expected_counts(hybrid_olx_path)
    with tarfile.open(hybrid_mbz_path) as tar:
        actual = sum(1 for m in tar.getmembers() if m.name.endswith("page.xml"))
    assert actual == expected_pages
