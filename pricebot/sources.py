"""
The marketplaces the app knows about: their display name, the default
search-page URL (editable on /manage), and which hostnames belong to them
(used to label a price captured with the bookmarklet).

You can capture prices from ANY website with the bookmarklet - pages from
hosts not listed here are labelled with their hostname (e.g. "jib.co.th").
"""
from dataclasses import dataclass
from urllib.parse import quote_plus, urlparse


@dataclass(frozen=True)
class Site:
    key: str
    label: str
    default_search_url: str
    hosts: tuple[str, ...]
    color: str  # badge colour in the UI


# {q}   = search keyword
# {max} = the product's target price. Any URL parameter containing {max} is
#         dropped automatically when the product has no target price.
SITES: list[Site] = [
    Site(
        "facebook",
        "Facebook Marketplace",
        "https://www.facebook.com/marketplace/bangkok/search/?query={q}&maxPrice={max}",
        ("facebook.com", "fb.com"),
        "#4f8cff",
    ),
    Site(
        "shopee", "Shopee",
        "https://shopee.co.th/search?keyword={q}&maxPrice={max}",
        ("shopee.co.th", "shope.ee"), "#ff6a3d",
    ),
    Site(
        "lazada", "Lazada",
        "https://www.lazada.co.th/catalog/?q={q}&price=0-{max}",
        ("lazada.co.th",), "#9b7bff",
    ),
    Site("kaidee", "Kaidee", "https://www.kaidee.com/search?q={q}", ("kaidee.com",), "#2fbf71"),
]
SITES_BY_KEY = {s.key: s for s in SITES}

# Defaults from earlier versions - if a saved link still equals one of these,
# it's upgraded to the new default (with the price filter) on startup.
OLD_DEFAULTS = {
    "facebook": ["https://www.facebook.com/marketplace/bangkok/search/?query={q}"],
    "shopee": ["https://shopee.co.th/search?keyword={q}"],
    "lazada": ["https://www.lazada.co.th/catalog/?q={q}"],
}


def detect_source(url: str | None) -> str:
    """Map a page URL to a site key, or to its bare hostname if unknown."""
    if not url:
        return "other"
    host = (urlparse(url).hostname or "").lower()
    for site in SITES:
        if any(host == h or host.endswith("." + h) for h in site.hosts):
            return site.key
    return host.removeprefix("www.") or "other"


def build_search_url(template: str, keyword: str, max_price: float | None = None) -> str:
    if max_price is None:
        base, sep, query = template.partition("?")
        kept = [part for part in query.split("&") if part and "{max}" not in part]
        template = base + (sep + "&".join(kept) if kept else "")
    else:
        template = template.replace("{max}", str(int(max_price)))
    return template.replace("{q}", quote_plus(keyword))


def source_label(key: str) -> str:
    site = SITES_BY_KEY.get(key)
    return site.label if site else key


def source_color(key: str) -> str:
    site = SITES_BY_KEY.get(key)
    return site.color if site else "#8a8f9c"
