"""
Facebook Marketplace does NOT have a public search API, requires a logged-in
session to view listings, and actively blocks automated scraping (this is
against Facebook's Terms of Service to circumvent).

Because of that, this scraper intentionally does NOT attempt to scrape
Facebook automatically. Instead:
  - Facebook is treated as a "manual" source in the UI: you (or a Telegram
    chat command, if you extend the bot) type in the price you found on
    Facebook Marketplace, and the bot stores it like any other price point
    so it still shows up in the comparison table and still triggers
    price-change alerts.

If you really want automated Facebook coverage later, the realistic options
are (not implemented here, each has real cost/legal tradeoffs):
  1. Use the official Facebook Marketplace API if/when Meta makes one
     available for your use case.
  2. Use a licensed third-party data provider that already has Marketplace
     access agreements.
  3. Browser automation with a real logged-in account - fragile, against
     Facebook's ToS, and can get the account banned. Not recommended.
"""
from app.scrapers.base import BaseScraper, ScrapedListing


class FacebookScraper(BaseScraper):
    source_name = "facebook"

    def search(self, keyword: str, limit: int = 10) -> list[ScrapedListing]:
        # No automated scraping - see module docstring. Prices for this
        # source are entered manually through the web UI instead.
        return []
