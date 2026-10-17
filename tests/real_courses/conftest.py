from pathlib import Path

import pytest

from tests.real_courses.courses import olx_params, wp_params

ASSET_CACHE = Path(__file__).parents[2] / ".cache" / "real_courses_assets"


def pytest_generate_tests(metafunc):
    all_courses = metafunc.config.getoption("--all-courses")
    if "root" in metafunc.fixturenames:
        metafunc.parametrize("root", olx_params(all_courses))
    if "url" in metafunc.fixturenames:
        metafunc.parametrize("url", wp_params(all_courses))


@pytest.fixture(scope="session", autouse=True)
def _real_courses_guard(request):
    if not request.config.getoption("--real-courses"):
        pytest.skip("needs --real-courses")


@pytest.fixture(scope="session")
def asset_cache():
    ASSET_CACHE.mkdir(parents=True, exist_ok=True)
    return ASSET_CACHE