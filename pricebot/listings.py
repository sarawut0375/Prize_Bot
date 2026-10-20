"""
Saving offers and deciding when to send a Telegram alert.

An alert goes out when a listing is new or its price changed AND one of:
  - its price is at/below the product's target price      (notify_target)
  - it is the new lowest price seen for that product      (notify_new_lowest)
  - an already-saved listing changed price                (notify_price_change)
Each kind can be switched off on /manage.
"""
from dataclasses import dataclass, field
from datetime import datetime
from html import escape

from sqlmodel import Session, select

from pricebot import settings_store, telegram
from pricebot.models import Listing, Product
from pricebot.prices import fmt_price
from pricebot.sources import source_label


@dataclass
class SaveResult:
    listing: Listing
    is_new: bool
    price_changed: bool
    events: list[str] = field(default_factory=list)  # "target" / "new_lowest" / "price_change"


def lowest_price(session: Session, product_id: int, exclude_id: int | None = None) -> float | None:
    stmt = select(Listing.price).where(Listing.product_id == product_id)
    if exclude_id is not None:
        stmt = stmt.where(Listing.id != exclude_id)
    prices = session.exec(stmt).all()
    return min(prices) if prices else None


def save_listing(
    session: Session,
    product: Product,
    *,
    source: str,
    title: str,
    price: float,
    url: str | None = None,
    seller: str | None = None,
    location: str | None = None,
    condition: str | None = None,
    image_url: str | None = None,
    note: str | None = None,
    via: str = "manual",
) -> SaveResult:
    url = (url or "").strip() or None
    existing = None
    if url:
        existing = session.exec(
            select(Listing).where(Listing.product_id == product.id, Listing.url == url)
        ).first()

    lowest_before = lowest_price(session, product.id, exclude_id=existing.id if existing else None)

    if existing:
        price_changed = existing.price != price
        if price_changed:
            existing.previous_price = existing.price
            existing.price = price
        existing.title = title or existing.title
        existing.source = source or existing.source
        for attr, value in (
            ("seller", seller), ("location", location), ("condition", condition),
            ("image_url", image_url), ("note", note),
        ):
            if value:
                setattr(existing, attr, value)
        existing.captured_via = via
        existing.last_seen = datetime.now()
        listing, is_new = existing, False
    else:
        listing = Listing(
            product_id=product.id, source=source, title=title, price=price, url=url,
            seller=seller or None, location=location or None, condition=condition or None,
            image_url=image_url or None, note=note or None, captured_via=via,
        )
        session.add(listing)
        price_changed, is_new = False, True

    session.commit()
    session.refresh(listing)

    result = SaveResult(listing=listing, is_new=is_new, price_changed=price_changed)
    if is_new or price_changed:
        if product.target_price is not None and price <= product.target_price:
            result.events.append("target")
        if lowest_before is None or price < lowest_before:
            result.events.append("new_lowest")
        if price_changed:
            result.events.append("price_change")
    return result


def _enabled(event: str) -> bool:
    return settings_store.get_bool(f"notify_{event}")


def notify(product: Product, results: list[SaveResult]) -> tuple[bool, str] | None:
    """Send ONE Telegram message for a batch of saves on one product
    (a single bookmarklet capture is a batch of one). Returns None if no
    alert was needed."""
    relevant = [r for r in results if any(_enabled(e) for e in r.events)]
    if not relevant:
        return None

    best = min(relevant, key=lambda r: r.listing.price)
    events = {e for r in relevant for e in r.events if _enabled(e)}
    lst = best.listing

    lines = [f"🔔 <b>{escape(product.name)}</b>"]
    if "target" in events and product.target_price is not None:
        lines.append(f"🎯 ถึงราคาเป้าหมายแล้ว (เป้า {fmt_price(product.target_price)} บาท)")
    if "new_lowest" in events:
        lines.append("📉 ราคาต่ำสุดใหม่ของสินค้านี้")
    if "price_change" in events and lst.previous_price is not None:
        arrow = "ลดลง 📉" if lst.price < lst.previous_price else "เพิ่มขึ้น 📈"
        lines.append(f"ราคาเปลี่ยน {arrow}: {fmt_price(lst.previous_price)} → {fmt_price(lst.price)} บาท")

    lines.append("")
    lines.append(f"<b>{fmt_price(lst.price)} บาท</b> · {escape(source_label(lst.source))}")
    lines.append(escape(lst.title[:200]))
    extra = " · ".join(x for x in (lst.seller, lst.location, lst.condition) if x)
    if extra:
        lines.append(escape(extra))
    if lst.url:
        lines.append(lst.url)
    if len(relevant) > 1:
        lines.append(f"\n(+ อีก {len(relevant) - 1} รายการที่อัปเดตในรอบนี้)")

    return telegram.send("\n".join(lines))
