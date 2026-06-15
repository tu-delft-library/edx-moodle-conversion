import tarfile

import pytest

from ocw.converter import MBZBuilder
from ocw.parser import OLXCourse


def test_olxcourse_instantiates(minimal_fixture):
    course = OLXCourse(minimal_fixture)
    assert course.root == minimal_fixture


def test_mbzbuilder_instantiates(minimal_fixture):
    course = OLXCourse(minimal_fixture)
    builder = MBZBuilder(course)
    assert builder.course is course


def test_builder_raises_not_implemented(minimal_fixture, tmp_path):
    course = OLXCourse(minimal_fixture)
    builder = MBZBuilder(course)
    with pytest.raises(NotImplementedError):
        builder.build(tmp_path / "out.mbz")


def test_fixture_builder_writes_files(simple_course):
    assert (simple_course / "course" / "course.xml").exists()
    assert (simple_course / "html" / "page1.html").exists()
    assert (simple_course / "video" / "vid1.xml").exists()


def test_fixture_builder_as_tar(olx_builder, tmp_path):
    olx_builder.build()
    tar_path = olx_builder.as_tar(tmp_path / "course.tar.gz")
    assert tarfile.is_tarfile(tar_path)
