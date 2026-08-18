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
