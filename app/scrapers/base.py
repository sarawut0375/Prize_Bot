"""
Common interface every marketplace scraper implements.

A scraper takes a search keyword and returns a list of ScrapedListing.
Scrapers should never raise on "no results" - return an empty list instead.
They may raise on genuine network/parsing errors so the scheduler can log it.
"""
from dataclasses import dataclass
from typing import Optional

import requests

from app.config import settings


@dataclass
class ScrapedListing:
    title: str
    price: float
    url: Optional[str] = None
    seller: Optional[str] = None
    currency: str = "THB"


DEFAULT_HEADERS = {
    "User-Agent": settings.USER_AGENT,
    "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
}


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


class BaseScraper:
    """Subclass and implement `search`."""

    source_name: str = "base"

    def search(self, keyword: str, limit: int = 10) -> list[ScrapedListing]:
        raise NotImplementedError
