from app.models import Source
from app.scrapers.base import BaseScraper, ScrapedListing
from app.scrapers.facebook import FacebookScraper
from app.scrapers.kaidee import KaideeScraper
from app.scrapers.lazada import LazadaScraper
from app.scrapers.shopee import ShopeeScraper

SCRAPERS: dict[str, BaseScraper] = {
    Source.SHOPEE.value: ShopeeScraper(),
    Source.LAZADA.value: LazadaScraper(),
    Source.KAIDEE.value: KaideeScraper(),
    Source.FACEBOOK.value: FacebookScraper(),
}

__all__ = ["SCRAPERS", "BaseScraper", "ScrapedListing"]
