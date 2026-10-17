from pathlib import Path

import pytest

ASSET_CACHE = Path(__file__).parents[2] / ".cache" / "real_courses_assets"


@pytest.fixture(scope="session", autouse=True)
def _real_courses_guard(request):
    if not request.config.getoption("--real-courses"):
        pytest.skip("needs --real-courses")


@pytest.fixture(scope="session")
def asset_cache():
    ASSET_CACHE.mkdir(parents=True, exist_ok=True)
    return ASSET_CACHE
