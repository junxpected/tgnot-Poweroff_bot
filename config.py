"""Project configuration."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE_DIR = BASE_DIR / "database"

# Export in shell before run: export BOT_TOKEN="<telegram_token>"
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Admin users (Telegram user IDs)
ADMIN_IDS = [1201120661]

CITY_NAME = "Рівне"
TIMEZONE = "Europe/Kyiv"

SCHEDULE_URL = "https://www.roe.vsei.ua/disconnections"

# PDF files with address schedules
CITY_PDF_PATH = DATA_DIR / "GPV_cherga_misto_Rivne.pdf"
REGION_PDF_PATH = DATA_DIR / "GPV_cherga_Rivnenska_oblast.pdf"

# SQLite DB path
DB_PATH = DATABASE_DIR / "bot.db"
