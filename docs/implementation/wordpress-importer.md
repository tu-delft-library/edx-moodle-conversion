# WordPress Importer

The WordPress importer accepts a public TU Delft OCW course URL through `ocw-wp` or the WordPress GUI. It reads HTML
only and does not use a WordPress API.

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
