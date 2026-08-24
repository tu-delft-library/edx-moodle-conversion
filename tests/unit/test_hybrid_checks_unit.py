from ocw.converter import MBZBuilder
from ocw.hybrid_checks import run_hybrid_checks
from ocw.parser.olx import Course


def test_run_hybrid_checks_all_pass_on_matching_build(minimal_fixture, tmp_path):
    course = Course(minimal_fixture)
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)

    results = run_hybrid_checks(minimal_fixture, out)

    assert len(results) == 3
    assert all(r.passed for r in results)
