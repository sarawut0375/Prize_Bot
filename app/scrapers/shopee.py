"""
Shopee Thailand scraper, using Shopee's own public-facing search JSON
endpoint (the same one shopee.co.th calls from the browser).

IMPORTANT / LIMITATIONS:
Shopee actively rate-limits and anti-bot-protects this endpoint. It can
start returning HTTP 403 / empty results for datacenter IPs, or require
a valid `csrftoken`/session cookie. If that happens:
  1. Try lowering SCRAPE_INTERVAL in .env (scrape less often).
  2. Consider running the bot from a residential/home IP (e.g. on your
     own PC or a Raspberry Pi) rather than a cloud server.
  3. As a fallback, add prices for this product manually from the web UI.
"""
from app.config import settings
from app.scrapers.base import BaseScraper, ScrapedListing, get_session

SEARCH_API = "https://shopee.co.th/api/v4/search/search_items"


class ShopeeScraper(BaseScraper):
    source_name = "shopee"

    def search(self, keyword: str, limit: int = 10) -> list[ScrapedListing]:
        session = get_session()
        session.headers.update(
            {
                "Accept": "application/json",
                "X-API-SOURCE": "pc",
                "Referer": f"https://shopee.co.th/search?keyword={keyword}",
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
            return []
        try:
            data = resp.json()
        except ValueError:
            return []

        items = data.get("items") or []
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
