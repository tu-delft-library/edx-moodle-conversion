import re


def fix_unsized_base64_imgs(html: str) -> str:
    # base64 imgs with no width/height render at native pixel size in Moodle;
    # constrain them to the page container width
    def _inject(m: re.Match) -> str:
        tag = m.group(0)
        if "width=" in tag or "height=" in tag:
            # already explicitly sized — leave alone
            return tag
        if "style=" in tag:
            # prepend to existing style block
            return re.sub(r'style="', 'style="max-width:100%;', tag, count=1)
        # no style attr at all — add one
        return tag.replace("<img ", '<img style="max-width:100%" ', 1)

    return re.sub(r'<img\b[^>]*\bsrc="data:image/[^>]*>', _inject, html)
