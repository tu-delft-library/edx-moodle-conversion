# WP Importer

The WordPress importer accepts a public TU Delft OCW course URL through `ocw-wp` or the WordPress GUI. It reads HTML
only and does not use a WordPress API.

## Conversion flow

* [`ocw.cli.wp.main()`](../reference/python.md#ocw.cli.wp.main) and
  [`App._convert_one()`](../reference/python.md#ocw.gui.wp.App._convert_one): accept one or more public course URLs.
  They create a temporary directory when external PDF fetching is enabled and pass its asset fetcher to the parser.
* [`WPCourse.parse()`](../reference/python.md#ocw.wp_parser.WPCourse.parse): fetches the course home page, obtains
  subject links from its sidebar, and turns each subject into a chapter in the shared course structure.
* [`WPCourse._parse_subject_page()`](../reference/python.md#ocw.wp_parser.WPCourse._parse_subject_page): reads each
  activity group as a sequential. It keeps `vc_row` introduction content and sends lecture and reading links to their
  dedicated parsers.
* [`WPCourse._parse_lecture()`](../reference/python.md#ocw.wp_parser.WPCourse._parse_lecture) and
  [`WPCourse._parse_reading()`](../reference/python.md#ocw.wp_parser.WPCourse._parse_reading): preserve page HTML,
  extract YouTube or Collegerama IDs, convert expandable widgets, and download linked PDFs when possible.
* [`MBZBuilder.build()`](../reference/python.md#ocw.converter.builder.MBZBuilder.build): uses the same Moodle archive
  builder as OLX. WordPress conversion does not run OLX parity checks because it has no equivalent source structure.

## Structure mapping

The course home-page sidebar supplies subject links. Subject pages supply activity groups. Lecture and reading links
within each group become Moodle pages in the same shared course structure used by the OLX importer.

## Supported content

* Subject introduction text from `vc_row` blocks
* Lecture text before and after media
* YouTube and Collegerama iframe embeds
* Reading text and downloadable PDFs
* `vc_expandable_text` widgets converted to native HTML details elements

## Deliberate exclusions

Exercises, exams, MOOCs, course overview metadata, and course-wide materials pages are not imported. CSS selectors
target the TU Delft OCW WordPress layout, so unrelated WordPress themes are out of scope.
