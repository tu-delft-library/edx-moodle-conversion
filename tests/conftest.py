import pytest
from pathlib import Path

from tests.builders import Chapter, HtmlComponent, OLXFixtureBuilder, Sequential, Vertical, VideoComponent

MINIMAL_FIXTURE = Path(__file__).parent / "fixtures" / "minimal"


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
