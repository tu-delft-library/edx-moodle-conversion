import re
import tarfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from ocw.converter import MBZBuilder
from ocw.parser.olx import Course
from tests.builders import (
    Chapter,
    HtmlComponent,
    OLXFixtureBuilder,
    PdfTextbook,
    Sequential,
    StaticTab,
    Vertical,
)

MINIMAL = Path(__file__).parent.parent / "fixtures" / "minimal"


def _get_backup_xml(tmp_path, **builder_kwargs) -> ET.Element:
    course = Course(MINIMAL)
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course, **builder_kwargs).build(out)
    with tarfile.open(out) as tar:
        return ET.parse(tar.extractfile("moodle_backup.xml")).getroot()


def _get_course_xml(tmp_path, **builder_kwargs) -> ET.Element:
    course = Course(MINIMAL)
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course, **builder_kwargs).build(out)
    with tarfile.open(out) as tar:
        return ET.parse(tar.extractfile("course/course.xml")).getroot()


def test_details_block_present(tmp_path):
    detail = _get_backup_xml(tmp_path).find(".//details/detail")
    assert detail is not None
    assert detail.findtext("type") == "course"
    assert detail.findtext("format") == "moodle2"


def test_required_metadata_fields(tmp_path):
    info = _get_backup_xml(tmp_path).find("information")
    for field in (
        "moodle_version",
        "backup_version",
        "backup_release",
        "backup_date",
        "original_course_format",
        "original_course_contextid",
        "original_system_contextid",
    ):
        assert info.findtext(field) is not None, f"missing {field}"


def test_root_settings_present(tmp_path):
    names = {
        s.findtext("name")
        for s in _get_backup_xml(tmp_path).findall(".//settings/setting")
    }
    for required in ("activities", "blocks", "users", "filters"):
        assert required in names


def test_files_setting_present_when_authora(tmp_path):
    names = {
        s.findtext("name")
        for s in _get_backup_xml(tmp_path, authora=True).findall(".//settings/setting")
        if s.findtext("level") == "root"
    }
    assert "files" in names


def test_files_setting_absent_without_authora(tmp_path):
    names = {
        s.findtext("name")
        for s in _get_backup_xml(tmp_path, authora=False).findall(".//settings/setting")
        if s.findtext("level") == "root"
    }
    assert "files" not in names


def test_section_settings_generated(tmp_path):
    section_settings = [
        s
        for s in _get_backup_xml(tmp_path).findall(".//settings/setting")
        if s.findtext("level") == "section"
    ]
    assert len(section_settings) > 0
    names = {s.findtext("name") for s in section_settings}
    assert any("_included" in n for n in names)
    assert any("_userinfo" in n for n in names)


def test_activity_settings_generated(tmp_path):
    activity_settings = [
        s
        for s in _get_backup_xml(tmp_path).findall(".//settings/setting")
        if s.findtext("level") == "activity"
    ]
    assert len(activity_settings) > 0
    names = {s.findtext("name") for s in activity_settings}
    assert any("page_" in n and "_included" in n for n in names)


def test_empty_course_still_valid(tmp_path):
    b = OLXFixtureBuilder(tmp_path / "course")
    course = Course(b.build())
    course.parse()
    out = tmp_path / "course.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        xml = ET.parse(tar.extractfile("moodle_backup.xml")).getroot()
    assert xml.find(".//details/detail") is not None
    assert [
        s
        for s in xml.findall(".//settings/setting")
        if s.findtext("level") == "activity"
    ] == []


# ── module-scoped fixtures ────────────────────────────────────────────────────

_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(scope="module")
def mbz(tmp_path_factory):
    out = tmp_path_factory.mktemp("bu") / "course.mbz"
    course = Course(MINIMAL)
    course.parse()
    MBZBuilder(course).build(out)
    return out


@pytest.fixture(scope="module")
def mbz_names(mbz):
    with tarfile.open(mbz) as tar:
        return set(tar.getnames())


