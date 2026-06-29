import pytest
from pathlib import Path

from tests.builders import Chapter, HtmlComponent, OLXFixtureBuilder, Sequential, Vertical, VideoComponent

MINIMAL_FIXTURE = Path(__file__).parent / "fixtures" / "minimal"


def pytest_addoption(parser):
    parser.addoption("--olx-path", default=None, help="OLX directory for hybrid checks")
    parser.addoption("--mbz-path", default=None, help="MBZ file for hybrid checks")


@pytest.fixture(scope="module")
def hybrid_olx_path(request):
    p = request.config.getoption("--olx-path")
    return Path(p) if p else MINIMAL_FIXTURE


@pytest.fixture(scope="module")
def hybrid_mbz_path(request, hybrid_olx_path, tmp_path_factory):
    p = request.config.getoption("--mbz-path")
    if p:
        return Path(p)
    from ocw.converter import MBZBuilder
    from ocw.parser import Course
    out = tmp_path_factory.mktemp("hybrid") / "course.mbz"
    course = Course(hybrid_olx_path)
    course.parse()
    MBZBuilder(course).build(out)
    return out


@pytest.fixture
def minimal_fixture():
    return MINIMAL_FIXTURE


GENERATED = Path(__file__).parent / "fixtures" / "generated"

@pytest.fixture
def olx_builder():
    return OLXFixtureBuilder(GENERATED / "course")


@pytest.fixture
def simple_course(olx_builder):
    """1 chapter → 1 sequential → 1 vertical → 1 html + 1 video."""
    olx_builder.chapters = [
        Chapter("week1", "Week 1", [
            Sequential("sec1", "Section 1", [
                Vertical("unit1", "Unit 1", [
                    HtmlComponent("page1", "Page 1"),
                    VideoComponent("vid1", "Video 1"),
                ])
            ])
        ])
    ]
    return olx_builder.build()


INTRO_COURSE = Path(__file__).parent / "fixtures" / "Intro To Open edX Course.tar.gz"
CORE_COURSE  = Path(__file__).parent / "fixtures" / "Core Contributor Onboarding.tar.gz"

@pytest.fixture
def intro_course_path():
    if not INTRO_COURSE.exists():
        pytest.skip("real tarball not present")
    return INTRO_COURSE

@pytest.fixture
def core_course_path():
    if not CORE_COURSE.exists():
        pytest.skip("real tarball not present")
    return CORE_COURSE
