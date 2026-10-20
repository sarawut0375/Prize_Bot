"""
Shopee Thailand scraper, using Shopee's own public-facing search JSON
endpoint (the same one shopee.co.th calls from the browser).

⚠️ DISABLED BY DEFAULT - confirmed actively blocked.
A real run against this scraper got HTTP 403 with Shopee's own anti-bot
error body:
    {"is_customized":false,"is_login":false,"action_type":2,
     "error":90309999,"tracking_id":"...","redirect_to_error_page":true}
That means Shopee's own system already detected and flagged this traffic
as a bot - same situation as Lazada (see app/scrapers/lazada.py). Because
of that, `app/price_checker.py` does NOT call this scraper automatically
(see MANUAL_ONLY_SOURCES there) - prices for Shopee are entered by hand
through the web UI instead.

This file is kept for reference / in case Shopee's detection logic changes
later, but re-enabling automated Shopee scraping means deliberately working
around a security control that has already caught this bot once, which
risks a harder/longer block on your IP. If you still want to re-enable it,
remove `Source.SHOPEE.value` from `MANUAL_ONLY_SOURCES` in
`app/price_checker.py` - but do so at your own risk. If you do, and it
starts failing again:
  1. Try widening SCRAPE_INTERVAL_MIN/MAX_MINUTES in .env (scrape less often).
  2. Consider running the bot from a residential/home IP rather than a
     cloud server.
  3. Fall back to adding prices for this product manually from the web UI.
"""
import logging
from urllib.parse import quote

from app.config import settings
from app.scrapers.base import BaseScraper, ScrapedListing, get_session

SEARCH_API = "https://shopee.co.th/api/v4/search/search_items"

logger = logging.getLogger("price_bot.scrapers.shopee")


class ShopeeScraper(BaseScraper):
    source_name = "shopee"

    def search(self, keyword: str, limit: int = 10) -> list[ScrapedListing]:
        session = get_session()
        session.headers.update(
            {
                "Accept": "application/json",
                "X-API-SOURCE": "pc",
                # HTTP headers must be Latin-1; a raw Thai keyword here raises
                # UnicodeEncodeError inside requests. URL-encode it instead -
                # this is exactly what a real browser sends.
                "Referer": f"https://shopee.co.th/search?keyword={quote(keyword)}",
            }
        )
        params = {
            "by": "relevancy",
            "keyword": keyword,
            "limit": limit,
            "newest": 0,
            "order": "desc",
            "page_type": "search",
            "scenario": "PAGE_GLOBAL_SEARCH",
            "version": 2,
        }
        resp = session.get(SEARCH_API, params=params, timeout=settings.REQUEST_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            logger.warning(
                "Shopee search for '%s' got HTTP %s: %s", keyword, resp.status_code, resp.text[:300]
            )
            return []
        try:
            data = resp.json()
        except ValueError:
            logger.warning("Shopee search for '%s' returned non-JSON body: %s", keyword, resp.text[:300])
            return []

        items = data.get("items") or []
        if not items:
            # error_msg / reason here almost always explains *why* zero results came
            # back (e.g. anti-bot challenge) even though the HTTP call "succeeded".
            logger.info(
                "Shopee search for '%s' returned 0 items. Raw response keys: %s, error: %s",
                keyword, list(data.keys()), data.get("error_msg") or data.get("error"),
            )
        results: list[ScrapedListing] = []
        for entry in items[:limit]:
            item = entry.get("item_basic") or entry.get("item") or {}
            if not item:
                continue
            name = item.get("name")
            # Shopee prices are in "micro units" (price / 100000 = baht)
            raw_price = item.get("price") or item.get("price_min")
            if name is None or raw_price is None:
                continue
            price = raw_price / 100000
            shop_id = item.get("shopid")
            item_id = item.get("itemid")
            url = (
                f"https://shopee.co.th/product/{shop_id}/{item_id}"
                if shop_id and item_id
                else None
            )
            results.append(
                ScrapedListing(
                    title=name,
                    price=price,
                    url=url,
                    seller=item.get("shop_name"),
                )
            )
        return results
