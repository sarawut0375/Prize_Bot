"""
Application configuration, loaded from environment variables (.env file).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    # --- Database ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'price_bot.db'}")

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # --- Scheduler ---
    # The bot re-checks prices on a random interval between these two values
    # (in minutes) each cycle, instead of a fixed interval - this looks less
    # like a bot to sites with anti-scraping protection (Shopee/Lazada).
    SCRAPE_INTERVAL_MIN_MINUTES: int = int(os.getenv("SCRAPE_INTERVAL_MIN_MINUTES", "10"))
    SCRAPE_INTERVAL_MAX_MINUTES: int = int(os.getenv("SCRAPE_INTERVAL_MAX_MINUTES", "30"))

    # --- Scraper behaviour ---
    REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "15"))
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    )

    # --- Web server ---
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


settings = Settings()
