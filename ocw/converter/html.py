import re

# TODO: This file mostly handles injecting inline styling to make the MBZ import look closer to the OLX export; would be nice if we could make this a bit more open

CLASS_BLACKLIST: list[str] = []  
TUD_DOWNLOAD_BOX_CLASS = "tud-button"


def strip_blacklisted_classes(html: str) -> str:
    if not CLASS_BLACKLIST:
        return html
    pattern = re.compile(
        r'<div\b[^>]*class="[^"]*\b(?:'
        + "|".join(re.escape(c) for c in CLASS_BLACKLIST)
        + r')\b[^"]*"[^>]*>.*?</div>',
        re.DOTALL,
    )
    return pattern.sub("", html)


def strip_templated_iframes(html: str) -> str:
    def _drop(m: re.Match) -> str:
        open_tag = m.group(1)
        return "" if re.search(r'src="[^"]*%%[A-Z_]+%%[^"]*"', open_tag) else m.group(0)

    return re.sub(r"(<iframe\b[^>]*>).*?</iframe>", _drop, html, flags=re.DOTALL)


def constrain_img_size(html: str) -> str:
    # OLX images (base64 or file-referenced) often carry hardcoded pixel width/height
    # from the original author. We overide this with inline styling  
    def _inject(m: re.Match) -> str:
        tag = m.group(0)
        if "style=" in tag:
            return re.sub(
                r'style="', 'style="max-width:100%;height:auto;', tag, count=1
            )
        return tag.replace("<img ", '<img style="max-width:100%;height:auto;" ', 1)

    return re.sub(r"<img\b[^>]*>", _inject, html)


def constrain_table_size(html: str) -> str:
    # Word-pasted tables (telltale <o:p> tags) carry hardcoded pixel widths on
    # <table> and each <td> that overflow Moodle's narrower content column.
    # table-layout defaults to auto, so limitting just the outer <table> lets
    # columns shrink proportionally without touching per-cell widths.
    def _inject(m: re.Match) -> str:
        tag = m.group(0)
        if "style=" in tag:
            return re.sub(r'style="', 'style="max-width:100%;', tag, count=1)
        return tag.replace("<table ", '<table style="max-width:100%" ', 1)

    return re.sub(r"<table\b[^>]*>", _inject, html)


def style_figcaption(html: str) -> str:
    # OLX authors simulate an image caption with a bare heading tag inside
    # <figcaption> (e.g. <figcaption><h6>...</h6></figcaption>); OpenEdX's theme
    # silently shrinks headings nested in figcaption, but Moodle renders them at
    # full heading size. Inside a shrink-to-fit floated <figure>, that larger
    # caption text can out-grow the image and stretch the whole box.
    def _inject_heading_style(hm: re.Match) -> str:
        tag = hm.group(0)
        if "style=" in tag:
            return re.sub(
                r'style="', 'style="font-size:0.75em;font-weight:normal;', tag, count=1
            )
        return re.sub(
            r"^<(h[1-6])\b", r'<\1 style="font-size:0.75em;font-weight:normal;"', tag
        )

    def _style_captions(m: re.Match) -> str:
        return re.sub(r"<h[1-6]\b[^>]*>", _inject_heading_style, m.group(0))

    return re.sub(
        r"<figcaption\b[^>]*>.*?</figcaption>", _style_captions, html, flags=re.DOTALL
    )
