"""
Price Bot web app.

  /            ผลลัพธ์ - every product with its lowest price, per-site prices, search links
  /product/ID  รายละเอียด - every saved offer for one product, with all details
  /manage      จัดการ - products, Telegram, Shopee API keys, search links, bookmarklet
  /capture     the small window the "เก็บราคา" bookmarklet opens
"""
import logging
import re
import secrets
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from pricebot import settings_store, shopee_api, shopee_sync, telegram
from pricebot.bookmarklet import bookmarklet_href
from pricebot.config import PACKAGE_DIR
from pricebot.database import engine, init_db
from pricebot.listings import notify, save_listing
from pricebot.models import Listing, Product
from pricebot.prices import fmt_price, parse_price
from pricebot.sources import SITES, build_search_url, detect_source, source_color, source_label

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    shopee_sync.start()
    yield


app = FastAPI(title="Price Bot", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")
templates.env.globals.update(
    csrf=settings_store.csrf_token,
    fmt_price=fmt_price,
    source_label=source_label,
    source_color=source_color,
    SITES=SITES,
)


# ---------------------------------------------------------------- helpers

def _check_csrf(token: str) -> None:
    if not secrets.compare_digest(token or "", settings_store.csrf_token()):
        raise HTTPException(status_code=403, detail="ฟอร์มหมดอายุ - รีเฟรชหน้าแล้วลองใหม่")


def _redirect(path: str, msg: str | None = None, err: str | None = None, anchor: str = "") -> RedirectResponse:
    params = []
    if msg:
        params.append("msg=" + quote(msg))
    if err:
        params.append("err=" + quote(err))
    query = ("?" + "&".join(params)) if params else ""
    return RedirectResponse(f"{path}{query}{'#' + anchor if anchor else ''}", status_code=303)


def _opt_float(value: str | None) -> float | None:
    return parse_price(value) if value and value.strip() else None


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _enabled_sites() -> list:
    return [s for s in SITES if settings_store.get_bool(f"site_enabled_{s.key}")]


def _search_links(keyword: str) -> list[dict]:
    return [
        {"site": s, "url": build_search_url(settings_store.get(f"search_url_{s.key}"), keyword)}
        for s in _enabled_sites()
    ]


def _get_product(session: Session, product_id: int) -> Product:
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="ไม่พบสินค้านี้")
    return product


def _summary(session: Session, product: Product) -> dict:
    listings = session.exec(select(Listing).where(Listing.product_id == product.id)).all()
    lowest = min(listings, key=lambda l: l.price) if listings else None
    by_source: dict[str, Listing] = {}
    for l in listings:
        if l.source not in by_source or l.price < by_source[l.source].price:
            by_source[l.source] = l
    return {
        "product": product,
        "count": len(listings),
        "lowest": lowest,
        "by_source": sorted(by_source.values(), key=lambda l: l.price),
        "hit_target": bool(lowest and product.target_price is not None and lowest.price <= product.target_price),
        "last_update": max((l.last_seen for l in listings), default=None),
        "search_links": _search_links(product.keyword),
    }


def _ctx(request: Request, **extra) -> dict:
    return {
        "request": request,
        "msg": request.query_params.get("msg"),
        "err": request.query_params.get("err"),
        "shopee_ready": shopee_sync.is_configured(),
        **extra,
    }


# ---------------------------------------------------------------- results

@app.get("/")
def results(request: Request):
    with Session(engine) as s:
        products = s.exec(select(Product).order_by(Product.is_active.desc(), Product.created_at.desc())).all()
        summaries = [_summary(s, p) for p in products]
    return templates.TemplateResponse("results.html", _ctx(request, summaries=summaries))


@app.get("/product/{product_id}")
def product_detail(request: Request, product_id: int):
    with Session(engine) as s:
        product = _get_product(s, product_id)
        summary = _summary(s, product)
        listings = s.exec(
            select(Listing).where(Listing.product_id == product_id).order_by(Listing.price)
        ).all()
    sources = sorted({l.source for l in listings})
    return templates.TemplateResponse(
        "product.html", _ctx(request, s=summary, listings=listings, sources=sources)
    )


