import tarfile

from ocw.parser import Course


def _expected_counts(olx_path):
    course = Course(olx_path)
    course.parse()
    pages = sum(
        len(vert["components"])
        for ch in course.chapters
        for seq in ch["sequentials"]
        for vert in seq["verticals"]
    )
    return len(course.chapters), pages


def test_section_count_parity(hybrid_olx_path, hybrid_mbz_path):
    expected_sections, _ = _expected_counts(hybrid_olx_path)
    with tarfile.open(hybrid_mbz_path) as tar:
        actual = sum(1 for m in tar.getmembers() if m.name.endswith("section.xml"))
    assert actual == expected_sections


def test_page_count_parity(hybrid_olx_path, hybrid_mbz_path):
    _, expected_pages = _expected_counts(hybrid_olx_path)
    with tarfile.open(hybrid_mbz_path) as tar:
        actual = sum(1 for m in tar.getmembers() if m.name.endswith("page.xml"))
    assert actual == expected_pages
