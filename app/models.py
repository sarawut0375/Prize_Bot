"""
Database models.

Product      - a thing the user wants to track (e.g. "iPhone 15 Pro Max 256GB")
PriceRecord  - one price observation for a Product from one Source, at one point in time
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class Source(str, Enum):
    FACEBOOK = "facebook"
    SHOPEE = "shopee"
    LAZADA = "lazada"
    KAIDEE = "kaidee"
    MANUAL = "manual"  # for sources without an automated scraper (e.g. Facebook Marketplace)


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, description="Display name for this product")
    keyword: str = Field(description="Search keyword used when scraping each marketplace")

    # Comma separated list of Source values this product should be tracked on,
    # e.g. "shopee,lazada,kaidee,facebook"
    sources: str = Field(default="shopee,lazada,kaidee")

    # Optional target price. When the lowest observed price goes at/below this,
    # (or whenever the price changes, depending on NOTIFY_ON_ANY_CHANGE) a Telegram
    # alert is sent.
    target_price: Optional[float] = None

    # If true, notify on every price change, not only when hitting target_price.
    notify_on_any_change: bool = True

    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def source_list(self) -> list[str]:
        return [s.strip() for s in self.sources.split(",") if s.strip()]


class PriceRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)

    source: Source
    title: str = Field(description="Listing title as found on the marketplace")
    price: float
    currency: str = Field(default="THB")
    url: Optional[str] = None
    seller: Optional[str] = None

    scraped_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class ScrapeLog(SQLModel, table=True):
    """One row per (product, source) scrape attempt - whether it succeeded,
    how many listings it found, and the error if it failed. Used to show
    "online / offline" status and result counts on the web page."""

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)

    source: Source
    success: bool = Field(description="False if the scraper raised an error (site blocked/down/changed)")
    items_found: int = Field(default=0, description="How many listings were found this attempt")
    error_message: Optional[str] = None

    checked_at: datetime = Field(default_factory=datetime.utcnow, index=True)
