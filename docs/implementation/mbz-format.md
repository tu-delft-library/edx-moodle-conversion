# MBZ Format

An MBZ archive is a Moodle backup archive containing XML files and stored course assets. `MBZBuilder` creates the
archive layout expected by Moodle restore.

## Consistency constraints

A key challenge is ensuring XML objects are consistent with one another, enforced through these constraints:

* sequential integer IDs for MBZ XML elements
* XML entity escaping
* SHA-1 digest of file bytes: Moodle uses this as the storage key
* Link handling: `rewrite_static_urls(html)` changes `/static/foo` to `@@PLUGINFILE@@/foo`

## Context ids

The course context id (`course_ctx` in `MBZBuilder._populate`) must be distinct from every other id allocated in the
build, and in particular from 1. Every Moodle site's own system context is permanently id 1, and restore pre-maps
backup context id 1 straight to it. Reusing 1 would redirect course context files (course image,
overviewfiles) into the site's system context instead of the course. For that reason we use an offset.

## Course image

Only `course_image_path` is written to the course context `overviewfiles` area. Moodle's `get_course_overviewfiles()`
sorts this area by filename and keeps only the first `courseoverviewfileslimit` files. For this we only supply a single
image, even if the source may contain multiple candidates.

## Overview image

On Authora courses the thumbnail is also embedded inline in the Overview section summary. This second copy mirrors
real Authora restored courses. It is registered under `component=course, filearea=section, itemid=<overview section
id>` with its own `.` placeholder, and referenced from that section's own `inforef.xml` (not the course's).

## Linked pages and section counts

Pages that are linked from more than one place are built once, and the links resolve through their `mod_id`:
`reading_link` stubs through `_reading_page_ids`, any other dedup content (currently lectures) through
`_dedup_page_ids`. The canonical page is always built before its stubs, in source parse order.

`build_sections()` sets two counts. `regular_section_count` is the sections that are not subsection linked, which is how
many of the declared section numbers Moodle restore honours. `child_section_count` is the subsection linked child
sections it built, renumbered by `relocate_child_sections()`.

## Important content

* `course/course.xml`: course settings, sections, custom fields, and local plugin data
* `sections/`: Moodle section definitions
* `activities/`: Moodle page and resource definitions
* `files.xml`: archive metadata for embedded assets

## Custom fields

The converter can populate `publisher`, `language`, `access`, and `license` when Moodle has matching eduSources
custom fields. Use `--disable-custom-fields` when the target instance does not provide them.

## Video data

Video mappings are written as local Video Router plugin data. Moodle restore passes that data to `local_vidrouter`,
which creates a mapping when the video key is new.
