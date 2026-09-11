# Plan: OLX course image (+ banner) into the .mbz

Source: Jorrit's email. `.mbz` courses currently have no course image, even though every OLX
export already carries one. He found two candidate images in `RTC1`'s `course/static/`:
`course_image.jpg` (thumbnail, used for Settings > Description > Course image / catalogue tile)
and `arch_rtc1_edx_2120p.png` (larger, likely a banner/background — no confirmed Moodle field for
this without a vendor theme, per his own email).

WP is out of scope for this plan (no cached WP HTML fixtures, no live-fetch permission — separate
investigation).

## Root cause

Nothing reads `course_image`/`banner_image` today. `Course.parse()` (`ocw/parser/olx.py`) never
looks at those two root-`<course>` attributes, so no `BaseParser` field carries them, and the
builder has no code path that emits a `course` component / `overviewfiles` filearea file record.
Separately, `FILE_ENTRY` (`ocw/templates.py:428`) hardcodes `filearea="content"` and
`_write_files_xml` never passes a `filearea` kwarg, so the file wouldn't be constructible as a
course-context file even if resolved.

## Confirmed facts (from `files/OLX/DelftX URED1x .../course/course/3T2025.xml`)

```xml
<course ... course_image="course_image.jpg" ... >
```
and in `policies/3T2025/policy.json`:
```json
"banner_image": "/static/arch_ured1x_teaser.jpg",
```

Both filenames resolve straight out of `self.static_files` (`ocw/parser/olx.py:80-86`), which
already indexes every file under `course/static/` by filename — no fetch step needed, these are
packaged assets, not remote URLs.

`course.xml`'s course-level context is fixed at `contextid="1"` (`ocw/templates.py:111`,
`<course id="1" contextid="1">`), which is also the `original_course_contextid`
(`ocw/templates.py:29`). Moodle's own "Course image" (Settings > Description > Course image) is
just a file backed up as `component="course"`, `filearea="overviewfiles"`, `itemid=0`, in that
context — no other XML wiring required, Moodle's restore + `course_get_courseimage()` reads it
straight from `mdl_files`.

## Approach

1. **Parser (`ocw/parser/base.py`)**: two new optional `Path` fields on `BaseParser`:
   ```python
   self.course_image_path: Path | None = None
   self.banner_image_path: Path | None = None
   ```

2. **Parser (`ocw/parser/olx.py`)**: in `Course.parse()`, after `static_dir` is indexed (so the
   lookup dict exists), resolve both attributes off the same `course` element already parsed for
   `display_name`/`language`/`license`:
   ```python
   self.course_image_path = self._resolve_static_attr(course, "course_image")
   self.banner_image_path = self._resolve_static_attr(course, "banner_image")
   ```
   New helper, since both attributes need the same "strip an optional `/static/` prefix, look up
   in `self.static_files`, warn if declared-but-missing" handling:
   ```python
   def _resolve_static_attr(self, course: ET.Element, attr: str) -> Path | None:
       """Resolve an OLX course-root attribute naming a `static/` asset to its local path."""
       raw = course.get(attr)
       if not raw:
           return None
       name = raw.removeprefix("/static/")
       path = self.static_files.get(name)
       if path is None:
           log.warning("Parsing OLX: course declares %s=%r but no such static file exists", attr, raw)
       return path
   ```
   Place the two calls right after the existing `static_dir` indexing loop (`olx.py:82-86`), since
   that's the earliest point `self.static_files` is populated.

3. **Templates (`ocw/templates.py`)**: parametrize `FILE_ENTRY`'s `filearea` (currently hardcoded)
   and let `itemid`/`sortorder` vary too, since course-context files need `filearea=overviewfiles`,
   `itemid=0`, and a controlled `sortorder`:
   ```python
   FILE_ENTRY = (
       '  <file id="{id}"><contenthash>{sha1}</contenthash>'
       "<contextid>{ctx}</contextid><component>{component}</component>"
       "<filearea>{filearea}</filearea><itemid>{itemid}</itemid>"
       "<filepath>/</filepath><filename>{name}</filename>"
       "<filesize>{size}</filesize><mimetype>{mime}</mimetype>"
       "<status>0</status><timecreated>{ts}</timecreated>"
       "<timemodified>{ts}</timemodified><sortorder>{sortorder}</sortorder>"
       "<userid>2</userid><repositorytype>$@NULL@$</repositorytype>"
       "<repositoryid>$@NULL@$</repositoryid>"
       "<source>$@NULL@$</source><author>$@NULL@$</author>"
       "<license>allrightsreserved</license>"
       "<reference>$@NULL@$</reference></file>"
   )
   ```

