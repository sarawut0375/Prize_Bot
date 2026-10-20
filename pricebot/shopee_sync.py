"""
Pull prices for products through the official Shopee Affiliate API, either
on demand (button on the results page) or on a timer (set on /manage).
This is the ONLY automatic searching the app does - every other site is
searched by you in your own browser and captured with the bookmarklet.
"""
import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from pricebot import settings_store, shopee_api
from pricebot.database import engine
from pricebot.listings import notify, save_listing
from pricebot.models import Product

logger = logging.getLogger("pricebot.shopee_sync")
scheduler = BackgroundScheduler()
JOB_ID = "shopee_api_sync"


def is_configured() -> bool:
    return bool(settings_store.get("shopee_app_id") and settings_store.get("shopee_secret"))


def sync_product(session: Session, product: Product) -> tuple[int, str | None]:
    """Returns (number of listings saved, error message or None)."""
    try:
        items = shopee_api.search(
            product.keyword,
            settings_store.get("shopee_app_id"),
            settings_store.get("shopee_secret"),
            limit=settings_store.get_int("shopee_api_limit", 10),
        )
    except shopee_api.ShopeeApiError as exc:
        logger.error("Shopee API failed for %r: %s", product.keyword, exc)
        return 0, str(exc)

    results = [
        save_listing(
            session, product, source="shopee", title=item.title, price=item.price,
            url=item.url, seller=item.seller, image_url=item.image_url, via="shopee_api",
        )
        for item in items
    ]
    notify(product, results)
    return len(results), None


def sync_all() -> None:
    if not (settings_store.get_bool("shopee_api_enabled") and is_configured()):
        return
    logger.info("Shopee API sync started")
    with Session(engine) as session:
        products = session.exec(select(Product).where(Product.is_active == True)).all()  # noqa: E712
        for i, product in enumerate(products):
            if i:
                time.sleep(2)  # be gentle with the API
            count, err = sync_product(session, product)
            logger.info("Shopee API: %s -> %s item(s)%s", product.name, count, f" (error: {err})" if err else "")


def reschedule() -> None:
    """(Re)apply the interval from settings. Call after settings change."""
    if scheduler.get_job(JOB_ID):
        scheduler.remove_job(JOB_ID)
    minutes = settings_store.get_int("shopee_api_interval_minutes", 0)
    if settings_store.get_bool("shopee_api_enabled") and minutes > 0:
        scheduler.add_job(sync_all, "interval", minutes=minutes, id=JOB_ID)
        logger.info("Shopee API auto-sync every %s minute(s)", minutes)


def start() -> None:
    if not scheduler.running:
        scheduler.start()
    reschedule()
