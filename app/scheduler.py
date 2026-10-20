"""
Background scheduler: re-check prices for every active Product on a random
interval between SCRAPE_INTERVAL_MIN_MINUTES and SCRAPE_INTERVAL_MAX_MINUTES
(instead of a fixed interval), so traffic looks less bot-like to sites with
anti-scraping protection.
"""
import logging
import random
import time
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from app.config import settings
from app.database import engine
from app.models import Product
from app.price_checker import check_product

logger = logging.getLogger("price_bot.scheduler")

scheduler = BackgroundScheduler()
JOB_ID = "price_check_job"

# Extra pause between products in one scheduled run - check_product() already
# pauses between sources within a product; this spaces out whole products too
# so a run with many tracked products doesn't fire everything in a tight burst.
MIN_DELAY_BETWEEN_PRODUCTS_SECONDS = 3.0
MAX_DELAY_BETWEEN_PRODUCTS_SECONDS = 8.0


def check_all_products() -> None:
    logger.info("Running scheduled price check for all active products...")
    with Session(engine) as session:
        products = session.exec(select(Product).where(Product.is_active == True)).all()  # noqa: E712
        for i, product in enumerate(products):
            if i > 0:
                time.sleep(
                    random.uniform(
                        MIN_DELAY_BETWEEN_PRODUCTS_SECONDS, MAX_DELAY_BETWEEN_PRODUCTS_SECONDS
                    )
                )
            try:
                check_product(session, product)
            except Exception as exc:  # noqa: BLE001
                logger.error("Price check failed for product %s: %s", product.name, exc)
    logger.info("Scheduled price check complete.")


def _run_and_reschedule() -> None:
    check_all_products()
    _schedule_next_run()


def _schedule_next_run() -> None:
    low = min(settings.SCRAPE_INTERVAL_MIN_MINUTES, settings.SCRAPE_INTERVAL_MAX_MINUTES)
    high = max(settings.SCRAPE_INTERVAL_MIN_MINUTES, settings.SCRAPE_INTERVAL_MAX_MINUTES)
    delay_minutes = random.randint(low, high)
    run_at = datetime.now() + timedelta(minutes=delay_minutes)

    scheduler.add_job(
        _run_and_reschedule,
        trigger="date",
        run_date=run_at,
        id=JOB_ID,
        replace_existing=True,
    )
    logger.info(
        "Next price check scheduled in %s minute(s), at %s.",
        delay_minutes, run_at.strftime("%Y-%m-%d %H:%M:%S"),
    )


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.start()
    _schedule_next_run()