@app.post("/product/{product_id}/listing")
def add_listing_manually(
    product_id: int,
    csrf: str = Form(""),
    title: str = Form(...),
    price: str = Form(...),
    url: str = Form(""),
    source: str = Form(""),
    seller: str = Form(""),
    location: str = Form(""),
    condition: str = Form(""),
    note: str = Form(""),
):
    _check_csrf(csrf)
    value = parse_price(price)
    if value is None:
        return _redirect(f"/product/{product_id}", err="ราคาไม่ถูกต้อง", anchor="add")
    with Session(engine) as s:
        product = _get_product(s, product_id)
        result = save_listing(
            s, product, source=_clean(source) or detect_source(url), title=title.strip(), price=value,
            url=_clean(url), seller=_clean(seller), location=_clean(location),
            condition=_clean(condition), note=_clean(note), via="manual",
        )
        notify(product, [result])
    return _redirect(f"/product/{product_id}", msg="บันทึกราคาแล้ว")


@app.post("/listing/{listing_id}/delete")
def delete_listing(listing_id: int, csrf: str = Form("")):
    _check_csrf(csrf)
    with Session(engine) as s:
        listing = s.get(Listing, listing_id)
        if not listing:
            raise HTTPException(status_code=404)
        product_id = listing.product_id
        s.delete(listing)
        s.commit()
    return _redirect(f"/product/{product_id}", msg="ลบรายการแล้ว")


@app.post("/product/{product_id}/shopee")
def shopee_now(product_id: int, csrf: str = Form(""), back: str = Form("")):
    _check_csrf(csrf)
    target = back if back.startswith("/") else f"/product/{product_id}"
    if not shopee_sync.is_configured():
        return _redirect(target, err="ยังไม่ได้ใส่ Shopee Affiliate API key ที่หน้าจัดการ")
    with Session(engine) as s:
        product = _get_product(s, product_id)
        count, err = shopee_sync.sync_product(s, product)
    if err:
        return _redirect(target, err=err)
    return _redirect(target, msg=f"ดึงจาก Shopee API ได้ {count} รายการ")


# ---------------------------------------------------------------- capture (bookmarklet)

@app.get("/capture")
def capture_form(
    request: Request, url: str = "", title: str = "", price: str = "", sel: str = "", image: str = ""
):
    with Session(engine) as s:
        products = s.exec(select(Product).where(Product.is_active == True).order_by(Product.name)).all()  # noqa: E712
        existing = None
        if url:
            existing = s.exec(select(Listing).where(Listing.url == url)).first()

    # Facebook titles look like "Marketplace - Old bike | Facebook" (sometimes with "(3) " in front).
    title = re.sub(r"^\(\d+\)\s*", "", title.strip())
    title = re.sub(r"^Marketplace\s*[-–]\s*", "", title)
    title = re.sub(r"\s*\|\s*Facebook$", "", title)

    # Highlighted text wins (that's the price the user pointed at), then page metadata.
    guess = parse_price(sel) if sel else None
    if guess is None:
        guess = parse_price(price)

    # Pre-select: the product this URL was saved under before, else best keyword match, else last used.
    title_l = title.lower()
    best_id, best_score = None, 0
    for p in products:
        words = [w for w in p.keyword.lower().split() if w]
        score = sum(1 for w in words if w in title_l)
        if words and score > best_score:
            best_id, best_score = p.id, score
    if existing:
        best_id = existing.product_id
    if best_id is None:
        last = request.cookies.get("pb_last_product")
        best_id = int(last) if last and last.isdigit() else None

    return templates.TemplateResponse(
        "capture.html",
        _ctx(
            request, products=products, url=url, title=title.strip(), price=guess, image=image,
            source=detect_source(url), selected_id=best_id, existing=existing, sel=sel,
        ),
    )


