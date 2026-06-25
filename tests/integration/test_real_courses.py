import tarfile
import pytest
from pathlib import Path

from ocw.converter import MBZBuilder
from ocw.parser import Course

FIXTURES = Path(__file__).parent.parent / "fixtures"

COURSES = {
    "minimal":              FIXTURES / "minimal",
    "core_contributor_dir": FIXTURES / "1_core_contributor_course",
    "intro_dir":            FIXTURES / "2_intro_to_course",
    "core_contributor_tar": FIXTURES / "1_Core Contributor Onboarding.tar.gz",
    "intro_tar":            FIXTURES / "2_Intro To Open edX Course.tar.gz",
}


def _resolve(path: Path, tmp_path: Path) -> Path:
    if path.suffix == ".gz":
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        with tarfile.open(path) as tar:
            tar.extractall(extract_dir)
        return next(p for p in extract_dir.iterdir() if p.is_dir())
    return path


@pytest.mark.parametrize("name,path", COURSES.items())
def test_parse_course(name, path, tmp_path):
    if not path.exists():
        pytest.skip(f"{name} not present")
    course = Course(_resolve(path, tmp_path))
    course.parse()
    assert course.course_name
    assert len(course.chapters) > 0


@pytest.mark.parametrize("name,path", COURSES.items())
def test_build_course(name, path, tmp_path):
    if not path.exists():
        pytest.skip(f"{name} not present")
    course = Course(_resolve(path, tmp_path))
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        names = tar.getnames()
    assert any("section_" in n for n in names)
    assert any("page_" in n for n in names)
