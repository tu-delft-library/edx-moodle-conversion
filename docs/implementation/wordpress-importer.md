# WP Importer

The WordPress importer accepts a public TU Delft OCW course URL through `ocw-wp` or the WordPress GUI. It reads HTML
only and does not use a WordPress API.

## Conversion flow

* [`ocw.cli.wp.main()`](../reference/python.md#ocw.cli.wp.main) and
  [`App._convert_one()`](../reference/python.md#ocw.gui.wp.App._convert_one): accept one or more public course URLs.
  They create a temporary directory when external PDF fetching is enabled and pass its asset fetcher to the parser.
* [`WPCourse.parse()`](../reference/python.md#ocw.parser.wp.WPCourse.parse): fetches the course home page, obtains
  subject links from its sidebar, and turns each subject into a chapter in the shared course structure.
* [`WPCourse._parse_subject_page()`](../reference/python.md#ocw.parser.wp.WPCourse._parse_subject_page): reads each
  activity group as a sequential. It keeps `vc_row` introduction content and sends lecture and reading links to their
  dedicated parsers.
* [`WPCourse._parse_lecture()`](../reference/python.md#ocw.parser.wp.WPCourse._parse_lecture) and
  [`WPCourse._parse_reading()`](../reference/python.md#ocw.parser.wp.WPCourse._parse_reading): preserve page HTML,
  extract YouTube or Collegerama IDs, convert expandable widgets, and download linked PDFs when possible.
* [`MBZBuilder.build()`](../reference/python.md#ocw.converter.builder.MBZBuilder.build): uses the same Moodle archive
  builder as OLX. WordPress conversion does not run OLX parity checks because it has no equivalent source structure.
* **[`ocw-wp-zip`](wp-zip-export.md) reuses the same parser and writes the course as an HTML zip instead of an MBZ.**

## Structure mapping

The course home-page sidebar supplies subject links. Subject pages supply activity groups. Lecture and reading links
within each group become Moodle pages in the same shared course structure used by the OLX importer.

## Supported content

* Subject introduction text from `vc_row` blocks
* Lecture text before and after media
* YouTube and Collegerama iframe embeds
* Reading text and downloadable PDFs
* `vc_expandable_text` widgets converted to native HTML details elements

## Shared pages

A reading or lecture linked from several subject pages is parsed once and cached by url (`_reading_pages`,
`_lecture_pages`).

`parse()` first counts how many subject pages link each lecture (`_lecture_ref_counts`). A lecture linked twice or more
goes to `dedup_pages`, which becomes the hidden section, and every subject page gets a `dedup_link` component pointing
at it. A lecture linked once stays inline. Calls that bypass `parse()` (unit tests) get an empty counter, so every url
counts as a single reference.

## Download widget

The WP site builds the download box client side (`TUD_download_tool.js`, then `builder.js`, then `resizer.js`), which
iframes the server rendered `TUD_download_tool.php`. `resizer.js` detects Moodle's global RequireJS and throws
"Mismatched anonymous define() module", so the widget never builds in Moodle.

The parser fetches the tool page at parse time instead and inlines the widget (`ocw/parser/download_tool.py`):

* the dropdowns become native `details` elements, so no JS is needed
* images and the "Other" tab's files are bundled locally, Video and Subtitles links stay on delftxdownloads
* the bootstrap `<script>` (matched by the host check signature) is dropped
* the stylesheet is `base-styles.css` plus `ocw-styles.css` from the tool page, scoped to the widget, with the jQuery
  `.tud-open` toggle class swapped for `details[open]`
* dropdowns flow in layout rather than absolutely positioned, since Moodle's `.no-overflow` content wrapper would clip
  them into a scrollbox

The OLX importer inlines the same widget (`inline_widget`).

## Deliberate exclusions

Exercises, exams, MOOCs, course overview metadata, and course-wide materials pages are not imported. CSS selectors
target the TU Delft OCW WordPress layout, so unrelated WordPress themes are out of scope.
