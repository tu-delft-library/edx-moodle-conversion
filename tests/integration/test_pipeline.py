import tarfile
import pytest

from ocw.converter import MBZBuilder
from ocw.parser import OLXCourse


#INFO: Check constructor works and generated path is valid 
def test_olxcourse_instantiates(minimal_fixture):
    course = OLXCourse(minimal_fixture)
    assert course.root == minimal_fixture

#INFO: Check that the MBZBuilder's constructor works 
def test_mbzbuilder_instantiates(minimal_fixture):
    course = OLXCourse(minimal_fixture)
    builder = MBZBuilder(course)
    assert builder.course is course


#INFO: This should not work right now 
def test_builder_raises_not_implemented(minimal_fixture, tmp_path):
    course = OLXCourse(minimal_fixture)
    builder = MBZBuilder(course)
    with pytest.raises(NotImplementedError):
        builder.build(tmp_path / "out.mbz")

#INFO: Check if builder adds all XML elements 
def test_fixture_builder_writes_files(simple_course):
    assert (simple_course / "course" / "course.xml").exists()
    assert (simple_course / "html" / "page1.html").exists()
    assert (simple_course / "video" / "vid1.xml").exists()

#INFO: Output as tar
def test_fixture_builder_as_tar(olx_builder):
    olx_builder.build()
    tar_path = olx_builder.as_tar()
    assert tarfile.is_tarfile(tar_path)
