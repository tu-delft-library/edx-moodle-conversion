"""Fake `TUD_download_tool.php` pages, shaped like the real server-rendered ones."""


def tool_page_html(download_id: str, slides: bool = True) -> str:
    """Video/Subtitles/Other buttons; the Other tab only lists slides when the lecture has a
    deck, like the real tool page."""
    base = f"https://delftxdownloads.tudelft.nl/{download_id}"
    other = (
        '<div class="tud-button tud-float other-download">'
        '<div class="tud-button-top other-download-top"><span class="tud-float">Other</span>'
        '<div class="tud-chevron-down tud-float"></div></div>'
        f'<ul class="TUD"><li class="TUD TUD_Slides"><a href="{base}-slides.pdf" '
        'target="_blank">Slides<span class="TUD">PDF</span></a></li></ul></div>'
        if slides
        else ""
    )
    return (
        '<div class="TUD_box_download"><div class="tud-button tud-float video-download">'
        '<div class="tud-button-top video-download-top">'
        '<img class="tud-float tud_video_img" src="img/icon_video_blanc_36.png">'
        '<span class="tud-float">Video</span><div class="tud-chevron-down tud-float"></div>'
        f'</div><ul class="TUD"><li class="TUD TUD_High_Video"><a href="{base}-video.mp4" '
        'target="_blank">High<span class="TUD">1080p</span></a></li></ul></div>'
        '<div class="tud-button tud-float subtitle-download">'
        '<div class="tud-button-top subtitle-download-top">'
        '<img class="tud-float tud_subtitle_img" src="img/icon_subtitles_blanc_36.png">'
        '<span class="tud-float">Subtitles</span>'
        '<div class="tud-chevron-down tud-float"></div></div>'
        f'<ul class="TUD"><li class="TUD TUD_SRT"><a href="{base}-video.srt" '
        'target="_blank">SRT English</a></li></ul></div>'
        f"{other}</div>"
        '<div class="transfer_div">ocw</div>'
        '<script src="js/iframeResizer.contentWindow.min.js"></script>'
    )