@app.post("/capture")
def capture_save(
    request: Request,
    csrf: str = Form(""),
    product_id: int = Form(...),
    title: str = Form(...),
    price: str = Form(...),
    url: str = Form(""),
    source: str = Form(""),
    seller: str = Form(""),
    location: str = Form(""),
    condition: str = Form(""),
    note: str = Form(""),
    image_url: str = Form(""),
):
    _check_csrf(csrf)
    value = parse_price(price)
    if value is None:
        raise HTTPException(status_code=400, detail="ราคาไม่ถูกต้อง")
    with Session(engine) as s:
        product = _get_product(s, product_id)
        result = save_listing(
            s, product, source=_clean(source) or detect_source(url), title=title.strip(), price=value,
            url=_clean(url), seller=_clean(seller), location=_clean(location),
            condition=_clean(condition), note=_clean(note), image_url=_clean(image_url), via="bookmarklet",
        )
        sent = notify(product, [result])
        product_name = product.name
    response = templates.TemplateResponse(
        "capture_done.html",
        _ctx(request, result=result, product_name=product_name, product_id=product_id, telegram=sent),
    )
    response.set_cookie("pb_last_product", str(product_id), max_age=60 * 60 * 24 * 180, samesite="lax")
    return response


# ---------------------------------------------------------------- manage

@app.get("/manage")
def manage(request: Request):
    with Session(engine) as s:
        products = s.exec(select(Product).order_by(Product.is_active.desc(), Product.created_at.desc())).all()
    cfg = settings_store.all_settings()
    return templates.TemplateResponse(
        "manage.html",
        _ctx(
            request, products=products, cfg=cfg, mask=settings_store.mask,
            bookmarklet=bookmarklet_href(cfg["base_url"]),
        ),
    )


@app.post("/manage/products/add")
def product_add(
    csrf: str = Form(""), name: str = Form(...), keyword: str = Form(""),
    target_price: str = Form(""), note: str = Form(""),
):
    _check_csrf(csrf)
    name = name.strip()
    if not name:
        return _redirect("/manage", err="กรุณาใส่ชื่อสินค้า", anchor="products")
    with Session(engine) as s:
        s.add(Product(name=name, keyword=keyword.strip() or name, target_price=_opt_float(target_price), note=_clean(note)))
        s.commit()
    return _redirect("/manage", msg=f"เพิ่ม \"{name}\" แล้ว", anchor="products")


@app.post("/manage/products/{product_id}/update")
def product_update(
    product_id: int, csrf: str = Form(""), name: str = Form(...), keyword: str = Form(""),
    target_price: str = Form(""), note: str = Form(""), is_active: str = Form(""),
):
    _check_csrf(csrf)
    with Session(engine) as s:
        p = _get_product(s, product_id)
        p.name = name.strip() or p.name
        p.keyword = keyword.strip() or p.name
        p.target_price = _opt_float(target_price)
        p.note = _clean(note)
        p.is_active = is_active == "1"
        s.commit()
    return _redirect("/manage", msg="บันทึกการแก้ไขแล้ว", anchor="products")


@app.post("/manage/products/{product_id}/delete")
def product_delete(product_id: int, csrf: str = Form("")):
    _check_csrf(csrf)
    with Session(engine) as s:
        p = _get_product(s, product_id)
        for l in s.exec(select(Listing).where(Listing.product_id == product_id)).all():
            s.delete(l)
        s.delete(p)
        s.commit()
    return _redirect("/manage", msg="ลบสินค้าและราคาที่บันทึกไว้ทั้งหมดแล้ว", anchor="products")


@app.post("/manage/telegram")
def manage_telegram(
    csrf: str = Form(""), action: str = Form("save"), bot_token: str = Form(""), chat_id: str = Form(""),
    notify_target: str = Form(""), notify_new_lowest: str = Form(""), notify_price_change: str = Form(""),
):
    _check_csrf(csrf)
    values = {
        "telegram_chat_id": chat_id.strip(),
        "notify_target": "1" if notify_target else "0",
        "notify_new_lowest": "1" if notify_new_lowest else "0",
        "notify_price_change": "1" if notify_price_change else "0",
    }
    if bot_token.strip():  # blank = keep the saved token
        values["telegram_bot_token"] = bot_token.strip()
    settings_store.set_many(values)
    if action == "test":
        ok, info = telegram.send("✅ ทดสอบจาก Price Bot — ตั้งค่า Telegram สำเร็จ")
        return _redirect("/manage", msg=info if ok else None, err=None if ok else info, anchor="telegram")
    return _redirect("/manage", msg="บันทึกการตั้งค่า Telegram แล้ว", anchor="telegram")


