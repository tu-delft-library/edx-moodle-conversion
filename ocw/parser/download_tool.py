"""Inline the DelftxDownloads widget from its server-rendered tool page.

On edX and WordPress the widget is an iframe of `TUD_download_tool.php`, set up client-side by
builder.js. Under Moodle that script chain breaks (resizer.js hands off to Moodle's RequireJS,
which throws "Mismatched anonymous define() module"), so the tool page is fetched at parse time
and its markup inlined instead, with native `details` dropdowns so no JS is needed.
"""

from collections.abc import Callable
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup, Tag

_TOOL_URL = (
    "https://delftxdownloads.tudelft.nl/_tools/dl/TUD_download_tool.php"
    "?src={src}&path={download_id}&lang={lang}&ft={filetype}&ccSA={cc_sa}&ccNC={cc_nc}"
)

# base-styles.css + ocw-styles.css from the tool page, scoped to the widget, with the jQuery
# `.tud-open` toggle class swapped for native `details[open]`. Dropdowns flow in-layout rather
# than absolutely positioned, since Moodle's `.no-overflow` content wrapper would otherwise clip
# them into a scrollbox.
CSS = (
    "<style>"
    ".TUD_box_download{margin:0;padding:12px 12px .5em 12px;border-radius:5px;clear:both;"
    "min-height:3em;box-sizing:content-box;font-family:Arial,Helvetica,sans-serif}"
    ".TUD_box_download a{text-decoration:none}"
    ".TUD_box_download .tud-float{float:left}"
    ".TUD_box_download .no-float{float:none;clear:both}"
    ".tud-button{position:relative;display:inline-block;margin:0 1em 1em 0;"
    "vertical-align:top}"
    ".tud-button-top{display:block;list-style:none;min-width:8em;padding:8px;height:24px;"
    "border:1px solid rgba(100,100,100,.2);background:#fff;border-radius:3px;"
    "box-sizing:content-box;cursor:pointer}"
    ".tud-button-top::-webkit-details-marker{display:none}"
    ".tud-button-top:hover{padding-bottom:calc(.5em - 3px);border-bottom:3px solid #00a6d6}"
    ".tud-button-top span{margin:.1em .5em 0 .5em}"
    ".tud-chevron-down{width:0;height:0;margin:.4em;border-left:7px solid transparent;"
    "border-right:7px solid transparent;border-top:12px solid #333;transform:scale(.8);"
    "transition:transform .2s;float:right}"
    ".tud-button[open] .tud-button-top{border-bottom-left-radius:0;"
    "border-bottom-right-radius:0}"
    ".tud-button[open] .tud-chevron-down{transform:scale(.9) rotate(180deg);"
    "margin-top:.3em;border-top:12px solid #646464}"
    ".tud-button ul.TUD{list-style:none;margin:0;padding:0 !important;width:100%;"
    "border:1px solid rgba(100,100,100,.2);border-top:none;"
    "border-bottom-left-radius:3px;border-bottom-right-radius:3px;background:#fff;"
    "box-sizing:border-box}"
    ".tud-button ul.TUD li.TUD{display:block;margin:0;padding:0;font-size:.95em;"
    "background:#fff;color:#000}"
    ".tud-button ul.TUD li.TUD:hover{background:#00a6d6;color:#fff}"
    ".tud-button ul.TUD li.TUD a{display:block;padding:.75em .5em;color:#000}"
    ".tud-button ul.TUD li.TUD:hover>a{color:#fff !important}"
    ".tud-button ul.TUD li.TUD:hover>a>span{color:#efefef !important}"
    ".tud-button ul.TUD li.TUD span.TUD{float:right;color:#646464}"
    ".TUD_subtext{font-size:.8em;clear:both;margin:0}"
    "</style>"
)


def tool_url(
    download_id: str,
    src: str,
    lang: str = "en",
    filetype: str = "mp4",
    cc_sa: str = "y",
    cc_nc: str = "y",
) -> str:
    """Build the tool page URL the same way builder.js sets the widget iframe's `src`."""
    return _TOOL_URL.format(
        src=src,
        download_id=quote(download_id, safe="/"),
        lang=lang,
        filetype=filetype,
        cc_sa=cc_sa,
        cc_nc=cc_nc,
    )


def inline_widget(
    page: BeautifulSoup, page_url: str, localize: Callable[[str], str | None]
) -> Tag:
    """Return the tool page's widget, ready to inline.

    `localize(url)` bundles an asset and returns its static-file name, or `None` when it can't.
    Images and the "Other" tab's files are bundled; Video/Subtitles links stay on
    delftxdownloads.
    """
    widget = page.select_one("div.TUD_box_download")
    for button in widget.select("div.tud-button"):
        button.name = "details"
        button["name"] = "tud-download"
        button.select_one("div.tud-button-top").name = "summary"
    for img in widget.select("img[src]"):
        url = urljoin(page_url, img["src"])
        name = localize(url)
        img["src"] = f"/static/{name}" if name else url
    for link in widget.select(".other-download a[href]"):
        name = localize(link["href"])
        if name:
            link["href"] = f"/static/{name}"
    widget.insert(0, BeautifulSoup(CSS, "html.parser").style)
    return widget


def replace_inline_boxes(
    root: Tag,
    src: str,
    fetch_page: Callable[[str], BeautifulSoup | None],
    localize: Callable[[str], str | None],
) -> list[str]:
    """Replace each inline `TUD_box_download` placeholder under `root` with the inlined widget.

    The placeholder's links stay `#` until the CDN script fills them, so a box without a download
    id is dropped, and one whose tool page can't be fetched is left as is. Returns the ids replaced.
    """
    download_ids = []
    for box in root.select("div.TUD_box_download"):
        download_id = box.get("data-downloadid", "")
        if not download_id:
            box.decompose()
            continue
        filetype = (box.get("data-videotype") or ".mp4").lstrip(".")
        url = tool_url(download_id, src, filetype=filetype)
        page = fetch_page(url)
        if page is None:
            continue
        box.replace_with(inline_widget(page, url, localize))
        download_ids.append(download_id)
    return download_ids
