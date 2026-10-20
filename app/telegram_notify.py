"""
Minimal Telegram notifier - no extra SDK, just calls the Bot API directly.

Setup:
  1. Talk to @BotFather on Telegram, send /newbot, follow the prompts.
     You'll get a token like `123456789:ABCdefGhIJKlmNoPQRstuVWXyz`.
  2. Put it in .env as TELEGRAM_BOT_TOKEN.
  3. Send any message to your new bot, then open:
     https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
     and find "chat":{"id": ...} - that number is TELEGRAM_CHAT_ID.
"""
import logging

import requests

from app.config import settings

logger = logging.getLogger("price_bot.telegram")

API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_message(text: str) -> bool:
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing); "
                        "skipping notification:\n%s", text)
        return False

    url = API_URL.format(token=settings.TELEGRAM_BOT_TOKEN)
    try:
        resp = requests.post(
            url,
            data={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error("Telegram API error %s: %s", resp.status_code, resp.text)
            return False
        return True
    except requests.RequestException as exc:
        logger.error("Failed to send Telegram message: %s", exc)
        return False