@app.post("/manage/telegram/clear")
def manage_telegram_clear(csrf: str = Form("")):
    _check_csrf(csrf)
    settings_store.set_many({"telegram_bot_token": "", "telegram_chat_id": ""})
    return _redirect("/manage", msg="ลบ Token Telegram แล้ว", anchor="telegram")


@app.post("/manage/shopee")
def manage_shopee(
    csrf: str = Form(""), action: str = Form("save"), app_id: str = Form(""), secret: str = Form(""),
    enabled: str = Form(""), interval: str = Form("60"), limit: str = Form("10"),
):
    _check_csrf(csrf)
    values = {
        "shopee_app_id": app_id.strip(),
        "shopee_api_enabled": "1" if enabled else "0",
        "shopee_api_interval_minutes": str(max(0, int(parse_price(interval) or 0))),
        "shopee_api_limit": str(min(50, max(1, int(parse_price(limit) or 10)))),
    }
    if secret.strip():
        values["shopee_secret"] = secret.strip()
    settings_store.set_many(values)
    shopee_sync.reschedule()
    if action == "test":
        try:
            items = shopee_api.search(
                "iphone", settings_store.get("shopee_app_id"), settings_store.get("shopee_secret"), limit=1
            )
        except shopee_api.ShopeeApiError as exc:
            return _redirect("/manage", err=str(exc), anchor="shopee")
        sample = f" เช่น \"{items[0].title[:40]}\" {fmt_price(items[0].price)} บาท" if items else ""
        return _redirect("/manage", msg=f"เชื่อมต่อ Shopee API สำเร็จ{sample}", anchor="shopee")
    return _redirect("/manage", msg="บันทึกการตั้งค่า Shopee API แล้ว", anchor="shopee")


@app.post("/manage/shopee/clear")
def manage_shopee_clear(csrf: str = Form("")):
    _check_csrf(csrf)
    settings_store.set_many({"shopee_app_id": "", "shopee_secret": "", "shopee_api_enabled": "0"})
    shopee_sync.reschedule()
    return _redirect("/manage", msg="ลบ key ของ Shopee แล้ว", anchor="shopee")


@app.post("/manage/sites")
async def manage_sites(request: Request):
    form = await request.form()
    _check_csrf(str(form.get("csrf", "")))
    values = {}
    for site in SITES:
        template = str(form.get(f"search_url_{site.key}", "")).strip()
        if template and "{q}" not in template:
            return _redirect("/manage", err=f"ลิงก์ของ {site.label} ต้องมี {{q}} ตรงตำแหน่งคำค้นหา", anchor="sites")
        values[f"search_url_{site.key}"] = template or site.default_search_url
        values[f"site_enabled_{site.key}"] = "1" if form.get(f"site_enabled_{site.key}") else "0"
    settings_store.set_many(values)
    return _redirect("/manage", msg="บันทึกลิงก์ค้นหาแล้ว", anchor="sites")


@app.post("/manage/sites/reset")
def manage_sites_reset(csrf: str = Form("")):
    _check_csrf(csrf)
    settings_store.set_many({f"search_url_{s.key}": s.default_search_url for s in SITES})
    return _redirect("/manage", msg="คืนค่าลิงก์ค้นหาเริ่มต้นแล้ว", anchor="sites")


@app.post("/manage/general")
def manage_general(csrf: str = Form(""), base_url: str = Form("")):
    _check_csrf(csrf)
    base = base_url.strip().rstrip("/") or "http://localhost:8000"
    if not base.startswith(("http://", "https://")):
        return _redirect("/manage", err="ที่อยู่ต้องขึ้นต้นด้วย http:// หรือ https://", anchor="bookmarklet")
    settings_store.set_many({"base_url": base})
    return _redirect("/manage", msg="บันทึกแล้ว — ลากปุ่มเก็บราคาไปที่แถบ Bookmark ใหม่อีกครั้ง", anchor="bookmarklet")
