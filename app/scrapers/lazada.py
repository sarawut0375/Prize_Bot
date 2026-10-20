"""
Lazada Thailand scraper, using the AJAX version of the catalog/search page
(the same request the browser makes when you type into Lazada's search box
and the page is rendered server-side with `&ajax=true`).

⚠️ DISABLED BY DEFAULT - confirmed actively blocked.
A real run against this scraper was redirected to Lazada's own anti-bot
"punish" page:
    https://www.lazada.co.th/catalog/_____tmd_____/punish?x5secdata=...
("tmd" = Alibaba group's anti-crawler system, used across Lazada/Taobao).
That means Lazada's own system already detected and flagged this traffic
as a bot. Because of that, `app/price_checker.py` does NOT call this
scraper automatically (see MANUAL_ONLY_SOURCES there) - prices for Lazada
are entered by hand through the web UI instead, same as Facebook.

This file is kept for reference / in case Lazada's detection logic changes
later, but re-enabling automated Lazada scraping means deliberately working
around a security control that has already caught this bot once, which
risks a harder/longer block on your IP and arguably crosses from "scraping
a public page" into "circumventing anti-bot protection". If you still want
to re-enable it, remove `Source.LAZADA.value` from `MANUAL_ONLY_SOURCES` in
`app/price_checker.py` - but do so at your own risk.
"""
import json
import logging
import re

from bs4 import BeautifulSoup

from app.config import settings
from app.scrapers.base import BaseScraper, ScrapedListing, get_session

SEARCH_URL = "https://www.lazada.co.th/catalog/"

logger = logging.getLogger("price_bot.scrapers.lazada")


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
            logger.warning(
                "Lazada search for '%s' got HTTP %s: %s", keyword, resp.status_code, resp.text[:300]
            )
            return []

        try:
            data = resp.json()
        except ValueError:
            # Lazada sometimes returns the full HTML page instead of JSON;
            # try to dig the embedded `window.pageData` JSON out of it.
            data = self._extract_page_data(resp.text)
            if data is None:
                snippet = " ".join(resp.text.split())[:400]
                logger.warning(
                    "Lazada search for '%s': response wasn't JSON and no "
                    "window.pageData found in the HTML (page length %s chars). "
                    "Lazada likely changed their page/response format, or this "
                    "is a bot-check/redirect page. Body snippet: %s",
                    keyword, len(resp.text), snippet,
                )
                return []

        items = (
            data.get("mainInfo", {}).get("listItems")
            or data.get("mods", {}).get("listItems")
            or []
        )
        if not items:
            logger.info(
                "Lazada search for '%s' parsed OK but found 0 items. "
                "Top-level JSON keys: %s", keyword, list(data.keys()),
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
