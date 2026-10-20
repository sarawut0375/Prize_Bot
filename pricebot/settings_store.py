"""
All user-editable settings, stored in the `setting` table and edited from
the /manage page. Secrets stay on this computer (in pricebot.db) and are
never shown in full on the page.
"""
import secrets

from sqlmodel import Session, select

from pricebot.database import engine
from pricebot.models import Setting
from pricebot.sources import SITES

DEFAULTS: dict[str, str] = {
    # Telegram
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "notify_target": "1",       # price at/below a product's target price
    "notify_new_lowest": "1",   # new lowest price for a product
    "notify_price_change": "1",  # a saved listing's price changed
    # Shopee Affiliate Open API (official)
    "shopee_app_id": "",
    "shopee_secret": "",
    "shopee_api_enabled": "0",
    "shopee_api_interval_minutes": "60",  # 0 = only when you press the button
    "shopee_api_limit": "10",
    # Bookmarklet
    "base_url": "http://localhost:8000",
}
for _site in SITES:
    DEFAULTS[f"search_url_{_site.key}"] = _site.default_search_url
    DEFAULTS[f"site_enabled_{_site.key}"] = "1"

SECRET_KEYS = {"telegram_bot_token", "shopee_secret"}


def get(key: str) -> str:
    with Session(engine) as s:
        row = s.get(Setting, key)
        if row is not None:
            return row.value
    return DEFAULTS.get(key, "")


def get_bool(key: str) -> bool:
    return get(key) == "1"


def get_int(key: str, fallback: int = 0) -> int:
    try:
        return int(get(key))
    except ValueError:
        return fallback


def all_settings() -> dict[str, str]:
    values = dict(DEFAULTS)
    with Session(engine) as s:
        for row in s.exec(select(Setting)).all():
            values[row.key] = row.value
    return values


def set_many(values: dict[str, str]) -> None:
    with Session(engine) as s:
        for key, value in values.items():
            row = s.get(Setting, key)
            if row is None:
                s.add(Setting(key=key, value=value))
            else:
                row.value = value
        s.commit()


def mask(value: str) -> str:
    if not value:
        return ""
    return "••••••" + value[-4:] if len(value) > 4 else "••••"


def csrf_token() -> str:
    """Per-install token embedded in every form, so other websites can't
    submit forms to this app behind your back."""
    token = get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        set_many({"csrf_token": token})
    return token
