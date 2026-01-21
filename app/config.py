import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_URL = "sqlite+aiosqlite:///power_bot.db"

DEFAULT_DAILY_HOUR = 7
DEFAULT_DAILY_MINUTE = 30
DEFAULT_REMIND_MINUTES = 60

RIVNE_SCHEDULE_URL = "https://www.roe.vsei.ua/disconnections"
