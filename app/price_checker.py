"""
Core logic: for a given Product, ask every enabled scraper for listings,
store a PriceRecord per listing found, and decide whether a Telegram
alert should go out (price dropped / changed / hit target).
"""
import logging

from sqlmodel import Session, select

from app.models import PriceRecord, Product, Source
from app.scrapers import SCRAPERS
from app.telegram_notify import send_telegram_message

logger = logging.getLogger("price_bot.checker")


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

    for source_name in product.source_list():
        scraper = SCRAPERS.get(source_name)
        if scraper is None:
            logger.warning("Unknown source '%s' for product %s", source_name, product.name)
            continue

        try:
            listings = scraper.search(product.keyword, limit=10)
        except Exception as exc:  # noqa: BLE001 - scrapers call external sites, keep bot alive
            logger.error("Scraper '%s' failed for '%s': %s", source_name, product.keyword, exc)
            continue

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
