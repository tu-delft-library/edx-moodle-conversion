# Moodle Video Router

The Moodle implementation contains two plugins that work together after an MBZ restore.

| Plugin | Responsibility |
| --- | --- |
| `local_vidrouter` | Imports mappings during restore and preserves video HTML during backup and duplication. |
| `filter_vidrouter` | Replaces `[[vid:KEY]]` when Moodle renders page content. |

## Rendering

`filter_vidrouter` reads the mapping table through Moodle cache. It renders YouTube when an ID is available, then
uses Collegerama as the configured fallback. A shortcode with no mapping renders an unavailable-video message.

## Restore and backup

`local_vidrouter` inserts a mapping only when a restored `vidkey` does not already exist. Existing mappings are not
overwritten. During Moodle course backup and duplication, the plugin stores resolved video HTML and restores it into
the duplicated course pages.

## Required filter order

Video Router Filter must be above Multimedia plugins at:

`Site administration > Plugins > Filters > Manage filters`

Multimedia plugins must also be On or Inherit in individual courses. A course-specific Off setting takes precedence
over the site configuration.

## Video Router Implementation Details

### Components

| Component | Responsibility |
| --- | --- |
| `ocw/parser.py` | Parses OLX video metadata. |
| `ocw/wp_parser.py` | Parses WordPress YouTube and Collegerama embeds. |
| `ocw/converter/builder.py` | Writes the Video Router data block into `course/course.xml`. |
| `local_vidrouter` | Imports video records during MBZ restore. |
| `filter_vidrouter` | Resolves `[[vid:KEY]]` at render time. |

### MBZ Data and Restore

`MBZBuilder._build_vidrouter_block()` writes a `plugin_local_vidrouter_course` block into `course/course.xml`.
Each `<video>` record contains the video key, title, source IDs, URL name, and source-page path.

During restore, `restore_local_vidrouter_plugin::process_plugin_local_vidrouter_video()` creates a row in
`filter_vidrouter_map` when that video key does not already exist. It clears the `filter_vidrouter/map` cache after an
insert.

### Video Key Derivation

| Source | `vidkey` value |
| --- | --- |
| OLX video with an edX video ID | Sanitised edX video ID. |
| OLX video without an edX video ID | Sanitised OLX unit `url_name`. |
| WordPress lecture | Sanitised lecture-page URL slug. |

The filter accepts only `[[vid:KEY]]`, where `KEY` matches `[A-Za-z0-9_-]+` and exactly matches a stored `vidkey`.

### Rendering

`filter_vidrouter\text_filter` loads the map and replaces matching placeholders. `video_renderer` uses the configured
primary source: currently YouTube. It uses Collegerama when the primary source has no ID and the fallback setting is
enabled. edX and TU Delft download IDs are stored for future migration work but are not current rendering sources.

### Extending Video Sources and Backfilling Mappings

Each source has a dedicated nullable ID column in `filter_vidrouter_map`, such as `youtubeid` and
`collegeramaid`. A new source must be added consistently across the converter and both Moodle plugins.

1. Add the source ID column through Moodle XMLDB: `db/install.xml`,
   <a href="../api/php/namespaces/default.html#function_xmldb_filter_vidrouter_upgrade">
   <code>xmldb_filter_vidrouter_upgrade()</code></a>
   in `db/upgrade.php`, and `filter/vidrouter/version.php`.
2. Add the field to relevant source parsers:
   [`Course._parse_video()`](../reference/python.md#ocw.parser.Course._parse_video) in `ocw/parser.py` and
   [`WPCourse._video_component()`](../reference/python.md#ocw.wp_parser.WPCourse._video_component) in
   `ocw/wp_parser.py`.
3. Write the field into the MBZ plugin block through
   <a href="../reference/python.md#ocw.converter.builder.MBZBuilder._build_vidrouter_block">
   <code>MBZBuilder._build_vidrouter_block()</code></a> in `ocw/converter/builder.py`.
4. Carry the field through native Moodle backup and restore:
   <a href="../api/php/classes/backup-local-vidrouter-plugin.html#method_get_video_rows">
   <code>backup_local_vidrouter_plugin::get_video_rows()</code></a>
   and
   <a href="../api/php/classes/restore-local-vidrouter-plugin.html#method_process_plugin_local_vidrouter_video">
   <code>restore_local_vidrouter_plugin::process_plugin_local_vidrouter_video()</code></a>.
5. Add the field to both
   <a href="../api/php/classes/filter-vidrouter-video-renderer.html#method_render">
   <code>video_renderer::render()</code></a>
   and
   <a href="../api/php/classes/filter-vidrouter-video-renderer.html#method_render_for_export">
   <code>video_renderer::render_for_export()</code></a>.
   Both paths must
   support the same source priority and fallback behaviour.
6. Add the source to `filter/vidrouter/settings.php` and `lang/en/filter_vidrouter.php` so administrators can select
   it.
7. Add the field to
   <a href="../api/php/classes/filter-vidrouter-edit-form.html"><code>filter_vidrouter_edit_form</code></a>,
   `manage.php`, and
   <a href="../api/php/classes/filter-vidrouter-bulk-import.html"><code>bulk_import::ASSIGNABLE_FIELDS</code></a>.
8. Validate source IDs as identifiers before using them to construct an embed URL.
9. Clear `filter_vidrouter/map` key `all_videos` after every mapping write. See
   <a href="../api/php/classes/filter-vidrouter-bulk-import.html#method_apply"><code>bulk_import::apply()</code></a>,
   `manage.php`, and
   <a href="../api/php/classes/restore-local-vidrouter-plugin.html#method_process_plugin_local_vidrouter_video">
   <code>process_plugin_local_vidrouter_video()</code></a>.
10. Add PHPUnit coverage for live rendering, export rendering, fallback, missing IDs, and CSV import.

#### Adding a new source ID to existing mappings

Use the CSV import screen to update existing mappings. Select a unique existing field as the match field, then provide
the new source ID as another column:

```csv
edxvideoid,newsourceid
existing-edx-id,new-source-id
```

<a href="../api/php/classes/filter-vidrouter-bulk-import.html#method_plan"><code>bulk_import::plan()</code></a>
previews the updates.
<a href="../api/php/classes/filter-vidrouter-bulk-import.html#method_apply"><code>bulk_import::apply()</code></a>
updates only rows with exactly one matching value. Unmatched and ambiguous rows are not updated.

`vidkey` is globally unique and is the value resolved by `[[vid:KEY]]`. `courseid` records the first course that
created a mapping. It does not list every course that uses the video and must not be used for source backfills.

Changing a mapping affects live shortcode rendering after cache invalidation. Moodle course duplication calls
<a href="../api/php/classes/filter-vidrouter-video-renderer.html#method_render_for_export">
<code>video_renderer::render_for_export()</code></a>
through
<a href="../api/php/classes/backup-local-vidrouter-plugin.html#method_get_video_rows">
<code>backup_local_vidrouter_plugin::get_video_rows()</code></a>,
so existing backups can retain older rendered HTML.

### Tests and CI

Plugin PHPUnit tests are in `moodle-plugin/filter/vidrouter/tests/`.
They cover bulk imports, mapping form validation, and YouTube and Collegerama rendering.
The Moodle plugin CI workflow is `.github/workflows/moodle-plugin-ci.yml`.
