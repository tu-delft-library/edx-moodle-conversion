"""Apply small HTML transformations before course content is written to Moodle.

The converter preserves authored markup where possible. These functions remove source-only
elements and add minimal inline styling where OLX or Word-authored HTML would otherwise render
poorly in Moodle's content area.
"""

import re

CLASS_BLACKLIST: list[str] = []  
TUD_DOWNLOAD_BOX_CLASS = "tud-button"


def strip_blacklisted_classes(html: str) -> str:
    """Remove complete `div` blocks whose class list contains a configured blacklist entry.

    Returns the original HTML unchanged when `CLASS_BLACKLIST` is empty.
    """
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
    """Remove iframes whose source URL contains an unresolved template placeholder."""
    def _drop(m: re.Match) -> str:
        open_tag = m.group(1)
        return "" if re.search(r'src="[^"]*%%[A-Z_]+%%[^"]*"', open_tag) else m.group(0)

    return re.sub(r"(<iframe\b[^>]*>).*?</iframe>", _drop, html, flags=re.DOTALL)


def constrain_img_size(html: str) -> str:
    """Constrain images to Moodle's content width while preserving aspect ratio."""
    def _inject(m: re.Match) -> str:
        tag = m.group(0)
        if "style=" in tag:
            return re.sub(
                r'style="', 'style="max-width:100%;height:auto;', tag, count=1
            )
        return tag.replace("<img ", '<img style="max-width:100%;height:auto;" ', 1)

    return re.sub(r"<img\b[^>]*>", _inject, html)


def constrain_table_size(html: str) -> str:
    """Constrain tables to Moodle's content width without rewriting cell dimensions."""
    def _inject(m: re.Match) -> str:
        tag = m.group(0)
        if "style=" in tag:
            return re.sub(r'style="', 'style="max-width:100%;', tag, count=1)
        return tag.replace("<table ", '<table style="max-width:100%" ', 1)

    return re.sub(r"<table\b[^>]*>", _inject, html)


def mark_hyperlinks_nomediaplugin(html: str) -> str:
    """Mark links so Moodle does not replace them with automatic media embeds.

    Adds the `nomediaplugin` class without removing existing link classes.
    """
    def _inject(m: re.Match) -> str:
        tag = m.group(0)
        if "class=" in tag:
            return re.sub(r'class="', 'class="nomediaplugin ', tag, count=1)
        return tag.replace("<a ", '<a class="nomediaplugin" ', 1)

    return re.sub(r"<a\b[^>]*>", _inject, html)


def style_figcaption(html: str) -> str:
    """Style headings inside figure captions as caption text."""
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
