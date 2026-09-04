"""Parse WordPress course sites into the normalised data consumed by `MBZBuilder`."""

import itertools
import logging
from collections import Counter

import requests
from bs4 import BeautifulSoup
from bs4.element import NavigableString

from ocw.fetcher import AssetFetcher
from ocw.parser.base import BaseParser
from ocw.utils import resolve_asset_name, safe_vidkey, warn_external_wp_urls

log = logging.getLogger("ocw.wp_parser")


class WPCourse(BaseParser):
    """Parse a WordPress course site's HTML navigation and content into course records.

    The parser follows the site's chapter and activity navigation rather than using a WordPress
    API.
    """

    _SKIPPED_ICON_TYPES = frozenset({"icon--exercise", "icon--exam", "icon--mooc"})

    _ALIGN_STYLES = {
        "alignleft": "float:left;margin:0 1em 1em 0;",
        "alignright": "float:right;margin:0 0 1em 1em;",
        "aligncenter": "display:block;margin:0 auto 1em;",
    }
    _VC_ALIGN_STYLES = {
        "vc_align_left": "float:left;margin:0 1em 1em 0;",
        "vc_align_right": "float:right;margin:0 0 1em 1em;",
        "vc_align_center": "display:block;margin:0 auto 1em;",
    }

    _FA_WOFF2_URL = "https://maxcdn.bootstrapcdn.com/font-awesome/4.3.0/fonts/fontawesome-webfont.woff2?v=4.3.0"
    _FA_WOFF_URL = "https://maxcdn.bootstrapcdn.com/font-awesome/4.3.0/fonts/fontawesome-webfont.woff?v=4.3.0"
    _DOWNLOAD_CSS = (
        "<style>"
        ".vc_download>a{display:block;min-height:90px;text-decoration:none;color:#222;"
        "border-top:1px solid #9b9b8b;border-bottom:1px solid #9b9b8b;"
        "padding-top:20px;padding-bottom:20px;padding-left:60px}"
        ".vc_download>a:before{display:block;width:40px;height:40px;line-height:40px;"
        "text-align:center;color:#fff;border-radius:3px;background:#222;padding:0;"
        "position:absolute;top:24px;left:0px;font-size:1rem}"
        ".vc_download>a>strong{display:block;text-decoration:underline}"
        ".ocw-vc-row{display:flex;flex-wrap:wrap;gap:0 20px}"
        ".ocw-vc-row>.vc_download{flex:1 1 0;min-width:220px}"
        ".ocw-vc-icon{position:relative}"
        ".ocw-vc-icon:before{font:normal normal normal 24px/1 FontAwesome;text-rendering:auto;"
        "-webkit-font-smoothing:antialiased}"
        "@font-face{font-family:'FontAwesome';"
        "src:url('@@PLUGINFILE@@/fontawesome-webfont.woff2') format('woff2'),"
        "url('@@PLUGINFILE@@/fontawesome-webfont.woff') format('woff');"
        "font-weight:normal;font-style:normal}"
        '.fa-file:before{content:"\\f15b"}'
        "</style>"
    )

    def __init__(self, root: str, fetcher: AssetFetcher | None = None) -> None:
        super().__init__(root, fetcher)
        self._session = requests.Session()
        # URL -> parsed canonical reading vertical (or None), for dedup across subject pages.
        self._reading_pages: dict[str, dict | None] = {}
        # URL -> parsed canonical lecture vertical, for dedup across subject pages.
        self._lecture_pages: dict[str, dict] = {}
        # Lecture URL -> number of subject pages referencing it, from a pre-scan pass in
        # `parse()`. Only URLs referenced 2+ times get routed through the dedup/Hidden-section
        # mechanism (see `_parse_lecture`); direct calls that bypass `parse()` (unit tests) get
        # an empty Counter, i.e. every URL defaults to "single reference".
        self._lecture_ref_counts: Counter[str] = Counter()

    def parse(self) -> None:
        """Parse the course home page, its subject pages, and all video components."""
        home = self._fetch_page(self.root)
        self.course_name = home.select_one("h1").get_text(strip=True)
        self._parse_home_summary(home)
        subjects = self._parse_subjects_sidebar(home)
        self._lecture_ref_counts = self._count_lecture_references(
            url for url, _ in subjects
        )
        for subject_url, subject_title in subjects:
            self.chapters.append(self._parse_subject_page(subject_url, subject_title))
        self.videos = [
            comp
            for chapter in self.chapters
            for sequential in chapter["sequentials"]
            for vertical in sequential["verticals"]
            for comp in vertical["components"]
            if comp["type"] == "video"
        ] + [
            comp
            for page in self.dedup_pages
            for comp in page["components"]
            if comp["type"] == "video"
        ]

    def _parse_home_summary(self, home: BeautifulSoup) -> None:
        """Extract the home page's course description into `overview_summary_html`, so
        `MBZBuilder._alloc_sections` puts it directly in the Overview section's own summary body
        -- otherwise that section shows no description at all.

        WPBakery tabs widgets (`vc_tta-container`) wrap the "Overview"/"What you will learn"
        panels' real content in `.vc_tta-panel-body`; the tab labels and accordion headings are
        siblings of those, not descendants, so selecting just the panel bodies drops the
        tab-switcher chrome. Pages without a tabs widget fall back to the whole article.
        """
        article = home.select_one("article")
        if article is None:
            return
        self._clean_article(article)
        panels = article.select(".vc_tta-panel-body")
        elements = panels if panels else [article]
        html = "".join(
            "".join(str(child) for child in el.contents) for el in elements
        ).strip()
        if not html:
            return
        warn_external_wp_urls(html, context="course overview")
        self.overview_summary_html = html

    def _parse_subjects_sidebar(self, home: BeautifulSoup) -> list[tuple[str, str]]:
        """Return top-level chapter URLs and titles from the course navigation.

        Matches the stable `ul.activities` wrapper because the heading above it varies between
        sites.
        """
        activities = home.select_one("ul.activities")
        if activities is None:
            log.warning("No chapter list found on %s", self.root)
            return []
        return [(a["href"], a.get_text(strip=True)) for a in activities.find_all("a")]

    def _convert_expandable_widgets(self, article) -> None:
        """Replace JavaScript-driven WordPress expandable widgets with native `details` elements.

        Widgets without content are removed.
        """
        for widget in article.select("div.vc_expandable_text"):
            text_div = widget.select_one("div.vc_expandable_text__text")
            if text_div is None:
                widget.decompose()
                continue
            if "style" in text_div.attrs:
                del text_div["style"]
            toggle = widget.select_one("span.vc_expandable_text__more")
            label = (toggle.get("data-label-more") if toggle else None) or "Read more"
            if toggle is not None:
                toggle.decompose()
            widget.name = "details"
            del widget["class"]
            summary = widget.new_tag("summary")
            summary.string = label
            text_div.insert_before(summary)

    def _apply_wp_image_alignment(self, article) -> None:
        """Translate WordPress `alignleft`/`alignright`/`aligncenter` image classes into inline
        float styles, since Moodle's theme has no CSS for WordPress's align classes.

        WPBakery's `vc_single_image` shortcode puts the alignment class (`vc_align_left`/
        `vc_align_right`/`vc_align_center`) on an ancestor wrapper div instead of the `<img>`
        itself, so that case is checked separately.
        """
        for img in article.select("img"):
            classes = img.get("class") or []
            align = next((c for c in classes if c in self._ALIGN_STYLES), None)
            if align is not None:
                img["style"] = self._ALIGN_STYLES[align] + img.get("style", "")
                continue
            wrapper = img.find_parent(class_=lambda c: c in self._VC_ALIGN_STYLES)
            if wrapper is not None:
                wrapper_align = next(
                    c for c in wrapper["class"] if c in self._VC_ALIGN_STYLES
                )
                img["style"] = self._VC_ALIGN_STYLES[wrapper_align] + img.get(
                    "style", ""
                )

    def _replace_separators(self, article) -> None:
        """Replace WPBakery `vc_separator` dividers with `<hr>`; the original markup depends on
        Visual Composer CSS Moodle doesn't ship, so it renders as invisible empty elements.
        """
        for sep in article.select("div.vc_separator"):
            sep.replace_with(article.new_tag("hr"))

    def _clean_article(self, article) -> None:
        """Apply all WordPress-widget-to-Moodle-safe-HTML conversions to `article`."""
        self._convert_expandable_widgets(article)
        self._apply_wp_image_alignment(article)
        self._replace_separators(article)
        self._fix_download_tool_widgets(article)
        self._localize_images(article)

    def _localize_images(self, article) -> None:
        """Fetch external `<img>` sources (`src` and `srcset`) locally and rewrite them to the
        `/static/` convention.

        Images that cannot be fetched (unsupported type, request failure) are left pointing at
        their original source.
        """
        for img in article.select("img"):
            src = img.get("src")
            if src and src.startswith("http"):
                name = self._resolve_and_fetch(src)
                if name:
                    img["src"] = f"/static/{name}"
            srcset = img.get("srcset")
            if srcset:
                img["srcset"] = self._localize_srcset(srcset)

    def _localize_srcset(self, srcset: str) -> str:
        """Rewrite each URL in a `srcset` attribute the same way as `src`, keeping each
        candidate's width/density descriptor intact."""
        candidates = []
        for candidate in srcset.split(","):
            parts = candidate.split()
            if not parts:
                continue
            url, *descriptor = parts
            if url.startswith("http"):
                name = self._resolve_and_fetch(url)
                if name:
                    url = f"/static/{name}"
            candidates.append(" ".join([url, *descriptor]))
        return ", ".join(candidates)

    _TUD_HOST_CHECK = 'TUD_location.indexOf("ocw.tudelft.nl")!=-1'
    _TUD_HOST_CHECK_FORCED = "true"

    def _fix_download_tool_widgets(self, article) -> None:
        """Patch WordPress's `#download_tool` widget so it actually works when served from Moodle.

        The widget's own bootstrap script branches on whether `location.href` contains
        "ocw.tudelft.nl": the true branch loads jQuery itself before using it; the false branch
        (taken on Moodle) assumes jQuery is already global, which is only true on WP. Forcing the
        host check permanently true makes the widget always take the self-contained branch.
        """
        for widget in article.select("#download_tool"):
            for script in widget.select("script"):
                if script.string and self._TUD_HOST_CHECK in script.string:
                    script.string = script.string.replace(
                        self._TUD_HOST_CHECK, self._TUD_HOST_CHECK_FORCED
                    )

    def _excluded_imgs(self, article) -> set[str]:
        """Return image srcs the parser already intentionally drops on purpose, so the
        content-loss audit doesn't flag them as false positives.

        Covers the licence footer's CC badge (`section.license`, skipped in
        `_classify_lecture_child`/`_reading_body_html`).
        """
        excluded: set[str] = set()
        for region in article.select("section.license"):
            excluded.update(
                img["src"] for img in region.select("img") if img.get("src")
            )
        return excluded

    def _audit_content_loss(
        self,
        expected_imgs: set[str],
        expected_iframe_srcs: set[str],
        expected_separators: int,
        components: list[dict],
        found_iframe_srcs: set[str],
        url: str,
        expected_downloads: int = 0,
        found_downloads: int = 0,
    ) -> None:
        """Warn about img/iframe/separator/download content present on the source page but
        missing from the built components. Detection only — never changes what gets built.

        Expected sets/counts must be captured before `_clean_article` mutates the article
        (separator divs are replaced in place, so a post-clean count is always zero).

        `found_iframe_srcs` covers iframes already pulled out into their own video components
        (the lecture path); iframes left embedded raw inside an `"html"` component (the reading
        path, which doesn't route through `_lecture_videos` at all) are picked up here instead.

        `expected_downloads`/`found_downloads` cover `vc_download` blocks; only the lecture path
        passes real values (readings resolve their own single download separately, outside this
        loop, and are warned about there instead).
        """
        found_imgs: set[str] = set()
        found_iframe_srcs = set(found_iframe_srcs)
        found_hrs = 0
        for comp in components:
            if comp["type"] != "html":
                continue
            frag = BeautifulSoup(comp["content"], "lxml")
            found_imgs.update(
                img["src"] for img in frag.select("img") if img.get("src")
            )
            found_iframe_srcs.update(
                el["src"] for el in frag.select("iframe") if el.get("src")
            )
            found_hrs += len(frag.select("hr"))

        found_names = {resolve_asset_name(src) for src in found_imgs}
        expected_by_name = {resolve_asset_name(src): src for src in expected_imgs}
        for name, src in sorted(expected_by_name.items()):
            if name not in found_names:
                log.warning(
                    "Parsing WP: image '%s' present on page but not captured in any component at %s",
                    src,
                    url,
                )
        for src in sorted(expected_iframe_srcs - found_iframe_srcs):
            log.warning(
                "Parsing WP: iframe '%s' present on page but not captured in any component at %s",
                src,
                url,
            )
        if expected_separators != found_hrs:
            log.warning(
                "Parsing WP: %d separator(s) present on page but only %d <hr> captured at %s",
                expected_separators,
                found_hrs,
                url,
            )
        if expected_downloads != found_downloads:
            log.warning(
                "Parsing WP: %d download(s) present on page but only %d captured at %s",
                expected_downloads,
                found_downloads,
                url,
            )

    def _find_activities_list(self, article):
        """Return the `ul.activities` wrapper among `article`'s direct children, or `None`."""
        if article is None:
            return None
        for child in article.find_all(recursive=False):
            if child.name == "ul" and "activities" in (child.get("class") or []):
                return child
        return None

    def _count_lecture_references(self, subject_urls) -> "Counter[str]":
        """Pre-scan every subject page and count how many link to each lecture URL.

        Must run before any subject page is fully parsed, so `_parse_lecture` can tell a lecture
        referenced from exactly one subject (build inline, like a normal page) from one
        referenced from several (route through the dedup/Hidden-section mechanism instead of
        duplicating it once per subject).
        """
        counts: Counter[str] = Counter()
        for url in subject_urls:
            soup = self._fetch_page(url)
            activities = self._find_activities_list(soup.select_one("article"))
            if activities is None:
                continue
            for a in activities.select("a.icon.icon--lecture"):
                counts[a["href"]] += 1
        return counts

    def _parse_subject_page(self, url: str, title: str) -> dict:
        """Parse one subject page into a chapter record.

        Content before the activity list becomes the chapter summary. Activity groups become
        sequentials and their links become verticals.
        """
        soup = self._fetch_page(url)
        article = soup.select_one("article")
        if article is not None:
            self._clean_article(article)
        intro_rows = []
        activities = None
        if article is not None:
            for child in article.find_all(recursive=False):
                if child.name == "ul" and "activities" in (child.get("class") or []):
                    activities = child
                    break
                if child.name == "div" and "vc_row" in (child.get("class") or []):
                    intro_rows.append(child)
        if activities is None:
            log.warning("No activities list found on subject page '%s'", url)
            return {"display_name": title, "sequentials": []}
        sequentials = []
        for group in activities.find_all("li", recursive=False):
            seq_title_el = group.select_one("span.course-title")
            seq_title = seq_title_el.get_text(strip=True) if seq_title_el else title
            verticals = [
                v
                for a in group.select("ul a.icon")
                if (v := self._parse_item(a, title, seq_title)) is not None
            ]
            sequentials.append({"display_name": seq_title, "verticals": verticals})
        chapter = {"display_name": title, "sequentials": sequentials}
        if intro_rows:
            summary_html = "".join(str(row) for row in intro_rows)
            warn_external_wp_urls(summary_html, context=title)
            chapter["summary_html"] = summary_html
        return chapter

    def _parse_item(self, link, chapter_name: str, sequential_name: str) -> dict | None:
        """Dispatch one activity link according to its `icon--...` class.

        Configured unsupported icon types are skipped. Unknown types produce a warning.
        """
        icon_type = next(
            (c for c in link.get("class", []) if c.startswith("icon--")), ""
        )
        if icon_type in self._SKIPPED_ICON_TYPES:
            return None
        title = link.get_text(strip=True)
        if icon_type == "icon--lecture":
            return self._parse_lecture(
                link["href"], title, chapter_name, sequential_name
            )
        if icon_type == "icon--reading":
            return self._parse_reading(link["href"], title)
        log.warning(
            "Unhandled WP item type '%s' at %s", icon_type or "<none>", link["href"]
        )
        return None

    def _parse_lecture(
        self, url: str, title: str, chapter_name: str, sequential_name: str
    ) -> dict:
        """Build `url`'s lecture vertical, deduping it only if it's genuinely referenced from
        multiple subjects.

        A URL referenced from 2+ subjects (per `self._lecture_ref_counts`, populated by
        `parse()`'s pre-scan) returns an in-course link on every occurrence (including the
        first), resolved to a Moodle page ID at build time (see
        `SectionStrategy._build_dedup_url`); its real page is built at most once, into
        `self.dedup_pages`, for `MBZBuilder._build_wp_dedup_section` to place in one hidden,
        unlisted section -- it should exist once in the backup, not N times. A URL referenced
        from just one subject (or parsed directly, bypassing `parse()`'s pre-scan -- e.g. unit
        tests) builds inline instead, exactly like any other page.
        """
        if self._lecture_ref_counts.get(url, 0) >= 2:
            if url not in self._lecture_pages:
                result = self._parse_lecture_uncached(
                    url, title, chapter_name, sequential_name
                )
                self._lecture_pages[url] = result
                self.dedup_pages.append(result)
            return {
                "display_name": title,
                "components": [{"type": "dedup_link", "dedup_url": url}],
            }
        if url not in self._lecture_pages:
            self._lecture_pages[url] = self._parse_lecture_uncached(
                url, title, chapter_name, sequential_name
            )
        return {
            "display_name": title,
            "components": self._lecture_pages[url]["components"],
        }

    def _parse_lecture_uncached(
        self, url: str, title: str, chapter_name: str, sequential_name: str
    ) -> dict:
        """Parse one lecture page into a vertical record.

        Preserves descriptive HTML in source order, extracts YouTube or Collegerama videos, and
        turns a linked PDF into a local file link when it can be resolved.
        """
        soup = self._fetch_page(url)
        article = soup.select_one("article")
        expected_imgs = (
            {img["src"] for img in article.select("img") if img.get("src")}
            - self._excluded_imgs(article)
            if article
            else set()
        )
        expected_iframe_srcs = (
            {el["src"] for el in article.select("iframe") if el.get("src")}
            if article
            else set()
        )
        expected_separators = len(article.select("div.vc_separator")) if article else 0
        expected_downloads = len(article.select("div.vc_download")) if article else 0
        if article is not None:
            self._clean_article(article)
        total_videos = (
            len([el for el in article.select("iframe") if self._is_playable_video(el)])
            if article
            else 0
        )
        multiple = total_videos > 1
        video_index = itertools.count(1)
        components = []
        found_iframe_srcs: set[str] = set()
        found_downloads = 0
        for child in article.find_all(recursive=False) if article else []:
            for kind, value in self._classify_lecture_child(
                child, url, title, chapter_name, sequential_name, multiple, video_index
            ):
                if kind == "component":
                    components.append(value)
                elif kind == "pdf_url_group":
                    boxes = []
                    for block in value:
                        name = self._resolve_and_fetch(block["href"])
                        if name:
                            boxes.append(self._download_link_component(name, block)["content"])
                            found_downloads += 1
                    if boxes:
                        self._ensure_download_css(components)
                        content = (
                            f'<div class="ocw-vc-row">{"".join(boxes)}</div>'
                            if len(boxes) > 1
                            else boxes[0]
                        )
                        components.append({"type": "html", "content": content})
                elif kind == "video_src":
                    found_iframe_srcs.add(value)

        self._audit_content_loss(
            expected_imgs,
            expected_iframe_srcs,
            expected_separators,
            components,
            found_iframe_srcs,
            url,
            expected_downloads=expected_downloads,
            found_downloads=found_downloads,
        )
        self._warn_external_wp_links(components, title)
        return {"display_name": title, "components": components, "dedup_url": url}

    def _warn_external_wp_links(self, components: list[dict], context: str) -> None:
        """Warn about any `html` component still linking back to ocw.tudelft.nl."""
        for comp in components:
            if comp["type"] == "html":
                warn_external_wp_urls(comp["content"], context=context)

    def _download_link_component(self, name: str, block: dict) -> dict:
        """Build the vc_download-style HTML block for one resolved download link.

        Uses the block's own caption/filename (never the lecture/page title) so multiple
        downloads on one page get distinct, meaningful link text.
        """
        caption = block["caption"] or block["filename"]
        return {
            "type": "html",
            "content": (
                '<div class="vc_download"><a class="ocw-vc-icon fa-file" target="_blank" '
                f'href="/static/{name}"><strong>{caption}</strong>{block["filename"]}</a></div>'
            ),
        }

    def _ensure_download_css(self, components: list[dict]) -> None:
        """Fetch the download box's Font Awesome webfont (once per course, deduped through
        `static_files` like any other asset) and add its `<style>` block to `components` (once
        per page)."""
        woff2_name = resolve_asset_name(self._FA_WOFF2_URL)
        if woff2_name not in self.static_files:
            self._resolve_and_fetch(self._FA_WOFF2_URL)
            self._resolve_and_fetch(self._FA_WOFF_URL)
        if not any(
            c["content"] == self._DOWNLOAD_CSS
            for c in components
            if c["type"] == "html"
        ):
            components.append({"type": "html", "content": self._DOWNLOAD_CSS})

    def _classify_lecture_child(
        self,
        child,
        url: str,
        title: str,
        chapter_name: str,
        sequential_name: str,
        multiple: bool,
        video_index,
    ) -> list[tuple[str, object]]:
        """Classify one top-level lecture element into zero or more (kind, value) results.

        `kind` is `"component"` (a page or video component), `"pdf_url_group"` (one or more
        `vc_download` blocks found together under this element, kept together so sibling
        downloads from the same WPBakery row render side by side), or `"video_src"`. An
        element carrying one or more playable iframes and no other real content (WPBakery's
        `wpb_video_widget` wrapper) is consumed whole as video. An element that mixes iframe(s)
        with other real content -- WPBakery nests video and text/image columns several layout-div
        levels deep inside one shared row -- is recursed into instead, so its non-video siblings
        aren't swallowed along with the video.

        `multiple` and `video_index` are shared across the whole page (computed once in
        `_parse_lecture`) rather than reset per element, so pages that lay out each video in its
        own separate top-level row (instead of one shared wrapper) still get a unique routing key
        per video instead of every video colliding on the same unsuffixed key.
        """
        if child.name == "h1":
            return []
        if child.name == "section" and "license" in (child.get("class") or []):
            return []
        if child.name == "p" and "article__link-list" in (child.get("class") or []):
            return []

        iframes = [child] if child.name == "iframe" else child.select("iframe")
        if iframes:
            if self._is_video_only(child, iframes):
                videos = self._lecture_videos(
                    iframes,
                    url,
                    title,
                    chapter_name,
                    sequential_name,
                    multiple,
                    video_index,
                )
                results = []
                for component, src in videos:
                    results.append(("component", component))
                    results.append(("video_src", src))
                return results
            results = []
            for grandchild in child.find_all(recursive=False):
                results.extend(
                    self._classify_lecture_child(
                        grandchild,
                        url,
                        title,
                        chapter_name,
                        sequential_name,
                        multiple,
                        video_index,
                    )
                )
            return results

        dl_blocks = self._find_download_link(child)
        if dl_blocks:
            return [("pdf_url_group", dl_blocks)]

        if (
            child.get_text(strip=True)
            or child.name in ("img", "hr")
            or child.find(["img", "hr"])
        ):
            return [("component", {"type": "html", "content": str(child)})]
        return []

    @staticmethod
    def _is_video_only(child, iframes: list) -> bool:
        """True when `child` (already known to contain `iframes`) has no other real content --
        text, image, or `<hr>` -- outside of those iframes, so it's safe to consume whole as
        video instead of recursing into its children individually."""
        if child.name == "iframe":
            return True
        if child.select("img") or child.select("hr"):
            return False
        return not child.get_text(strip=True)

    @staticmethod
    def _is_playable_video(iframe) -> bool:
        """True when `iframe` embeds a YouTube or Collegerama video we route through vidrouter."""
        src = iframe.get("src") or ""
        return "youtube.com" in src or "collegerama.tudelft.nl" in src

    def _lecture_videos(
        self,
        iframes: list,
        url: str,
        title: str,
        chapter_name: str,
        sequential_name: str,
        multiple: bool,
        video_index,
    ) -> list[tuple[dict, str]]:
        """Build one (component, source iframe src) pair per iframe in `iframes`. `src` is
        returned only for content-loss auditing.
        """
        videos = [el for el in iframes if el.get("src")]
        results = []
        for iframe in videos:
            src = iframe["src"]
            index = next(video_index) if multiple else None
            if "youtube.com" in src:
                youtubeid = src.rstrip("/").split("/")[-1].split("?")[0]
                component = self._video_component(
                    url,
                    title,
                    chapter_name,
                    sequential_name,
                    youtubeid=youtubeid,
                    index=index,
                )
                results.append((component, src))
            elif "collegerama.tudelft.nl" in src:
                collegeramaid = src.rstrip("/").split("/")[-1]
                component = self._video_component(
                    url,
                    title,
                    chapter_name,
                    sequential_name,
                    collegeramaid=collegeramaid,
                    index=index,
                )
                results.append((component, src))
            else:
                results.append(({"type": "html", "content": str(iframe)}, src))
        return results

    def _video_component(
        self,
        url: str,
        title: str,
        chapter_name: str,
        sequential_name: str,
        *,
        youtubeid: str | None = None,
        collegeramaid: str | None = None,
        index: int | None = None,
    ) -> dict:
        """Build a video-routing record for a WordPress lecture page.

        The routing key derives from the page URL slug, suffixed with `index` when the page
        embeds more than one video so each gets a distinct key. WordPress supplies YouTube or
        Collegerama IDs, while edX, SRT, and TUD download identifiers remain unset.
        """
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        if index is not None:
            slug = f"{slug}-{index}"
        return {
            "type": "video",
            "display_name": title,
            "vidkey": safe_vidkey(slug),
            "youtubeid": youtubeid,
            "edxvideoid": None,
            "srtbaseid": None,
            "tuddownloadid": None,
            "collegeramaid": collegeramaid,
            "urlname": slug,
            "videopagepath": f"{chapter_name} > {sequential_name} > {title}",
        }

    def _parse_reading(self, url: str, title: str) -> dict | None:
        """Every occurrence of `url` (including the first) returns an in-course link, resolved
        to a Moodle page ID at build time (see `SectionStrategy._build_page`).

        `url`'s real page is built at most once, into `self.reading_pages`, for
        `MBZBuilder._build_wp_readings_section` to place in a standalone Readings section --
        mirroring the OLX layout instead of leaving the canonical page inline in whichever
        subject happened to link it first.
        """
        if url not in self._reading_pages:
            result = self._parse_reading_uncached(url, title)
            self._reading_pages[url] = result
            if result is not None:
                self.reading_pages.append(result)
        if self._reading_pages[url] is None:
            return None
        return {
            "display_name": title,
            "components": [{"type": "reading_link", "reading_url": url}],
        }

    def _parse_reading_uncached(self, url: str, title: str) -> dict | None:
        """Parse one reading page into an HTML vertical with its own styled download box.

        Returns `None` when no reading body and no download resolve.
        """
        soup = self._fetch_page(url)
        components = []
        text_html = self._reading_body_html(soup, url)
        if text_html:
            components.append({"type": "html", "content": text_html})

        dl_blocks = self._find_download_link(soup)
        if dl_blocks:
            name = self._resolve_and_fetch(dl_blocks[0]["href"])
            if name is None:
                log.warning(
                    "Parsing WP: Missing pdf for Readings entry '%s' at %s", title, url
                )
            else:
                self._ensure_download_css(components)
                components.append(self._download_link_component(name, dl_blocks[0]))

        if not components:
            return None
        return {"display_name": title, "components": components, "reading_url": url}

    def _reading_body_html(self, soup: BeautifulSoup, url: str) -> str:
        """Extract reading-body HTML without the title, PDF download control, licence footer, or
        subject link list."""
        article = soup.select_one("article")
        if article is None:
            return ""
        expected_imgs = {
            img["src"] for img in article.select("img") if img.get("src")
        } - self._excluded_imgs(article)
        expected_iframe_srcs = {
            el["src"] for el in article.select("iframe") if el.get("src")
        }
        expected_separators = len(article.select("div.vc_separator"))
        self._clean_article(article)
        parts = []
        for child in article.find_all(recursive=False):
            if child.name == "h1":
                continue
            if child.name == "section" and "license" in (child.get("class") or []):
                continue
            if child.name == "p" and "article__link-list" in (child.get("class") or []):
                continue
            if self._find_download_link(child):
                continue
            if (
                child.get_text(strip=True)
                or child.name in ("img", "hr")
                or child.find(["img", "hr"])
            ):
                parts.append(str(child))
        html = "".join(parts)
        self._audit_content_loss(
            expected_imgs,
            expected_iframe_srcs,
            expected_separators,
            [{"type": "html", "content": html}],
            set(),
            url,
        )
        warn_external_wp_urls(html, context=url)
        return html

    def _resolve_and_fetch(self, asset_url: str) -> str | None:
        """Return the local static-file name for an asset (PDF, download, webfont...), fetching
        it when configured.

        Successfully fetched assets are registered in `static_files`.
        """
        name = resolve_asset_name(asset_url)
        if name in self.static_files:
            return name
        if self.fetcher is None:
            return None
        fetched = self.fetcher.fetch(asset_url)
        if fetched is None:
            return None
        self.static_files[fetched.name] = fetched
        return fetched.name

    def _find_download_link(self, node) -> list[dict]:
        """Return one entry per WordPress `vc_download` block in or below `node`.

        Each entry is `{"href": str, "caption": str | None, "filename": str}`. `caption` is the
        block's `<strong>` text when present; `filename` is the anchor's remaining direct text
        (falls back to the href's basename when the source page has none).
        """
        classes = node.get("class") or []
        containers = (
            [node] if "vc_download" in classes else node.select("div.vc_download")
        )
        blocks = []
        for container in containers:
            link = container.select_one("a.icon.fa-file")
            if link is None or not link.get("href"):
                continue
            href = link["href"]
            strong = link.select_one("strong")
            caption = strong.get_text(strip=True) if strong else None
            filename = "".join(
                c for c in link.contents if isinstance(c, NavigableString)
            ).strip() or resolve_asset_name(href)
            blocks.append({"href": href, "caption": caption, "filename": filename})
        return blocks

    def _fetch_page(self, url: str) -> BeautifulSoup:
        """Fetch `url` and parse its HTML with lxml.

        HTTP failures propagate to the conversion workflow.
        """
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
