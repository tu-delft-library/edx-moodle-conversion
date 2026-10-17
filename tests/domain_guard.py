"""Shared regression guard: no foreign domain should survive conversion except inside a plain
content link (`<a href>`, a deliberate outbound reference the author wrote, never fetched) or on
one of the video hosts that are accepted to stay external (youtube.com, Collegerama). The
DelftX download widget's video/subtitle files stay on delftxdownloads.tudelft.nl, but only as
`href`s, so that host isn't allowed for assets.

Every other `src`/`srcset` reference (`<img>`, `<iframe>`, `<script>`, CSS `url(...)`) is expected
to have been fetched locally and rewritten to `/static/...` or `@@PLUGINFILE@@/...` by the time
content reaches a built MBZ. A foreign host surviving there means some asset type slipped through
the fetch pipeline unnoticed -- exactly the class of regression the WP download-widget scrollbar
bug and the still-open slides bug both were.
"""

import re

# Embedded video players allowed to stay external.
ALLOWED_ASSET_HOSTS = frozenset({
    "youtube.com",
    "www.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "collegerama.tudelft.nl",
})

_SRC_ATTR_RE = re.compile(r'\b(?:src|srcset)\s*=\s*"([^"]*)"', re.IGNORECASE)
_URL_HOST_RE = re.compile(r'https?://([^/"\'>\s]+)')
_CSS_URL_RE = re.compile(r'url\(\s*[\'"]?(https?://[^)\'">\s]+)', re.IGNORECASE)


def asset_hosts(html: str) -> set[str]:
    """Return every external host referenced by a `src`/`srcset` attribute or CSS `url(...)` in
    `html`. Deliberately ignores `href` -- a prose link to another site is a content link, not an
    asset reference, and is allowed to point anywhere.
    """
    hosts: set[str] = set()
    for attr_value in _SRC_ATTR_RE.findall(html):
        for candidate in attr_value.split(","):  # srcset: comma-separated "url descriptor" pairs
            match = _URL_HOST_RE.search(candidate)
            if match:
                hosts.add(match.group(1).lower())
    for match in _CSS_URL_RE.findall(html):
        host_match = _URL_HOST_RE.search(match)
        if host_match:
            hosts.add(host_match.group(1).lower())
    return hosts


def foreign_asset_hosts(html: str) -> set[str]:
    """`asset_hosts(html)` minus the accepted video/subtitle hosts."""
    return {h for h in asset_hosts(html) if h not in ALLOWED_ASSET_HOSTS}
