"""
Core logic: for a given Product, ask every enabled scraper for listings,
store a PriceRecord per listing found, and decide whether a Telegram
alert should go out (price dropped / changed / hit target).
"""
import logging
import random
import time

from sqlmodel import Session, select

from app.models import PriceRecord, Product, ScrapeLog, Source
from app.scrapers import SCRAPERS
from app.telegram_notify import send_telegram_message

logger = logging.getLogger("price_bot.checker")

# Pause for a random stretch between hitting each marketplace within one
# check, so requests don't all fire back-to-back (which looks bot-like).
# This only adds delay *between sources* for a single product, not before
# the very first one.
MIN_DELAY_BETWEEN_SOURCES_SECONDS = 2.0
MAX_DELAY_BETWEEN_SOURCES_SECONDS = 6.0


def _best_previous_price(session: Session, product_id: int) -> float | None:
    records = session.exec(
        select(PriceRecord)
        .where(PriceRecord.product_id == product_id)
        .order_by(PriceRecord.scraped_at.desc())
        .limit(50)
    ).all()
    if not records:
        return None
    return min(r.price for r in records)


def check_product(session: Session, product: Product) -> list[PriceRecord]:
    """Scrape every source configured for `product`, persist results, and
    send a Telegram alert if warranted. Returns the newly created records."""

    previous_best = _best_previous_price(session, product.id)
    new_records: list[PriceRecord] = []

    is_first_source = True
    for source_name in product.source_list():
        if source_name == Source.FACEBOOK.value:
            # No automated scraping for Facebook - see app/scrapers/facebook.py.
            # Prices for this source are added by hand via add_manual_price().
            continue

        scraper = SCRAPERS.get(source_name)
        if scraper is None:
            logger.warning("Unknown source '%s' for product %s", source_name, product.name)
            continue

        if not is_first_source:
            delay = random.uniform(
                MIN_DELAY_BETWEEN_SOURCES_SECONDS, MAX_DELAY_BETWEEN_SOURCES_SECONDS
            )
            time.sleep(delay)
        is_first_source = False

        try:
            listings = scraper.search(product.keyword, limit=10)
        except Exception as exc:  # noqa: BLE001 - scrapers call external sites, keep bot alive
            logger.error("Scraper '%s' failed for '%s': %s", source_name, product.keyword, exc)
            session.add(
                ScrapeLog(
                    product_id=product.id,
                    source=Source(source_name),
                    success=False,
                    items_found=0,
                    error_message=str(exc)[:500],
                )
            )
            session.commit()
            continue

        session.add(
            ScrapeLog(
                product_id=product.id,
                source=Source(source_name),
                success=True,
                items_found=len(listings),
            )
        )
        session.commit()

        for listing in listings:
            record = PriceRecord(
                product_id=product.id,
                source=Source(source_name),
                title=listing.title,
                price=listing.price,
                currency=listing.currency,
                url=listing.url,
                seller=listing.seller,
            )
            session.add(record)
            new_records.append(record)

    if new_records:
        session.commit()
        for r in new_records:
            session.refresh(r)

    _maybe_notify(product, previous_best, new_records)
    return new_records


def get_source_status(session: Session, product: Product) -> dict[str, dict]:
    """Latest scrape status per source for this product, for display in the UI:
    {"shopee": {"online": True, "items_found": 5, "checked_at": ..., "error": None}, ...}
    Facebook is always reported as "manual" since it has no automated scraper.
    """
    status: dict[str, dict] = {}
    for source_name in product.source_list():
        if source_name == Source.FACEBOOK.value:
            count = session.exec(
                select(PriceRecord).where(
                    PriceRecord.product_id == product.id,
                    PriceRecord.source == Source.FACEBOOK,
                )
            ).all()
            status[source_name] = {
                "manual": True,
                "items_found": len(count),
                "checked_at": max((r.scraped_at for r in count), default=None),
            }
            continue

        latest = session.exec(
            select(ScrapeLog)
            .where(ScrapeLog.product_id == product.id, ScrapeLog.source == Source(source_name))
            .order_by(ScrapeLog.checked_at.desc())
            .limit(1)
        ).first()
        if latest is None:
            status[source_name] = {"online": None, "items_found": 0, "checked_at": None, "error": None}
        else:
            status[source_name] = {
                "online": latest.success,
                "items_found": latest.items_found,
                "checked_at": latest.checked_at,
                "error": latest.error_message,
            }
    return status


def add_manual_price(
    session: Session,
    product: Product,
    title: str,
    price: float,
    url: str | None = None,
    seller: str | None = None,
    source: Source = Source.FACEBOOK,
) -> PriceRecord:
    """Used by the web UI to record a price found by hand (e.g. on Facebook
    Marketplace, where automated scraping isn't available - see
    app/scrapers/facebook.py)."""

    previous_best = _best_previous_price(session, product.id)

    record = PriceRecord(
        product_id=product.id,
        source=source,
        title=title,
        price=price,
        url=url,
        seller=seller,
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    _maybe_notify(product, previous_best, [record])
    return record


def _maybe_notify(product: Product, previous_best: float | None, new_records: list[PriceRecord]) -> None:
    if not new_records:
        return

    current_best_record = min(new_records, key=lambda r: r.price)
    current_best = current_best_record.price

    hit_target = product.target_price is not None and current_best <= product.target_price
    price_changed = previous_best is not None and current_best != previous_best
    is_first_check = previous_best is None

    should_notify = hit_target or (product.notify_on_any_change and price_changed)
    if not should_notify:
        return

    lines = [f"🔔 <b>{product.name}</b>"]
    if hit_target:
        lines.append(f"ถึงราคาเป้าหมายแล้ว! ({product.target_price:,.0f} บาท)")
    elif price_changed and previous_best is not None:
        direction = "ลดลง 📉" if current_best < previous_best else "เพิ่มขึ้น 📈"
        lines.append(f"ราคาเปลี่ยน {direction}: {previous_best:,.0f} → {current_best:,.0f} บาท")

    lines.append(
        f"ราคาต่ำสุดตอนนี้: {current_best:,.0f} บาท จาก {current_best_record.source.value}"
    )
    lines.append(current_best_record.title)
    if current_best_record.url:
        lines.append(current_best_record.url)

    if not (is_first_check and not hit_target):
        # Don't spam a notification for the very first scrape unless it already
        # hits the target price.
        send_telegram_message("\n".join(lines))
