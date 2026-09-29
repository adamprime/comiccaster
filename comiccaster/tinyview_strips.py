"""What a TinyView strip is, shared by the scraper and the feed generator.

A TinyView strip lives at ``https://tinyview.com/<series>/<YYYY>/<MM>/<DD>/<strip>``
and its panels at ``https://cdn.tinyview.com/<series>/<YYYY>/<MM>/<DD>/<strip>/...``.
Several strips can share one date folder (Kowal Comics' five-part "Bella" is all
filed under 2026/09/24), so the date never identifies a strip; its address does.

Until 2026-09-29 the scraper keyed strips on their date and kept every image under
the date folder. Same-date strips collapsed into one record carrying each other's
panels, and later siblings were skipped as already recorded. Both halves of the
pipeline now use these rules, so what the scraper records is exactly what the
generator can render.

The folder comes from the address, never from the feed slug: the
``fowl-language-tinyview`` feed is filed at ``fowl-language`` on TinyView.

Selenium-free on purpose: the network-free feed generator imports this module.
"""

import re
from typing import Optional
from urllib.parse import urlparse

STRIP_HOST = 'tinyview.com'
CDN_HOST = 'cdn.tinyview.com'

_STRIP_PATH = re.compile(r'^[^/]+/\d{4}/\d{2}/\d{2}/[^/]+$')


def canonical_strip_url(url: str) -> str:
    """Return ``url`` as scheme, lower-cased host and path, without a trailing slash.

    Query strings and fragments are dropped, so ``...#comments`` or ``...?ref=home``
    name the same strip as the bare address. This is the key strips are recorded
    and deduplicated under, and the item guid in every TinyView feed.
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}"


def strip_folder(url: str) -> Optional[str]:
    """Return ``<series>/<YYYY>/<MM>/<DD>/<strip>`` for a strip address, else None.

    None means the address is not a single strip: a series page, a date with no
    strip segment, or a page on another host.
    """
    parsed = urlparse(url)
    if parsed.netloc.lower() != STRIP_HOST:
        return None
    path = parsed.path.strip('/')
    return path if _STRIP_PATH.match(path) else None


def image_belongs_to_strip(image_url: str, strip_url: str) -> bool:
    """True when ``image_url`` sits under ``strip_url``'s own folder on the TinyView CDN.

    Images from a same-date sibling strip, from another host, or for an address
    that is not a strip never belong.
    """
    folder = strip_folder(strip_url)
    if folder is None:
        return False
    image = urlparse(image_url)
    return image.netloc.lower() == CDN_HOST and image.path.startswith(f'/{folder}/')
