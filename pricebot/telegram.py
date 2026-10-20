"""
Telegram notifications through the Bot API (no extra SDK).

Getting a token / chat id (also shown on the /manage page):
  1. In Telegram, talk to @BotFather -> /newbot -> copy the token.
  2. Send any message to your new bot.
  3. Open https://api.telegram.org/bot<TOKEN>/getUpdates and copy "chat":{"id": ...}.
"""
import logging

import requests

from pricebot import settings_store

logger = logging.getLogger("pricebot.telegram")


def send(text: str, token: str | None = None, chat_id: str | None = None) -> tuple[bool, str]:
    token = token if token is not None else settings_store.get("telegram_bot_token")
    chat_id = chat_id if chat_id is not None else settings_store.get("telegram_chat_id")
    if not token or not chat_id:
        logger.info("Telegram not configured - skipping message:\n%s", text)
        return False, "ยังไม่ได้ตั้งค่า Telegram (Bot Token / Chat ID)"
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        # The token is part of the request URL, so it appears inside the
        # exception text - never show or log it.
        detail = str(exc).replace(token, settings_store.mask(token))
        logger.error("Telegram request failed: %s", detail)
        return False, f"เชื่อมต่อ Telegram ไม่ได้: {detail}"
    if resp.status_code != 200:
        try:
            desc = resp.json().get("description", resp.text)
        except ValueError:
            desc = resp.text
        logger.error("Telegram API error %s: %s", resp.status_code, desc)
        return False, f"Telegram ตอบกลับ error {resp.status_code}: {desc}"
    return True, "ส่งข้อความสำเร็จ"
