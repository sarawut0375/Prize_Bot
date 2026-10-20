"""
Kaidee.com (classifieds) scraper.

Kaidee pages are server-rendered with an embedded Next.js `__NEXT_DATA__`
JSON blob, which is far more stable to parse than CSS selectors. We fall
back to a plain HTML/CSS scrape if that blob isn't found.

NOTE: Kaidee may change their markup/API at any time without notice.
If this stops returning results, open the search page in a browser,
view source, and adjust `_parse_next_data` / `_parse_html` accordingly.
"""
import json
import logging
import re

from bs4 import BeautifulSoup

from app.config import settings
from app.scrapers.base import BaseScraper, ScrapedListing, get_session

SEARCH_URL = "https://www.kaidee.com/search"

logger = logging.getLogger("price_bot.scrapers.kaidee")


class KaideeScraper(BaseScraper):
    source_name = "kaidee"

    def search(self, keyword: str, limit: int = 10) -> list[ScrapedListing]:
        session = get_session()
        resp = session.get(
            SEARCH_URL,
            params={"q": keyword},
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        listings = self._parse_next_data(soup, limit)
        if listings:
            return listings
        listings = self._parse_html(soup, limit)
        if not listings:
            has_next_data = soup.find("script", id="__NEXT_DATA__") is not None
            snippet = " ".join(resp.text.split())[:400]
            logger.info(
                "Kaidee search for '%s' found 0 items (HTTP %s, page length %s chars, "
                "__NEXT_DATA__ present: %s). Kaidee likely changed their page structure, "
                "blocked the request, or this page needs JavaScript to load results. "
                "Body snippet: %s",
                keyword, resp.status_code, len(resp.text), has_next_data, snippet,
            )
        return listings

    def _parse_next_data(self, soup: BeautifulSoup, limit: int) -> list[ScrapedListing]:
        tag = soup.find("script", id="__NEXT_DATA__")
        if not tag or not tag.string:
            return []
        try:
            data = json.loads(tag.string)
        except json.JSONDecodeError:
            return []

        items = []
        _walk_for_items(data, items)

        results: list[ScrapedListing] = []
        for item in items[:limit]:
            title = item.get("title") or item.get("name")
            price = _to_float(item.get("price"))
            if not title or price is None:
                continue
            item_id = item.get("id") or item.get("item_id")
            url = f"https://www.kaidee.com/product-{item_id}" if item_id else None
            results.append(
                ScrapedListing(
                    title=str(title),
                    price=price,
                    url=url,
                    seller=item.get("seller_name") or item.get("username"),
                )
            )
        return results

    def _parse_html(self, soup: BeautifulSoup, limit: int) -> list[ScrapedListing]:
        results: list[ScrapedListing] = []
        # Best-effort generic fallback: look for anchors that wrap a price-looking string.
        for card in soup.select("a[href*='/product-']")[:limit]:
            text = card.get_text(" ", strip=True)
            price = _extract_price_from_text(text)
            if price is None:
                continue
            href = card.get("href")
            url = href if href and href.startswith("http") else f"https://www.kaidee.com{href}"
            results.append(ScrapedListing(title=text[:120], price=price, url=url))
        return results


def _walk_for_items(node, out: list):
    """Recursively collect dicts that look like a product listing."""
    if isinstance(node, dict):
        if ("title" in node or "name" in node) and "price" in node:
            out.append(node)
        for v in node.values():
            _walk_for_items(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_for_items(v, out)


def _to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[\d,]+(\.\d+)?", str(value))
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


def _extract_price_from_text(text: str) -> float | None:
    match = re.search(r"([\d,]+)\s*(?:บาท|THB|฿)", text)
    if not match:
        return None
    return float(match.group(1).replace(",", ""))
