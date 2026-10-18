# WP Zip Export

## Purpose

`ocw-wp-zip` backs up a WordPress course site as a browsable HTML folder inside a zip. It is not an MBZ and nothing
restores it into Moodle. The zip is a standalone backup: assume ocw.tudelft.nl and the edX / DelftX hosts will go
down, so everything the course needs is inside it.

## Data flow

`WPCourse` parses the site (same parser as `ocw-wp`), `ZipBuilder` plans and writes the pages, then
`log_zip_checks` compares the planned page count with the zip contents.

| Step   | Code                                                 | Output                                                                |
| ------ | ---------------------------------------------------- | --------------------------------------------------------------------- |
| Parse  | `ocw/parser/wp.py` `WPCourse(keep_all_content=True)` | Chapters, readings, shared pages, static files                        |
| Plan   | `ZipBuilder._plan()`                                 | Chapter, sequential, vertical, reading, and shared page paths         |
| Write  | `ZipBuilder._write_pages()`, `_write_index()`        | HTML pages, root `index.html` with the course banner                  |
| Assets | `ZipBuilder._copy_assets()`                          | `assets/` folder, refs rewritten to relative paths, blacklist applied |
| Report | `ExternalContentReport`                              | `external_content.xlsx`, and the table at the top of `course.docx`    |
| Docx   | `ZipBuilder._write_docx()`, `HtmlToDocx`             | `course.docx`: table, contents list, then the whole course in order   |
| Check  | `ocw/zip_checks.py` `log_zip_checks()`               | `PASS`/`FAIL` log line                                                |

The zip and the MBZ share the static ref parser, the naming helper and the asset blacklist (`ocw/assets.py`), and a
test pins that both ship the same static files.

## Zip layout

Everything sits under one `<course_slug>/` folder. Chapter index pages are `index.html` in each chapter folder.
Content pages are `<sequential>/<NN>_<title>.html`. Readings and shared lectures go in `readings/` and `shared/`.

## Page count parity

Expected is every planned vertical, reading and shared page. Actual are `.html` files whose name is not `index.html`.
Pages with no components get a placeholder body ("No content was found on the source page.") so every link resolves.

## Link policy

Links are rewritten in `ZipBuilder._relink()`:

| Link                                                           | Result                                                         |
| -------------------------------------------------------------- | -------------------------------------------------------------- |
| Target is a page in the zip                                    | Relative link (root relative html path in the docx)            |
| Course home                                                    | `index.html`                                                   |
| `/teachers/<slug>`                                             | The Teachers chapter page                                      |
| OCW `wp-content/uploads`, files on edX / DelftX hosts          | Fetched and bundled in the parser, then a relative asset link  |
| Any other ocw.tudelft.nl or edX / DelftX link                  | Unwrapped: text kept, url as plain text after it               |
| Widget Video / Subtitles links (`WIDGET_MEDIA_LINKS`)          | Stay clickable, the only exception                             |
| Dead host footnote links (`#fn1`, `#fnref2`)                   | In page anchors, not in the external table                     |
| creativecommons.org and third party hosts                      | Untouched                                                      |

## Audit

`audit_zip()` in `ocw/url_audit.py` checks a built zip, and the same checks run on the hyperlinks of `course.docx`:

* no ocw.tudelft.nl or edX / DelftX link left (bar the widget Video / Subtitles links)
* every relative link resolves to a file in the zip
* the external content table and the pages list the same urls
* every file in `assets/` is used by a page

`tests/real_courses/test_wp_zip_courses.py` runs it on real courses (`--real-courses --all-courses`).

## Asset blacklist

Matched by filename in `ocw/assets.py` (`ASSET_BLACKLIST`). Matched files are not copied as assets, and any `<img>` or
`<a>` that points at them is removed from the page.

| Pattern                    | Matches        | Why                                                    |
| -------------------------- | -------------- | ------------------------------------------------------ |
| `^88x31\.png$`             | CC licence badge | theme chrome, on 53 pages of the breakwaters course  |
| `^featured-Image\.[a-z]+$` | course image   | only the MBZ ships it, the zip shows the banner instead |

## Flags

`--fetch-external-assets` (default on) fetches files still hosted on edX, DelftX and OCW uploads.
`--no-fetch-external-assets` skips the fetch.

## GUI

`ocw/gui/wp_zip.py` reuses the WordPress URL dialog. The MBZ-only checkboxes are hidden through
`ConverterApp.MBZ_OPTIONS = False`. Packaged as `ocw-gui-wp-zip` in `.github/workflows/build-gui.yml`.
