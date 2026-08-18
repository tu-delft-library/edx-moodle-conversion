# MBZ Format

An MBZ archive is a Moodle backup archive containing XML files and stored course assets. `MBZBuilder` creates the
archive layout expected by Moodle restore.

## Consistency constraints

A key challenge is ensuring XML objects are consistent with one another, enforced through these constraints:

* sequential integer IDs for MBZ XML elements
* XML entity escaping
* SHA-1 digest of file bytes: Moodle uses this as the storage key
* Link handling: `rewrite_static_urls(html)` changes `/static/foo` to `@@PLUGINFILE@@/foo`

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
