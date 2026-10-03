# WP Zip Export

**## Purpose**

\*\*`ocw-wp-zip` backs up a WordPress course site as a browsable HTML folder inside a zip. It is not an MBZ and nothing
restores it into Moodle.

**## Data flow**

**`WPCourse` parses the site (same parser as `ocw-wp`), `ZipBuilder` plans and writes the pages, then
`log_zip_checks` compares the planned page count with the zip contents.**

| Step   | Code                                                 | Output                                                        |
| ------ | ---------------------------------------------------- | ------------------------------------------------------------- |
| Parse  | `ocw/parser/wp.py` `WPCourse(keep_all_content=True)` | Chapters, readings, shared pages, static files                |
| Plan   | `ZipBuilder._plan()`                                 | Chapter, sequential, vertical, reading, and shared page paths |
| Write  | `ZipBuilder._write_pages()`, `_write_index()`        | HTML pages, root `index.html`                                 |
| Assets | `ZipBuilder._copy_assets()`                          | `assets/` folder, refs rewritten to relative paths            |
| Report | `ExternalContentReport`                              | `external_content.docx`                                       |
| Check  | `ocw/zip_checks.py` `log_zip_checks()`               | `PASS`/`FAIL` log line                                        |

**## Zip layout**

**Everything sits under one `<course_slug>/` folder. Chapter index pages are `index.html` in each chapter folder.
Content pages are `<sequential>/<NN>_<title>.html`. Readings and shared lectures go in `readings/` and `shared/`.**

**## Page count parity**

**Expected = verticals with components across all sequentials, plus reading and shared pages with components.
Actual = `.html` files whose name is not `index.html`. Empty verticals are linked but not written, so they are not
counted.**

**## Flags**

**`--fetch-external-assets` (default on) fetches PDFs still hosted on edX. `--no-fetch-external-assets` skips the
fetch. `--sequential-sections`, `--authora`, and `--disable-custom-fields` are MBZ-only and not offered here.**

**## GUI**

**`ocw/gui/wp_zip.py` reuses the WordPress URL dialog. The MBZ-only checkboxes are hidden through
`ConverterApp.MBZ_OPTIONS = False`. Packaged as `ocw-gui-wp-zip` in `.github/workflows/build-gui.yml`.**
