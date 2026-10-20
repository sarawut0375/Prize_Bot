"""
FastAPI app: web UI for adding products to track and viewing the price
comparison table, plus a couple of JSON endpoints for manual actions.
"""
import logging
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.config import settings
from app.database import engine, init_db
from app.models import PriceRecord, Product, ScrapeLog, Source
from app.price_checker import add_manual_price, check_product, get_source_status
from app.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield


app = FastAPI(title="Price Bot", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

ALL_SOURCES = [s.value for s in Source]


def _session() -> Session:
    return Session(engine)


def _latest_prices_by_source(session: Session, product_id: int) -> dict:
    """Return {source: cheapest PriceRecord from that source's most recent
    scrape} for a product, so the home page shows one row per source."""
    records = session.exec(
        select(PriceRecord)
        .where(PriceRecord.product_id == product_id)
        .order_by(PriceRecord.scraped_at.desc())
    ).all()

    most_recent_scrape_at: dict[str, object] = {}
    best: dict[str, PriceRecord] = {}
    for r in records:
        key = r.source.value
        most_recent_scrape_at.setdefault(key, r.scraped_at)
        # Only consider records from the same scrape run as the most recent one
        # for this source (within a 5 minute window of it).
        if (most_recent_scrape_at[key] - r.scraped_at).total_seconds() > 300:
            continue
        if key not in best or r.price < best[key].price:
            best[key] = r
    return best


@app.get("/")
def index(request: Request):
    with _session() as session:
        products = session.exec(select(Product).order_by(Product.created_at.desc())).all()
        comparisons = {}
        source_status = {}
        for p in products:
            comparisons[p.id] = _latest_prices_by_source(session, p.id)
            source_status[p.id] = get_source_status(session, p)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "products": products,
            "comparisons": comparisons,
            "source_status": source_status,
            "scrape_interval_min": settings.SCRAPE_INTERVAL_MIN_MINUTES,
            "scrape_interval_max": settings.SCRAPE_INTERVAL_MAX_MINUTES,
        },
    )


@app.get("/products/new")
def new_product_form(request: Request):
    return templates.TemplateResponse(
        "add_product.html", {"request": request, "all_sources": ALL_SOURCES}
    )


@app.post("/products")
def create_product(
    name: str = Form(...),
    keyword: str = Form(...),
    sources: list[str] = Form(...),
    target_price: float | None = Form(None),
    notify_on_any_change: bool = Form(False),
):
    with _session() as session:
        product = Product(
            name=name,
            keyword=keyword,
            sources=",".join(sources),
            target_price=target_price,
            notify_on_any_change=notify_on_any_change,
        )
        session.add(product)
        session.commit()
        session.refresh(product)
        check_product(session, product)  # first scrape happens immediately
    return RedirectResponse(url="/", status_code=303)


@app.get("/products/{product_id}")
def product_detail(request: Request, product_id: int):
    with _session() as session:
        product = session.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        records = session.exec(
            select(PriceRecord)
            .where(PriceRecord.product_id == product_id)
            .order_by(PriceRecord.scraped_at.desc())
            .limit(100)
        ).all()
        by_source = defaultdict(list)
        for r in records:
            by_source[r.source.value].append(r)
        status = get_source_status(session, product)
    return templates.TemplateResponse(
        "product_detail.html",
        {
            "request": request,
            "product": product,
            "by_source": dict(by_source),
            "source_status": status,
            "scrape_interval_min": settings.SCRAPE_INTERVAL_MIN_MINUTES,
            "scrape_interval_max": settings.SCRAPE_INTERVAL_MAX_MINUTES,
        },
    )


@app.post("/products/{product_id}/refresh")
def refresh_product(product_id: int):
    with _session() as session:
        product = session.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        check_product(session, product)
    return RedirectResponse(url=f"/products/{product_id}", status_code=303)


@app.post("/products/{product_id}/manual-price")
def manual_price(
    product_id: int,
    title: str = Form(...),
    price: float = Form(...),
    url: str | None = Form(None),
    seller: str | None = Form(None),
    source: str = Form(Source.FACEBOOK.value),
):
    with _session() as session:
        product = session.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        add_manual_price(
            session, product, title=title, price=price, url=url, seller=seller,
            source=Source(source),
        )
    return RedirectResponse(url=f"/products/{product_id}", status_code=303)


@app.post("/products/{product_id}/delete")
def delete_product(product_id: int):
    with _session() as session:
        product = session.get(Product, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        records = session.exec(
            select(PriceRecord).where(PriceRecord.product_id == product_id)
        ).all()
        for r in records:
            session.delete(r)
        logs = session.exec(
            select(ScrapeLog).where(ScrapeLog.product_id == product_id)
        ).all()
        for log in logs:
            session.delete(log)
        session.delete(product)
        session.commit()
    return RedirectResponse(url="/", status_code=303)
