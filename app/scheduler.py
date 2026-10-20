"""
Background scheduler: every SCRAPE_INTERVAL_MINUTES, re-check prices for
every active Product.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import Session, select

from app.config import settings
from app.database import engine
from app.models import Product
from app.price_checker import check_product

logger = logging.getLogger("price_bot.scheduler")

scheduler = BackgroundScheduler()


def check_all_products() -> None:
    logger.info("Running scheduled price check for all active products...")
    with Session(engine) as session:
        products = session.exec(select(Product).where(Product.is_active == True)).all()  # noqa: E712
        for product in products:
            try:
                check_product(session, product)
            except Exception as exc:  # noqa: BLE001
                logger.error("Price check failed for product %s: %s", product.name, exc)
    logger.info("Scheduled price check complete.")


def start_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        check_all_products,
        trigger="interval",
        minutes=settings.SCRAPE_INTERVAL_MINUTES,
        id="price_check_job",
    )
    scheduler.start()
    logger.info(
        "Scheduler started: checking prices every %s minute(s).",
        settings.SCRAPE_INTERVAL_MINUTES,
    )
