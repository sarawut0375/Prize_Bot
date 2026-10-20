"""
Lazada Thailand scraper, using the AJAX version of the catalog/search page
(the same request the browser makes when you type into Lazada's search box
and the page is rendered server-side with `&ajax=true`).

LIMITATIONS: Lazada may also rate-limit or change this response shape.
See shopee.py's docstring for the same caveats - this is best-effort.
"""
import json
import re

from bs4 import BeautifulSoup

from app.config import settings
from app.scrapers.base import BaseScraper, ScrapedListing, get_session

SEARCH_URL = "https://www.lazada.co.th/catalog/"


class LazadaScraper(BaseScraper):
    source_name = "lazada"

    def search(self, keyword: str, limit: int = 10) -> list[ScrapedListing]:
        session = get_session()
        resp = session.get(
            SEARCH_URL,
            params={"q": keyword, "ajax": "true"},
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
        )
        if resp.status_code != 200:
            return []

        try:
            data = resp.json()
        except ValueError:
            # Lazada sometimes returns the full HTML page instead of JSON;
            # try to dig the embedded `window.pageData` JSON out of it.
            data = self._extract_page_data(resp.text)
            if data is None:
                return []

        items = (
            data.get("mainInfo", {}).get("listItems")
            or data.get("mods", {}).get("listItems")
            or []
        )

        results: list[ScrapedListing] = []
        for item in items[:limit]:
            name = item.get("name")
            price = item.get("priceShow") or item.get("price")
            if name is None or price is None:
                continue
            price_val = _to_float(price)
            if price_val is None:
                continue
            url = item.get("itemUrl") or item.get("productUrl")
            if url and url.startswith("//"):
                url = "https:" + url
            results.append(
                ScrapedListing(
                    title=name,
                    price=price_val,
                    url=url,
                    seller=item.get("sellerName") or item.get("brandName"),
                )
            )
        return results

    @staticmethod
    def _extract_page_data(html: str):
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script"):
            text = script.string or ""
            if "pageData" not in text:
                continue
            match = re.search(r"window\.pageData\s*=\s*(\{.*\});", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        return None


def _to_float(value) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[\d,]+(\.\d+)?", str(value))
    if not match:
        return None
    return float(match.group(0).replace(",", ""))