@pytest.fixture(scope="module")
def file_mbz(tmp_path_factory):
    root = tmp_path_factory.mktemp("fmbz")
    b = OLXFixtureBuilder(root / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1",
                    "S1",
                    [
                        Vertical(
                            "v1",
                            "V1",
                            [
                                HtmlComponent(
                                    "pg1",
                                    "Page 1",
                                    content='<img src="/static/test.png"/>',
                                ),
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    b.static_files = {"test.png": _PNG}
    course = Course(b.build())
    course.parse()
    out = root / "out.mbz"
    MBZBuilder(course).build(out)
    return out


def _parse(mbz_path, entry):
    with tarfile.open(mbz_path) as tar:
        return ET.parse(tar.extractfile(entry)).getroot()


# ── A: required file existence ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "moodle_backup.xml",
        "course/course.xml",
        "course/inforef.xml",
        "roles.xml",
        "gradebook.xml",
        "grade_history.xml",
        "groups.xml",
        "outcomes.xml",
        "questions.xml",
        "scales.xml",
        "files.xml",
    ],
)
def test_required_root_file_exists(mbz_names, path):
    assert path in mbz_names


@pytest.mark.parametrize(
    "filename",
    [
        "page.xml",
        "module.xml",
        "inforef.xml",
        "grades.xml",
        "grade_history.xml",
        "roles.xml",
        "filters.xml",
    ],
)
def test_activity_dir_has_file(mbz_names, filename):
    act_dirs = {
        n.rsplit("/", 1)[0]
        for n in mbz_names
        if re.match(r"activities/page_\d+/.+\.xml", n)
    }
    assert act_dirs, "no activity dirs found"
    for d in act_dirs:
        assert f"{d}/{filename}" in mbz_names


@pytest.mark.parametrize("filename", ["section.xml", "inforef.xml"])
def test_section_dir_has_file(mbz_names, filename):
    sec_dirs = {
        n.rsplit("/", 1)[0]
        for n in mbz_names
        if re.match(r"sections/section_\d+/.+\.xml", n)
    }
    assert sec_dirs, "no section dirs found"
    for d in sec_dirs:
        assert f"{d}/{filename}" in mbz_names


# ── B: XML field presence ─────────────────────────────────────────────────────

_SECTION_FIELDS = frozenset(
    {
        "number",
        "name",
        "summary",
        "summaryformat",
        "sequence",
        "visible",
        "availabilityjson",
        "timemodified",
    }
)
_MODULE_FIELDS = frozenset(
    {
        "modulename",
        "sectionid",
        "sectionnumber",
        "idnumber",
        "added",
        "score",
        "indent",
        "visible",
        "visibleoncoursepage",
        "visibleold",
        "groupmode",
        "groupingid",
        "completion",
        "completiongradeitemnumber",
        "completionpassgrade",
        "completionview",
        "completionexpected",
        "availability",
        "showdescription",
        "tags",
    }
)
_PAGE_FIELDS = frozenset(
    {
        "name",
        "intro",
        "introformat",
        "content",
        "contentformat",
        "legacyfiles",
        "legacyfileslast",
        "display",
        "displayoptions",
        "revision",
        "timemodified",
    }
)
_COURSE_FIELDS = frozenset(
    {
        "shortname",
        "fullname",
        "idnumber",
        "summary",
        "summaryformat",
        "format",
        "showgrades",
        "newsitems",
        "startdate",
        "enddate",
        "marker",
        "maxbytes",
        "legacyfiles",
        "showreports",
        "visible",
        "groupmode",
        "groupmodeforce",
        "defaultgroupingid",
        "lang",
        "theme",
        "timecreated",
        "timemodified",
        "requested",
        "enablecompletion",
        "completionnotify",
        "hiddensections",
        "coursedisplay",
        "category",
        "tags",
        "customfields",
    }
)


@pytest.mark.parametrize(
    "pattern,fields,nested_under",
    [
        (r"sections/section_\d+/section\.xml", _SECTION_FIELDS, None),
        (r"activities/page_\d+/module\.xml", _MODULE_FIELDS, None),
        (r"activities/page_\d+/page\.xml", _PAGE_FIELDS, "page"),
    ],
)
def test_xml_required_fields_present(mbz, mbz_names, pattern, fields, nested_under):
    paths = [n for n in mbz_names if re.match(pattern, n)]
    assert paths
    for path in paths:
        root = _parse(mbz, path)
        el = root.find(nested_under) if nested_under else root
        missing = fields - {child.tag for child in el}
        assert not missing, f"{path} missing: {missing}"


def test_course_xml_required_fields(mbz):
    root = _parse(mbz, "course/course.xml")
    missing = _COURSE_FIELDS - {child.tag for child in root}
    assert not missing, f"course/course.xml missing: {missing}"


# ── C: semantic values ────────────────────────────────────────────────────────


def test_section_availabilityjson_null_sentinel(mbz, mbz_names):
    for path in [
        n for n in mbz_names if re.match(r"sections/section_\d+/section\.xml", n)
    ]:
        assert _parse(mbz, path).findtext("availabilityjson") == "$@NULL@$"


def test_page_display_is_5(mbz, mbz_names):
    for path in [n for n in mbz_names if re.match(r"activities/page_\d+/page\.xml", n)]:
        assert _parse(mbz, path).find("page").findtext("display") == "5"


def test_page_displayoptions_exact_php(mbz, mbz_names):
    expected = 'a:1:{s:10:"printintro";s:1:"0";}'
    for path in [n for n in mbz_names if re.match(r"activities/page_\d+/page\.xml", n)]:
        val = _parse(mbz, path).find("page").findtext("displayoptions")
        assert val == expected, f"{path}: {val!r}"


def test_course_format_topics(tmp_path):
    assert _get_course_xml(tmp_path, authora=False).findtext("format") == "topics"


def test_format_is_multitabs_when_authora(tmp_path):
    assert _get_course_xml(tmp_path, authora=True).findtext("format") == "multitabs"


def test_original_course_format_matches_authora_flag(tmp_path):
    assert (
        _get_backup_xml(tmp_path, authora=True).findtext(".//original_course_format")
        == "multitabs"
    )
    assert (
        _get_backup_xml(tmp_path, authora=False).findtext(".//original_course_format")
        == "topics"
    )


def test_courseformatoptions_present_when_authora(tmp_path):
    root = _get_course_xml(tmp_path, authora=True)
    options = {
        o.findtext("name"): o.findtext("value")
        for o in root.findall(".//courseformatoptions/courseformatoption")
    }
    assert options["sectionname_as_header"] == "1"
    assert options["modview"] == "list"
    assert options["tilesperrow"] == "3"
    assert len(options) == 21
    assert "laststructurechange" not in options and "visibleold" not in options
    assert all(
        o.findtext("format") == "multitabs"
        for o in root.findall(".//courseformatoption")
    )


def test_courseformatoptions_absent_without_authora(tmp_path):
    assert _get_course_xml(tmp_path, authora=False).find("courseformatoptions") is None


def test_idnumber_format_option_is_empty_string(tmp_path):
    root = _get_course_xml(tmp_path, authora=True)
    option = next(
        o
        for o in root.findall(".//courseformatoption")
        if o.findtext("name") == "idnumber"
    )
    assert option.findtext("value") == ""


def test_plugin_format_multitabs_present_when_authora(tmp_path):
    root = _get_course_xml(tmp_path, authora=True)
    assert root.find("plugin_format_multitabs_course") is not None
    assert root.find("plugin_format_multitabs_course/multitabs/taggroups") is not None


def test_plugin_format_multitabs_absent_without_authora(tmp_path):
    assert (
        _get_course_xml(tmp_path, authora=False).find("plugin_format_multitabs_course")
        is None
    )


def test_course_idnumber_matches_shortname(mbz):
    course = _parse(mbz, "course/course.xml")
    assert course.findtext("idnumber") == course.findtext("shortname")


@pytest.fixture(scope="module")
def spaced_mbz(tmp_path_factory):
    root = tmp_path_factory.mktemp("smbz")
    b = OLXFixtureBuilder(root / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1",
                    "S1",
                    [
                        Vertical(
                            "v1",
                            "V1",
                            [
                                HtmlComponent(
                                    "pg1",
                                    "Page 1",
                                    content='<img src="/static/my_image.png"/>',
                                ),
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    b.static_files = {"my image.png": _PNG}
    course = Course(b.build())
    course.parse()
    out = root / "out.mbz"
    MBZBuilder(course).build(out)
    return out


def test_space_filename_image_included(spaced_mbz):
    root = _parse(spaced_mbz, "files.xml")
    names = [f.findtext("filename") for f in root.findall("file")]
    assert "my_image.png" in names


@pytest.fixture(scope="module")
def punctuation_mbz(tmp_path_factory):
    root = tmp_path_factory.mktemp("pmbz")
    b = OLXFixtureBuilder(root / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1",
                    "S1",
                    [
                        Vertical(
                            "v1",
                            "V1",
                            [
                                HtmlComponent(
                                    "pg1",
                                    "Page 1",
                                    content='<img src="/static/become_a_contributor_.png"/>',
                                ),
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    b.static_files = {"become a contributor!.png": _PNG}
    course = Course(b.build())
    course.parse()
    out = root / "out.mbz"
    MBZBuilder(course).build(out)
    return out


def test_punctuation_filename_image_included(punctuation_mbz):
    root = _parse(punctuation_mbz, "files.xml")
    names = [f.findtext("filename") for f in root.findall("file")]
    assert "become_a_contributor_.png" in names


def test_mediaplugin_filter_disabled(mbz):
    root = _parse(mbz, "course/filters.xml")
    actives = {
        fa.findtext("filter"): fa.findtext("active")
        for fa in root.findall(".//filter_active")
    }
    assert actives.get("mediaplugin") == "-1"


# ── course thumbnail: overviewfiles + Overview section embed (authora-gated) ──


def _course_image_builder(root):
    b = OLXFixtureBuilder(root / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1",
                    "S1",
                    [
                        Vertical(
                            "v1",
                            "V1",
                            [
                                HtmlComponent("pg1", "Page 1"),
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    b.static_files = {"thumb.png": _PNG}
    b.course_image = "/static/thumb.png"
    return b


def _course_image_mbz(tmp_path, **builder_kwargs) -> Path:
    course = Course(_course_image_builder(tmp_path).build())
    course.parse()
    out = tmp_path / "out.mbz"
    MBZBuilder(course, **builder_kwargs).build(out)
    return out


def _overview_section_id(mbz_path) -> str:
    return next(
        s for s in _section_xmls(mbz_path) if s.findtext("name") == "Overview"
    ).get("id")


def test_overviewfiles_placeholder_present_when_authora(tmp_path):
    mbz = _course_image_mbz(tmp_path, authora=True)
    root = _parse(mbz, "files.xml")
    overviewfiles = [
        f for f in root.findall("file") if f.findtext("filearea") == "overviewfiles"
    ]
    assert {f.findtext("filename") for f in overviewfiles} == {"thumb.png", "."}
    placeholder = next(f for f in overviewfiles if f.findtext("filename") == ".")
    assert (
        placeholder.findtext("contenthash")
        == "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    )
    assert placeholder.findtext("filesize") == "0"


def test_overviewfiles_placeholder_absent_without_authora(tmp_path):
    mbz = _course_image_mbz(tmp_path, authora=False)
    root = _parse(mbz, "files.xml")
    overviewfiles = [
        f for f in root.findall("file") if f.findtext("filearea") == "overviewfiles"
    ]
    assert {f.findtext("filename") for f in overviewfiles} == {"thumb.png"}


def test_overview_section_embeds_thumbnail_when_authora(tmp_path):
    mbz = _course_image_mbz(tmp_path, authora=True)
    overview_id = _overview_section_id(mbz)
    section = _parse(mbz, f"sections/section_{overview_id}/section.xml")
    assert "@@PLUGINFILE@@/thumb.png" in (section.findtext("summary") or "")


def test_overview_section_unchanged_without_authora(tmp_path):
    mbz = _course_image_mbz(tmp_path, authora=False)
    overview_id = _overview_section_id(mbz)
    section = _parse(mbz, f"sections/section_{overview_id}/section.xml")
    assert "@@PLUGINFILE@@" not in (section.findtext("summary") or "")


def test_section_filearea_entries_and_own_inforef_when_authora(tmp_path):
    mbz = _course_image_mbz(tmp_path, authora=True)
    overview_id = _overview_section_id(mbz)
    files_root = _parse(mbz, "files.xml")
    section_entries = [
        f
        for f in files_root.findall("file")
        if f.findtext("filearea") == "section" and f.findtext("itemid") == overview_id
    ]
    assert {f.findtext("filename") for f in section_entries} == {"thumb.png", "."}
    placeholder = next(f for f in section_entries if f.findtext("filename") == ".")
    assert (
        placeholder.findtext("contenthash")
        == "da39a3ee5e6b4b0d3255bfef95601890afd80709"
    )

    inforef = _parse(mbz, f"sections/section_{overview_id}/inforef.xml")
    inforef_ids = {f.findtext("id") for f in inforef.findall(".//fileref/file")}
    assert inforef_ids == {f.get("id") for f in section_entries}


def test_section_filearea_entries_absent_without_authora(tmp_path):
    mbz = _course_image_mbz(tmp_path, authora=False)
    files_root = _parse(mbz, "files.xml")
    assert not [
        f for f in files_root.findall("file") if f.findtext("filearea") == "section"
    ]


def test_course_inforef_scoped_to_overviewfiles_not_section(tmp_path):
    mbz = _course_image_mbz(tmp_path, authora=True)
    files_root = _parse(mbz, "files.xml")
    overviewfiles_ids = {
        f.get("id")
        for f in files_root.findall("file")
        if f.findtext("filearea") == "overviewfiles"
    }
    course_inforef = _parse(mbz, "course/inforef.xml")
    course_inforef_ids = {
        f.findtext("id") for f in course_inforef.findall(".//fileref/file")
    }
    assert course_inforef_ids == overviewfiles_ids


def test_placeholder_entries_not_copied_to_disk(tmp_path):
    mbz = _course_image_mbz(tmp_path, authora=True)
    with tarfile.open(mbz) as tar:
        names = set(tar.getnames())
    assert "files/da/da39a3ee5e6b4b0d3255bfef95601890afd80709" not in names


def test_distinct_banner_image_not_written_to_overviewfiles(tmp_path):
    """A separate banner_image must never land in overviewfiles alongside course_image:

    Moodle's get_course_overviewfiles() sorts that area by filename and keeps only
    courseoverviewfileslimit files."""
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1",
                    "S1",
                    [
                        Vertical(
                            "v1",
                            "V1",
                            [
                                HtmlComponent("pg1", "Page 1"),
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    b.static_files = {"thumb.png": _PNG, "banner.png": _PNG}
    b.course_image = "/static/thumb.png"
    b.banner_image = "/static/banner.png"
    course = Course(b.build())
    course.parse()
    out = tmp_path / "out.mbz"
    MBZBuilder(course, authora=True).build(out)
    files_root = _parse(out, "files.xml")
    overviewfiles = [
        f
        for f in files_root.findall("file")
        if f.findtext("filearea") == "overviewfiles"
    ]
    assert {f.findtext("filename") for f in overviewfiles} == {"thumb.png", "."}


def test_no_section_embed_without_course_image(tmp_path):
    """An authora course with no course_image/banner_image (e.g. a wp course with
    no scraped hero image) gets no section-area entries and no summary change."""
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1",
                    "S1",
                    [
                        Vertical(
                            "v1",
                            "V1",
                            [
                                HtmlComponent("pg1", "Page 1"),
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    course = Course(b.build())
    course.parse()
    out = tmp_path / "out.mbz"
    MBZBuilder(course, authora=True).build(out)
    files_root = _parse(out, "files.xml")
    assert not [
        f for f in files_root.findall("file") if f.findtext("filearea") == "section"
    ]
    overview_id = _overview_section_id(out)
    section = _parse(out, f"sections/section_{overview_id}/section.xml")
    assert not (section.findtext("summary") or "")


# ── E: files.xml entry completeness ──────────────────────────────────────────

_FILES_REQUIRED_FIELDS = frozenset(
    {
        "contenthash",
        "contextid",
        "component",
        "filearea",
        "itemid",
        "filepath",
        "filename",
        "userid",
        "filesize",
        "mimetype",
        "status",
        "timecreated",
        "timemodified",
        "sortorder",
        "repositorytype",
        "repositoryid",
        "reference",
        "source",
        "author",
        "license",
    }
)


def test_files_xml_entry_has_required_fields(file_mbz):
    root = _parse(file_mbz, "files.xml")
    entries = root.findall("file")
    assert entries, "no <file> entries — test needs a course with a static file ref"
    for entry in entries:
        missing = _FILES_REQUIRED_FIELDS - {child.tag for child in entry}
        assert not missing, f"files.xml entry id={entry.get('id')} missing: {missing}"


# ── F: parent/child section numbering (orphan "New section" regression) ──────


@pytest.fixture(scope="module")
def multi_chapter_mbz(tmp_path_factory):
    """2 chapters x 2 sequentials each — enough sections that interleaved
    numbering (the original bug) would show up if reintroduced."""
    root = tmp_path_factory.mktemp("mcmbz")
    b = OLXFixtureBuilder(root / "course")
    b.chapters = [
        Chapter(
            f"ch{i}",
            f"Chapter {i}",
            [
                Sequential(
                    f"ch{i}_s{j}",
                    f"Ch{i} Seq{j}",
                    [
                        Vertical(
                            f"ch{i}_s{j}_v1",
                            "V1",
                            [
                                HtmlComponent(f"ch{i}_s{j}_pg1", "Page 1"),
                            ],
                        )
                    ],
                )
                for j in range(2)
            ],
        )
        for i in range(2)
    ]
    course = Course(b.build())
    course.parse()
    out = root / "out.mbz"
    MBZBuilder(course).build(out)
    return out


def _section_xmls(mbz_path):
    with tarfile.open(mbz_path) as tar:
        return [
            ET.parse(tar.extractfile(m)).getroot()
            for m in tar.getmembers()
            if re.match(r"sections/section_\d+/section\.xml", m.name)
        ]


def test_parent_sections_numbered_before_children(multi_chapter_mbz):
    sections = _section_xmls(multi_chapter_mbz)
    parent_nums = [
        int(s.findtext("number"))
        for s in sections
        if s.findtext("component") != "mod_subsection"
    ]
    child_nums = [
        int(s.findtext("number"))
        for s in sections
        if s.findtext("component") == "mod_subsection"
    ]
    assert parent_nums and child_nums
    assert max(parent_nums) < min(child_nums), (
        f"parent numbers {sorted(parent_nums)} must all come before "
        f"child numbers {sorted(child_nums)} or Moodle misclassifies delegated sections"
    )


def test_subsection_module_sectionnumber_matches_parent(multi_chapter_mbz):
    with tarfile.open(multi_chapter_mbz) as tar:
        names = tar.getnames()
        section_number_by_id = {}
        for n in names:
            if re.match(r"sections/section_\d+/section\.xml", n):
                root = ET.parse(tar.extractfile(n)).getroot()
                section_number_by_id[int(root.get("id"))] = int(root.findtext("number"))
        subsection_modules = [
            n for n in names if re.match(r"activities/subsection_\d+/module\.xml", n)
        ]
        assert subsection_modules
        for n in subsection_modules:
            root = ET.parse(tar.extractfile(n)).getroot()
            sec_id = int(root.findtext("sectionid"))
            sec_num = int(root.findtext("sectionnumber"))
            assert sec_num == section_number_by_id[sec_id], (
                f"{n}: sectionnumber={sec_num} != section {sec_id}'s actual number={section_number_by_id[sec_id]}"
            )


def _syllabus_builder(root):
    b = OLXFixtureBuilder(root / "course")
    b.chapters = [
        Chapter(
            f"ch{i}",
            f"Chapter {i}",
            [
                Sequential(
                    f"ch{i}_s1",
                    f"Ch{i} Seq1",
                    [
                        Vertical(
                            f"ch{i}_s1_v1",
                            "V1",
                            [HtmlComponent(f"ch{i}_s1_pg1", "Page 1")],
                        )
                    ],
                )
            ],
        )
        for i in range(2)
    ]
    b.static_tabs = [StaticTab("Syllabus", "syllabus-slug")]
    b.tabs_files = {"syllabus-slug": "<p>Syllabus content</p>"}
    return b


@pytest.fixture(scope="module")
def syllabus_nested_mbz(tmp_path_factory):
    root = tmp_path_factory.mktemp("synmbz")
    course = Course(_syllabus_builder(root).build())
    course.parse()
    out = root / "out.mbz"
    MBZBuilder(course).build(out)
    return out


@pytest.fixture(scope="module")
def syllabus_flat_mbz(tmp_path_factory):
    root = tmp_path_factory.mktemp("syflmbz")
    course = Course(_syllabus_builder(root).build())
    course.parse()
    out = root / "out.mbz"
    MBZBuilder(course, sequential_sections=True).build(out)
    return out


@pytest.fixture(scope="module")
def syllabus_nested_legacy_mbz(tmp_path_factory):
    root = tmp_path_factory.mktemp("synlegmbz")
    course = Course(_syllabus_builder(root).build())
    course.parse()
    out = root / "out.mbz"
    MBZBuilder(course, authora=False).build(out)
    return out


@pytest.fixture(scope="module")
def syllabus_flat_legacy_mbz(tmp_path_factory):
    root = tmp_path_factory.mktemp("syflegmbz")
    course = Course(_syllabus_builder(root).build())
    course.parse()
    out = root / "out.mbz"
    MBZBuilder(course, sequential_sections=True, authora=False).build(out)
    return out


def _non_general_non_overview_numbers(mbz_path):
    return [
        int(s.findtext("number"))
        for s in _section_xmls(mbz_path)
        if s.findtext("name") not in ("", "Overview")
    ]


def test_overview_section_numbered_zero_without_authora(syllabus_nested_legacy_mbz):
    sections = _section_xmls(syllabus_nested_legacy_mbz)
    overview = [s for s in sections if s.findtext("name") == "Overview"]
    assert len(overview) == 1
    assert overview[0].findtext("number") == "0"
    assert not [s for s in sections if not s.findtext("name")]


def test_authora_general_section_is_empty_section_zero(syllabus_nested_mbz):
    sections = _section_xmls(syllabus_nested_mbz)
    zero = [s for s in sections if s.findtext("number") == "0"]
    assert len(zero) == 1
    assert (zero[0].findtext("name") or "") == ""
    assert not (zero[0].findtext("sequence") or "")
    assert zero[0].findtext("component") == "$@NULL@$"


def test_authora_general_section_is_hidden(syllabus_nested_mbz):
    sections = _section_xmls(syllabus_nested_mbz)
    zero = [s for s in sections if s.findtext("number") == "0"]
    assert zero[0].findtext("visible") == "0"


def test_authora_overview_is_section_one(syllabus_nested_mbz):
    sections = _section_xmls(syllabus_nested_mbz)
    overview = [s for s in sections if s.findtext("name") == "Overview"]
    assert len(overview) == 1
    assert overview[0].findtext("number") == "1"


def test_authora_section_numbers_are_unique(syllabus_nested_mbz):
    nums = [s.findtext("number") for s in _section_xmls(syllabus_nested_mbz)]
    assert len(nums) == len(set(nums))


def test_authora_overview_modules_use_section_number_one(overview_and_readings_mbz):
    """Syllabus page and Readings subsection record Overview's number in module.xml."""
    overview_id = next(
        s
        for s in _section_xmls(overview_and_readings_mbz)
        if s.findtext("name") == "Overview"
    ).get("id")
    with tarfile.open(overview_and_readings_mbz) as tar:
        modules = [
            ET.parse(tar.extractfile(m)).getroot()
            for m in tar.getmembers()
            if re.match(r"activities/[a-z]+_\d+/module\.xml", m.name)
        ]
    in_overview = [m for m in modules if m.findtext("sectionid") == overview_id]
    assert len(in_overview) == 2  # syllabus page + readings subsection module
    assert all(m.findtext("sectionnumber") == "1" for m in in_overview)


def test_authora_no_activity_targets_general_section(overview_and_readings_mbz):
    general_id = next(
        s for s in _section_xmls(overview_and_readings_mbz) if not s.findtext("name")
    ).get("id")
    acts = _backup_xml(overview_and_readings_mbz).findall(".//activities/activity")
    assert all(a.findtext("sectionid") != general_id for a in acts)


def test_overview_sequence_has_one_module(syllabus_nested_mbz):
    sections = _section_xmls(syllabus_nested_mbz)
    overview = next(s for s in sections if s.findtext("name") == "Overview")
    sequence = [m for m in (overview.findtext("sequence") or "").split(",") if m]
    assert len(sequence) == 1


def test_chapter_numbers_shift_past_overview_nested_without_authora(
    syllabus_nested_legacy_mbz,
):
    assert min(_non_general_non_overview_numbers(syllabus_nested_legacy_mbz)) == 1


def test_chapter_numbers_shift_past_general_and_overview_nested(syllabus_nested_mbz):
    assert min(_non_general_non_overview_numbers(syllabus_nested_mbz)) == 2


def test_chapter_numbers_shift_past_overview_flat_without_authora(
    syllabus_flat_legacy_mbz,
):
    """Flat sections already number 1..n with no offset (unlike Nested's
    0..n-1), so with a prepended Overview (offset=1) the first one is 2."""
    assert min(_non_general_non_overview_numbers(syllabus_flat_legacy_mbz)) == 2


def test_chapter_numbers_shift_past_general_and_overview_flat(syllabus_flat_mbz):
    assert min(_non_general_non_overview_numbers(syllabus_flat_mbz)) == 3


def test_overview_section_present_but_empty_without_syllabus(multi_chapter_mbz):
    """Overview always exists, even with no syllabus content -- it's just empty."""
    sections = _section_xmls(multi_chapter_mbz)
    overview = next(s for s in sections if s.findtext("name") == "Overview")
    assert overview.findtext("number") == "1"
    assert not [m for m in (overview.findtext("sequence") or "").split(",") if m]


# ── G: Readings section (pdf_textbooks -> mod_resource) ──────────────────────


def _readings_builder(root):
    b = OLXFixtureBuilder(root / "course")
    b.chapters = [
        Chapter(
            f"ch{i}",
            f"Chapter {i}",
            [
                Sequential(
                    f"ch{i}_s1",
                    f"Ch{i} Seq1",
                    [
                        Vertical(
                            f"ch{i}_s1_v1",
                            "V1",
                            [HtmlComponent(f"ch{i}_s1_pg1", "Page 1")],
                        )
                    ],
                )
            ],
        )
        for i in range(2)
    ]
    b.static_files = {"reading1.pdf": b"fake-pdf-bytes"}
    b.pdf_textbooks = [
        PdfTextbook(
            "Readings", [{"title": "Reading One", "url": "/static/reading1.pdf"}]
        )
    ]
    return b


@pytest.fixture(scope="module")
def readings_only_mbz(tmp_path_factory):
    root = tmp_path_factory.mktemp("rdmbz")
    course = Course(_readings_builder(root).build())
    course.parse()
    out = root / "out.mbz"
    MBZBuilder(course).build(out)
    return out


@pytest.fixture(scope="module")
def overview_and_readings_mbz(tmp_path_factory):
    root = tmp_path_factory.mktemp("ovrdmbz")
    b = _readings_builder(root)
    b.static_tabs = [StaticTab("Syllabus", "syllabus-slug")]
    b.tabs_files = {"syllabus-slug": "<p>Syllabus content</p>"}
    course = Course(b.build())
    course.parse()
    out = root / "out.mbz"
    MBZBuilder(course).build(out)
    return out


def _backup_xml(mbz_path) -> ET.Element:
    with tarfile.open(mbz_path) as tar:
        return ET.parse(tar.extractfile("moodle_backup.xml")).getroot()


def test_readings_nests_under_overview_without_syllabus(readings_only_mbz):
    """Overview always exists now, so Readings always nests as a mod_subsection
    inside it, even when the course has no syllabus content."""
    sections = _section_xmls(readings_only_mbz)
    overview = next(s for s in sections if s.findtext("name") == "Overview")
    readings = next(s for s in sections if s.findtext("name") == "Readings")
    assert overview.findtext("number") == "1"
    assert readings.findtext("component") == "mod_subsection"
    assert readings.findtext("itemid") not in (None, "", "$@NULL@$")


def test_readings_resource_insubsection_set_without_syllabus(readings_only_mbz):
    acts = _backup_xml(readings_only_mbz).findall(".//activities/activity")
    resource_acts = [a for a in acts if a.findtext("modulename") == "resource"]
    assert resource_acts
    assert all(a.findtext("insubsection") == "1" for a in resource_acts)


def test_readings_nested_as_subsection_under_overview(overview_and_readings_mbz):
    """With Overview present, Readings becomes a real mod_subsection delegate
    nested inside it — same shape NestedSectionStrategy uses for
    sequentials-under-chapters — not a second top-level section."""
    sections = _section_xmls(overview_and_readings_mbz)
    overview = next(s for s in sections if s.findtext("name") == "Overview")
    readings = next(s for s in sections if s.findtext("name") == "Readings")
    assert overview.findtext("number") == "1"
    assert readings.findtext("component") == "mod_subsection"
    assert readings.findtext("itemid") not in (None, "", "$@NULL@$")


def test_readings_subsection_numbered_after_all_other_sections(
    overview_and_readings_mbz,
):
    """Moodle requires every parent section number to sort below every child
    section number, course-wide (test_parent_sections_numbered_before_children)
    — the nested Readings child section must therefore be numbered after
    every chapter *and* every sequential-derived child section."""
    sections = _section_xmls(overview_and_readings_mbz)
    readings = next(s for s in sections if s.findtext("name") == "Readings")
    other_nums = [
        int(s.findtext("number")) for s in sections if s.findtext("name") != "Readings"
    ]
    assert int(readings.findtext("number")) > max(other_nums)


def test_overview_sequence_includes_readings_subsection_module(
    overview_and_readings_mbz,
):
    sections = _section_xmls(overview_and_readings_mbz)
    overview = next(s for s in sections if s.findtext("name") == "Overview")
    sequence = [m for m in (overview.findtext("sequence") or "").split(",") if m]
    assert len(sequence) == 2  # syllabus page + readings subsection module


def test_readings_subsection_activity_points_at_overview_section(
    overview_and_readings_mbz,
):
    sections = _section_xmls(overview_and_readings_mbz)
    overview_id = next(s for s in sections if s.findtext("name") == "Overview").get(
        "id"
    )
    acts = _backup_xml(overview_and_readings_mbz).findall(".//activities/activity")
    subsection_acts = [
        a
        for a in acts
        if a.findtext("title") == "Readings"
        and a.findtext("modulename") == "subsection"
    ]
    assert len(subsection_acts) == 1
    assert subsection_acts[0].findtext("sectionid") == overview_id


def test_readings_resource_insubsection_set_when_nested(overview_and_readings_mbz):
    acts = _backup_xml(overview_and_readings_mbz).findall(".//activities/activity")
    resource_acts = [a for a in acts if a.findtext("modulename") == "resource"]
    assert resource_acts
    assert all(a.findtext("insubsection") == "1" for a in resource_acts)


def test_overview_syllabus_page_insubsection_stays_empty(overview_and_readings_mbz):
    """Regression: insubsection used to be a single global flag set to "1"
    whenever *any* sub_mods existed in the course, wrongly tagging the
    Overview syllabus page (which sits in a plain top-level section) just
    because chapters/Readings elsewhere use subsections."""
    acts = _backup_xml(overview_and_readings_mbz).findall(".//activities/activity")
    syllabus_act = next(a for a in acts if a.findtext("title") == "Syllabus")
    assert syllabus_act.findtext("insubsection") == ""


def test_chapter_numbers_shift_past_overview_only(overview_and_readings_mbz):
    """Readings nests inside Overview rather than taking its own top-level
    slot, so the offset is still 2 (General and Overview), same as the
    no-Readings syllabus case — not 3."""
    sections = _section_xmls(overview_and_readings_mbz)
    chapter_nums = [
        int(s.findtext("number"))
        for s in sections
        if s.findtext("name") not in ("", "Overview", "Readings")
        and s.findtext("component") != "mod_subsection"
    ]
    assert min(chapter_nums) == 2


def test_readings_resource_written_with_correct_modulename(readings_only_mbz):
    with tarfile.open(readings_only_mbz) as tar:
        names = tar.getnames()
        resource_modules = [
            n for n in names if re.match(r"activities/resource_\d+/module\.xml", n)
        ]
        assert len(resource_modules) == 1
        root = ET.parse(tar.extractfile(resource_modules[0])).getroot()
        assert root.findtext("modulename") == "resource"


def test_readings_file_registered_under_mod_resource_component(readings_only_mbz):
    """Regression check for the FILE_ENTRY hardcoded-mod_page bug caught while
    planning this feature — a Readings PDF must not be misattributed to
    mod_page in files.xml."""
    with tarfile.open(readings_only_mbz) as tar:
        files_xml = ET.parse(tar.extractfile("files.xml")).getroot()
    entry = next(
        f for f in files_xml.findall("file") if f.findtext("filename") == "reading1.pdf"
    )
    assert entry.findtext("component") == "mod_resource"


def test_readings_file_bytes_copied(readings_only_mbz):
    with tarfile.open(readings_only_mbz) as tar:
        names = set(tar.getnames())
        files_xml = ET.parse(tar.extractfile("files.xml")).getroot()
    entry = next(
        f for f in files_xml.findall("file") if f.findtext("filename") == "reading1.pdf"
    )
    sha1 = entry.findtext("contenthash")
    assert f"files/{sha1[:2]}/{sha1}" in names


def test_readings_resource_without_resolvable_file_writes_empty_inforef(tmp_path):
    """A readings entry whose file never made it into static_files (e.g. a
    fetch that failed after the reading was still recorded) must not produce
    a <fileref> pointing at a nonexistent file record."""
    course = Course(_readings_builder(tmp_path).build())
    course.parse()
    course.readings.append({"title": "Ghost Reading", "name": "ghost.pdf"})
    out = tmp_path / "out.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        names = tar.getnames()
        resource_dirs = sorted(
            {n.split("/")[1] for n in names if n.startswith("activities/resource_")}
        )
        assert len(resource_dirs) == 2
        inforefs = {
            d: ET.parse(tar.extractfile(f"activities/{d}/inforef.xml")).getroot()
            for d in resource_dirs
        }
    ghost_inforef = next(
        root for root in inforefs.values() if root.find("fileref") is None
    )
    assert ghost_inforef.find("fileref") is None


# ── D: Wikiwijs metadata (summary + customfields, plan.md §10) ─────────────────


def _metadata_builder(root) -> OLXFixtureBuilder:
    b = OLXFixtureBuilder(root / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1", "S1", [Vertical("v1", "V1", [HtmlComponent("pg1", "Page 1")])]
                )
            ],
        )
    ]
    b.org = "TUDelftX"
    b.language = "en"
    b.license = "creative-commons: ver=4.0 BY NC SA"
    b.summary_html = "<p>Course summary</p>"
    return b


@pytest.fixture(scope="module")
def metadata_mbz(tmp_path_factory):
    root = tmp_path_factory.mktemp("meta")
    course = Course(_metadata_builder(root).build())
    course.parse()
    out = root / "out.mbz"
    MBZBuilder(course).build(out)
    with tarfile.open(out) as tar:
        return ET.parse(tar.extractfile("course/course.xml")).getroot()


def test_course_xml_summary_populated(metadata_mbz):
    assert metadata_mbz.findtext("summary") == "<p>Course summary</p>"


def test_course_xml_customfields_present_when_enabled(metadata_mbz):
    customfields = metadata_mbz.find("customfields").findall("customfield")
    assert 2 <= len(customfields) <= 4
    shortnames = {cf.findtext("shortname") for cf in customfields}
    assert {"access", "license"} <= shortnames


def test_course_xml_customfields_empty_when_disabled(tmp_path):
    course = Course(_metadata_builder(tmp_path).build())
    course.parse()
    out = tmp_path / "out.mbz"
    MBZBuilder(course, disable_custom_fields=True).build(out)
    with tarfile.open(out) as tar:
        xml = ET.parse(tar.extractfile("course/course.xml")).getroot()
    assert xml.find("customfields").findall("customfield") == []


def test_warn_external_edx_urls_fires_for_page_with_edx_link(tmp_path, caplog):
    """A page html component pointing at a real edX-hosted host (survey table,
    plan_2.md) must trigger the warning during full conversion, not just when
    calling warn_external_edx_urls directly."""
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1",
                    "S1",
                    [
                        Vertical(
                            "v1",
                            "V1",
                            [
                                HtmlComponent(
                                    "pg1",
                                    "Page 1",
                                    content='<a href="https://courses.edx.org/asset-v1:x.png">link</a>',
                                )
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    course = Course(b.build())
    course.parse()
    out = tmp_path / "out.mbz"
    with caplog.at_level("WARNING", logger="ocw.converter"):
        MBZBuilder(course).build(out)
    assert "still hosted on edX" in caplog.text
    assert "courses.edx.org" in caplog.text


def test_warn_external_edx_urls_silent_for_page_with_local_link(tmp_path, caplog):
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1",
                    "S1",
                    [
                        Vertical(
                            "v1",
                            "V1",
                            [
                                HtmlComponent(
                                    "pg1",
                                    "Page 1",
                                    content='<img src="/static/x.png"/>',
                                )
                            ],
                        )
                    ],
                )
            ],
        )
    ]
    course = Course(b.build())
    course.parse()
    out = tmp_path / "out.mbz"
    with caplog.at_level("WARNING", logger="ocw.converter"):
        MBZBuilder(course).build(out)
    assert "still hosted on edX" not in caplog.text


def test_warn_external_edx_urls_fires_for_syllabus_with_edx_link(tmp_path, caplog):
    """Syllabus content goes through a separate call site
    (builder.py's _build_overview_section) from page components — needs its
    own coverage, not just the page-level one above."""
    b = OLXFixtureBuilder(tmp_path / "course")
    b.chapters = [
        Chapter(
            "ch1",
            "Ch 1",
            [
                Sequential(
                    "s1", "S1", [Vertical("v1", "V1", [HtmlComponent("pg1", "Page 1")])]
                )
            ],
        )
    ]
    b.static_tabs = [StaticTab("Syllabus", "syllabus-slug")]
    b.tabs_files = {
        "syllabus-slug": '<a href="https://learning.edx.org/course/x">still on edx</a>'
    }
    course = Course(b.build())
    course.parse()
    out = tmp_path / "out.mbz"
    with caplog.at_level("WARNING", logger="ocw.converter"):
        MBZBuilder(course).build(out)
    assert "still hosted on edX" in caplog.text
    assert "learning.edx.org" in caplog.text
