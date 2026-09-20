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


def _build(fixture, out, authora):
    course = Course(fixture)
    course.parse()
    MBZBuilder(course, authora=authora).build(out)


def _section_result(results):
    return next(r for r in results if r.name == "chapter/section count parity")


def test_run_hybrid_checks_passes_without_authora_when_built_without_it(minimal_fixture, tmp_path):
    out = tmp_path / "course.mbz"
    _build(minimal_fixture, out, authora=False)

    results = run_hybrid_checks(minimal_fixture, out, authora=False)

    assert all(r.passed for r in results)


def test_run_hybrid_checks_section_count_off_by_one_on_authora_mismatch(minimal_fixture, tmp_path):
    out = tmp_path / "course.mbz"
    _build(minimal_fixture, out, authora=True)

    result = _section_result(run_hybrid_checks(minimal_fixture, out, authora=False))

    assert not result.passed
    assert result.actual == result.expected + 1
