"""Telegram bot handlers and entrypoint."""

from __future__ import annotations

import logging
from datetime import date

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN
from database.db import (
    get_schedule_for,
    get_schedule_for_date,
    get_user,
    init_db,
    set_user_address,
    upsert_user,
)
from services.address_lookup import AddressLookup
from services.scraper import scrape_and_store

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

STATE_CITY, STATE_STREET, STATE_HOUSE = range(3)
lookup = AddressLookup()


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🔍 Ввести адресу")],
            [KeyboardButton("📅 Графік на сьогодні")],
            [KeyboardButton("💡 Моя черга")],
            [KeyboardButton("📘 Графік моєї черги")],
        ],
        resize_keyboard=True,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    del context
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return ConversationHandler.END

    upsert_user(user.id, user.username or "", user.first_name or "")

    await message.reply_text(
        "🔌 Вітаю! Це бот графіків відключень світла Рівненщини ⚡\n\nОберіть дію:",
        reply_markup=main_menu(),
    )
    return ConversationHandler.END


async def address_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    del context
    message = update.effective_message
    if not message:
        return ConversationHandler.END

    await message.reply_text(
        "🏘 Введіть населений пункт (місто / село):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return STATE_CITY


async def save_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    if not message or not message.text:
        return ConversationHandler.END

    context.user_data["city"] = message.text.strip()
    await message.reply_text("📍 Введіть вулицю (або напишіть 'немає'):")
    return STATE_STREET


async def save_street(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    if not message or not message.text:
        return ConversationHandler.END

    street = message.text.strip()
    if street.lower() in ("немає", "-", "—"):
        street = ""

    context.user_data["street"] = street
    await message.reply_text("🏠 Введіть номер будинку (наприклад: 12):")
    return STATE_HOUSE


async def save_house(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    user = update.effective_user
    if not message or not message.text or not user:
        return ConversationHandler.END

    house = message.text.strip()
    city = context.user_data.get("city", "")
    street = context.user_data.get("street", "")

    # PDF rows often contain street names without exact "city + street" phrase,
    # so use street as a primary query. Fall back to city for cases like villages
    # where street can be omitted.
    query = street.strip() if street.strip() else city.strip()
    result, err = lookup.find_queue(query, house)

    if err == "NOT_FOUND":
        await message.reply_text(
            "❌ Не вдалося знайти вашу адресу!\n"
            "Приклад правильного формату:\n"
            "`Томахів`\n"
            "`1`\n"
            "Або:\n"
            "`Рівне`\n`Київська`\n`12`",
            parse_mode="Markdown",
            reply_markup=main_menu(),
        )
        return ConversationHandler.END

    if err == "EMPTY_STREET" or result is None:
        await message.reply_text(
            "❌ Некоректні дані адреси. Спробуйте ще раз.",
            reply_markup=main_menu(),
        )
        return ConversationHandler.END

    queue, subqueue, _source = result
    set_user_address(user.id, city, street, house, queue, subqueue)

    await message.reply_text(
        f"✅ Адреса збережена!\nВаша черга: *{queue}.{subqueue}*",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )
    return ConversationHandler.END


async def my_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    user_row = get_user(user.id)
    if not user_row or not user_row["queue"] or not user_row["subqueue"]:
        await message.reply_text("❌ Ви ще не вказали адресу.", reply_markup=main_menu())
        return

    await message.reply_text(
        f"💡 Ваша черга: *{user_row['queue']}.{user_row['subqueue']}*",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )


async def today_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    message = update.effective_message
    if not message:
        return

    today = date.today().strftime("%Y-%m-%d")
    schedule = get_schedule_for_date(today)

    if not schedule:
        await message.reply_text("📭 На сьогодні графік відсутній.", reply_markup=main_menu())
        return

    msg = [f"📅 *Графік на сьогодні ({today}):*", ""]
    for queue_code in sorted(schedule.keys()):
        msg.append(f"*Черга {queue_code}:*")
        msg.extend(f"• `{interval}`" for interval in schedule[queue_code])
        msg.append("")

    await message.reply_text("\n".join(msg), parse_mode="Markdown", reply_markup=main_menu())


async def my_queue_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    today = date.today().strftime("%Y-%m-%d")
    user_row = get_user(user.id)
    if not user_row or not user_row["queue"] or not user_row["subqueue"]:
        await message.reply_text("❌ Спочатку вкажіть адресу.", reply_markup=main_menu())
        return

    queue_code = f"{user_row['queue']}.{user_row['subqueue']}"
    rows = get_schedule_for(today, queue_code)

    msg = [f"📘 *Графік для {queue_code} на {today}:*", ""]
    if not rows:
        msg.append("❌ Відключень не заплановано.")
    else:
        for row in rows:
            msg.append(f"• `{row['off_time']}-{row['on_time']}`")

    await message.reply_text("\n".join(msg), parse_mode="Markdown", reply_markup=main_menu())


def build_application() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔍 Ввести адресу$"), address_start)],
        states={
            STATE_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_city)],
            STATE_STREET: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_street)],
            STATE_HOUSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_house)],
        },
        fallbacks=[],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^📅 Графік на сьогодні$"), today_schedule))
    app.add_handler(MessageHandler(filters.Regex("^💡 Моя черга$"), my_queue))
    app.add_handler(MessageHandler(filters.Regex("^📘 Графік моєї черги$"), my_queue_schedule))

    return app


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty. Set environment variable BOT_TOKEN.")

    init_db()
    lookup.load()

    try:
        scrape_and_store()
    except Exception:
        logger.exception("Failed to scrape schedule on startup")

    app = build_application()
    logger.info("Bot is running")
    app.run_polling()


if __name__ == "__main__":
    main()
