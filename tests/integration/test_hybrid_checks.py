from ocw.hybrid_checks import run_hybrid_checks


def _result(olx_path, mbz_path, name):
    return next(r for r in run_hybrid_checks(olx_path, mbz_path) if r.name == name)


#NOTE: Double check that the number of high level sections in the OLX export is the same as the high level chapters in the MBZ import
def test_chapter_section_count_parity(hybrid_olx_path, hybrid_mbz_path):
    r = _result(hybrid_olx_path, hybrid_mbz_path, "chapter/section count parity")
    assert r.actual == r.expected


#NOTE: Double check that the number of sub-sections in the OLX export is the same as sub-sections in the MBZ import
def test_sequential_subsection_count_parity(hybrid_olx_path, hybrid_mbz_path):
    r = _result(hybrid_olx_path, hybrid_mbz_path, "sequential/subsection count parity")
    assert r.actual == r.expected


#NOTE: Double check that the number of html files in the OLX export (which is where content is stored)
def test_page_count_parity(hybrid_olx_path, hybrid_mbz_path):
    r = _result(hybrid_olx_path, hybrid_mbz_path, "page count parity")
    assert r.actual == r.expected
