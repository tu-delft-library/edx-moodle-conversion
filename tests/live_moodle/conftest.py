import os
import subprocess
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

from ocw.converter import MBZBuilder
from ocw.parser import Course

load_dotenv()

MOODLE_CONTAINER = os.getenv("MOODLE_CONTAINER", "moodle-docker-webserver-1")
MINIMAL          = Path(__file__).parent.parent / "fixtures" / "minimal"


@pytest.fixture(scope="session", autouse=True)
def _moodle_guard():
    if not os.getenv("MOODLE_URL") or not os.getenv("MOODLE_TOKEN"):
        pytest.skip("MOODLE_URL / MOODLE_TOKEN not set")


def _ws(session, function, **params):
    r = session.post(f"{os.getenv('MOODLE_URL')}/webservice/rest/server.php", data={
        "wstoken": os.getenv("MOODLE_TOKEN"),
        "moodlewsrestformat": "json",
        "wsfunction": function,
        **params,
    })
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "exception" in data:
        raise RuntimeError(f"WS error: {data}")
    return data


@pytest.fixture(scope="session")
def ws_session():
    return requests.Session()


@pytest.fixture(scope="module")
def minimal_mbz(tmp_path_factory):
    out = tmp_path_factory.mktemp("live") / "course.mbz"
    course = Course(MINIMAL)
    course.parse()
    MBZBuilder(course).build(out)
    return out


@pytest.fixture(scope="module")
def restored_course(ws_session, minimal_mbz):
    """Copy MBZ into container → CLI restore → yield course_id → WS delete on teardown."""
    container_path = "/tmp/pytest_restore.mbz"
    subprocess.run(
        ["docker", "cp", str(minimal_mbz), f"{MOODLE_CONTAINER}:{container_path}"],
        check=True,
    )

    result = subprocess.run(
        ["docker", "exec", MOODLE_CONTAINER,
         "php", "admin/cli/restore_backup.php",
         f"--file={container_path}", "--categoryid=1"],
        capture_output=True, text=True,
    )
    output = result.stdout + result.stderr
    # parse "== Restored course ID: N =="
    for line in output.splitlines():
        if "Restored course ID:" in line:
            course_id = int(line.split(":")[-1].strip().rstrip("=").strip())
            break
    else:
        raise RuntimeError(f"restore failed:\n{output}")

    yield course_id

    _ws(ws_session, "core_course_delete_courses", **{"courseids[0]": str(course_id)})