4. **Builder (`ocw/converter/builder.py`)**:

   a. `_build_file_entries` currently defaults every entry's `filearea`/`itemid`/`sortorder`
      implicitly via the template's old hardcoded values. Give existing callers explicit defaults
      so behaviour for every non-course-image file stays identical:
      ```python
      file_entries.append(
          {
              "id": fid,
              "sha1": sha1,
              "name": name,
              "size": path.stat().st_size,
              "mime": mime,
              "path": path,
              "ctx": page["ctx"],
              "component": page.get("component", "mod_page"),
              "filearea": "content",
              "itemid": 0,
              "sortorder": 0,
          }
      )
      ```

   b. New method, called from `_populate` right after the existing `_build_file_entries` call
      (`builder.py:136`):
      ```python
      def _build_course_image_entries(self, c: BaseParser, ids: _Counter) -> list[dict]:
          """Build course-context `overviewfiles` file records for the course image and banner."""
          entries: list[dict] = []
          for sortorder, path in enumerate(
              p for p in (c.course_image_path, c.banner_image_path) if p is not None
          ):
              entries.append(
                  {
                      "id": ids.next(),
                      "sha1": sha1_of(path),
                      "name": path.name,
                      "size": path.stat().st_size,
                      "mime": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                      "path": path,
                      "ctx": 1,
                      "component": "course",
                      "filearea": "overviewfiles",
                      "itemid": 0,
                      "sortorder": sortorder,
                  }
              )
          return entries
      ```
      `ctx=1` matches the fixed course context already hardcoded in `templates.py:111`. Iterating
      `course_image_path` before `banner_image_path` puts the thumbnail at `sortorder=0`, so it's
      the one Moodle picks for the catalogue tile; the banner rides along in the same filearea at
      `sortorder=1`, embedded in the `.mbz` but not wired to any rendering path, ready for once the
      vendor theme/plugin answer lands (per Jorrit's own "get back to you" on that half).

   c. Wire it into `_populate` (`builder.py:136-138`):
      ```python
      file_entries = self._build_file_entries(c, pages + resources, ids)
      file_entries += self._build_course_image_entries(c, ids)
      self._write_all(
          tmp, c, all_sections, sub_mods, pages, resources, file_entries, ts, ids
      )
      ```

   d. `_write_files_xml` needs to pass the new fields through:
      ```python
      entries = "\n".join(
          templates.FILE_ENTRY.format(
              id=f["id"],
              sha1=f["sha1"],
              name=esc(f["name"]),
              size=f["size"],
              mime=esc(f["mime"]),
              ctx=f["ctx"],
              component=f["component"],
              filearea=f["filearea"],
              itemid=f["itemid"],
              sortorder=f["sortorder"],
              ts=ts,
          )
          for f in file_entries
      )
      ```
   `_copy_static` needs no change, it already just keys off `sha1`/`path`.

## Files changed

* `ocw/parser/base.py`: `course_image_path`/`banner_image_path` fields.
* `ocw/parser/olx.py`: `_resolve_static_attr` helper + two calls in `Course.parse()`.
* `ocw/templates.py`: `FILE_ENTRY` gains `{filearea}`/`{itemid}`/`{sortorder}` placeholders.
* `ocw/converter/builder.py`: `_build_file_entries` explicit defaults, new
  `_build_course_image_entries`, `_populate` wiring, `_write_files_xml` new format kwargs.

## Test plan

* New unit/integration coverage (mirroring existing `tests/integration/test_wp_requirements.py`-
  style OLX requirement tests, wherever the OLX equivalent lives): a fixture course with both
  `course_image` and `banner_image` set builds two `files.xml` entries with
  `component=course`/`filearea=overviewfiles`/`contextid=1`, correct `sortorder`, and matching
  payload files land in `files/<sha1[:2]>/<sha1>`. A fixture course with neither attribute set
  emits no such entries (regression guard on existing courses without either image).
* A fixture course that declares `course_image` but has no matching file under `course/static/`
  logs the warning and doesn't crash the build.
* Manual: restore a built `.mbz` for a real course (e.g. `URED1x`, confirmed to have both
  attributes above) into the local Moodle instance, check Settings > Description > Course image
  shows the thumbnail.

## Not doing

* WP course image/banner — needs either a live page fetch (blocked by house rule, would need
  explicit go-ahead) or a pasted HTML sample from Jorrit/you before it's buildable.
* Wiring the banner into any actual rendering path — blocked on the vendor's theme/UI answer per
  Jorrit's email; this plan only gets it embedded in the `.mbz` and sitting in `overviewfiles`,
  not displayed anywhere yet.
