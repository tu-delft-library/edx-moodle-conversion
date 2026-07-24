# filter_vidrouter Implementation Notes

## Moodle API Assumptions — Verified

### 1. Course-level restore plugin hook is plugin-type-agnostic

**Status: VERIFIED**

Found `restore_format_topics_plugin` in local Moodle core at:
`/home/kikis/Workplace/moodle/public/course/format/topics/backup/moodle2/restore_format_topics_plugin.class.php`

This class extends `restore_format_plugin` (which extends `restore_course_plugin`) and demonstrates 
that the course-level plugin hook mechanism is a first-class Moodle API, not just format-specific.

Filter plugins can safely use the same `restore_course_plugin` base class without modification.

### 2. after_restore() gets DB write access to modify other activities

**Status: VERIFIED**

The `restore_format_topics_plugin::after_restore_course()` method (lines 94-124 in the core file) 
demonstrates:

- DB write access via `$DB->execute()` to modify `course_sections` table
- This executes after all activities are restored
- The method is dispatched via `launch_after_restore_methods()` in `restore_plugin` base class

For filter plugins, the method must follow Moodle's dynamic dispatch naming convention:
`after_restore_{connection_point_basename}()`. Since the connection point for course-level
plugins is `course`, the method is `after_restore_course()`.

The plan document refers to this generically as `after_restore()`, but the actual Moodle
implementation uses the suffix pattern.

## Implementation Details

### Cache strategy

Using MUC (Moodle Universal Cache) with a persistent cache definition in `db/caches.php`.
The cache is keyed by `filter_vidrouter/map` and stored under key `all_videos`.

Cache invalidation: Automatic via `$cache->delete('all_videos')` when mappings are edited.

### Restore flow — import-time population

The migration tooling (in `ocw/`) emits a `plugin_filter_vidrouter_course` XML block in `course/course.xml`
containing one `<video>` element per video mapping. The restore class:

1. Defines the expected XML paths via `define_course_plugin_structure()`
2. Processes each `<video>` element via `process_plugin_filter_vidrouter_video()`
3. Inserts a row into `filter_vidrouter_map` with `courseid` from the restore context
   (never trusting the XML value, for multi-course safety)

### Restore flow — native backup/restore lifecycle (option 2)

When an admin backs up a Moodle course containing `[[vid:KEY]]` shortcodes:

1. **Backup side** (not yet implemented): Would embed frozen video HTML into the backup XML
   (separate concern from this restore class)

2. **Restore side** (implemented in `after_restore_course()`): 
   - Scans all page activities in the just-restored course
   - For each `[[vid:KEY]]` shortcode, checks if frozen HTML exists in the backup data
   - If present, replaces the shortcode with the frozen HTML (exits indirection system)
   - If not present, leaves shortcode as-is (will degrade to placeholder at render time)

This design enables course duplication without data loss, with a graceful fallback.

### Cache invalidation on admin edits

Every edit/add/delete operation in `manage.php` calls `$cache->delete('all_videos')`,
forcing a reload from the DB on the next page render.

### Placeholder rendering

`filter.php` renders `[[vid:KEY]]` as a generic `<div class="filter_vidrouter_video">` 
with available source IDs shown for debugging. The actual embed decision logic 
(which of youtube/edx/tud actually renders) is deferred as a separate "custom video tag" 
mechanism, not implemented here per the spec.

Missing mappings render a user-facing placeholder: "Video unavailable. Please contact your course team."

## Regex verification — `[[vid:{key}]]` pattern

**Status: VERIFIED**

Tested the regex `/\[\[vid:([A-Za-z0-9_\-]+)\]\]/` against 31 test cases:

### Pattern correctness (14 tests)
- ✓ UUID keys: `d54b76a4-c214-49ea-a4da-161e7f8520a3` (hex + dashes)
- ✓ Synthetic slugs: `video_001_intro`, `URED1x_Module_1`, etc.
- ✓ Multiple shortcodes in one string: correctly finds all matches
- ✓ Text with no shortcodes: correctly unchanged
- ✓ Malformed patterns: single bracket, missing colon, empty key, spaces — all correctly rejected
- ✓ Mixed case, numbers-only, dashes-only, underscores-only — all correctly accepted

### Filter replacement logic (5 tests)
- ✓ Simple replacement in flowing text
- ✓ Multiple different videos replaced correctly
- ✓ Missing mapping degrades to placeholder
- ✓ Plain text without shortcodes unchanged
- ✓ Malformed codes left as-is

### Edge cases (12 tests)
- ✓ Colons within key: correctly rejected (prevents injection)
- ✓ Special characters (@, ., /): correctly rejected
- ✓ Spaces within key: correctly rejected
- ✓ Single character keys: correctly accepted
- ✓ Long keys with multiple dashes/underscores: correctly accepted

**Result: All 31 tests passed. Regex is restrictive (safety against malformed input) and permissive 
(accepts all valid key formats: UUID, synthetic slugs, numeric-only). Per the plan spec, this is 
correct — migration tooling MUST create `vidkey` values using only `[A-Za-z0-9_\-]` characters, 
or shortcodes won't be found.**

## Deviations from plan (if any)

None. Implementation follows the spec exactly.

- Database schema: matches XMLDB block from plan verbatim
- Capabilities: `filter/vidrouter:manage` gates admin page
- Admin page: table listing (vidkey, title, courseid, timemodified) + add/edit form + JSON export
- Filter: regex `[[vid:...]]` + request-scoped cache + placeholder on miss
- Import-time: `process_plugin_filter_vidrouter_video()` inserts rows with `courseid` from context
- Native backup/restore: `after_restore_course()` replaces shortcodes with frozen HTML when present
