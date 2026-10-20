"""
Product  - something you want to find (e.g. "RTX 4060"), with a search keyword
           and an optional target price.
Listing  - one offer you found for a Product: a specific item on a specific
           site, with its price. Re-saving the same URL updates the price
           (and remembers the previous one) instead of creating a duplicate.
Setting  - key/value store for everything edited on the /manage page.
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now()


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    keyword: str
    target_price: Optional[float] = None
    note: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=_now)


class Listing(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)

    source: str = Field(index=True)  # facebook / shopee / lazada / kaidee / other hostname
    title: str
    price: float
    previous_price: Optional[float] = None
    currency: str = "THB"
    url: Optional[str] = Field(default=None, index=True)

    seller: Optional[str] = None
    location: Optional[str] = None
    condition: Optional[str] = None  # มือหนึ่ง / มือสอง
    image_url: Optional[str] = None
    note: Optional[str] = None

    captured_via: str = "manual"  # bookmarklet / manual / shopee_api
    first_seen: datetime = Field(default_factory=_now)
    last_seen: datetime = Field(default_factory=_now)


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str = ""
