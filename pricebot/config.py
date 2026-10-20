"""
Startup-only configuration. Everything a user should change (Telegram,
Shopee API keys, search links ...) lives in the database and is edited
from the /manage page instead - see settings_store.py.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PACKAGE_DIR = Path(__file__).resolve().parent

# 127.0.0.1 = only this computer can open the web page. The manage page holds
# API keys, so don't change this to 0.0.0.0 unless you know who's on your network.
HOST = os.getenv("PRICEBOT_HOST", "127.0.0.1")
PORT = int(os.getenv("PRICEBOT_PORT", "8000"))

DATABASE_PATH = Path(os.getenv("PRICEBOT_DB", str(BASE_DIR / "pricebot.db")))
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
