import re


def constrain_img_size(html: str) -> str:
    # OLX images (base64 or file-referenced) often carry hardcoded pixel width/height
    # from the original author; Moodle's page theme doesn't reliably scale these down
    # the way the OpenEdX LMS theme does, so oversized images overflow/clip. Inline
    # style beats theme CSS regardless of destination theme, and height:auto derives
    # the displayed height from the image's real aspect ratio, not the stale attribute.
    def _inject(m: re.Match) -> str:
        tag = m.group(0)
        if "style=" in tag:
            # prepend to existing style block
            return re.sub(r'style="', 'style="max-width:100%;height:auto;', tag, count=1)
        # no style attr at all — add one
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
