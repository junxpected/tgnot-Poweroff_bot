import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from .config import BOT_TOKEN, DEFAULT_DAILY_HOUR, DEFAULT_DAILY_MINUTE, DEFAULT_REMIND_MINUTES
from .db import engine, SessionLocal
from .models import Base, User
from .notifier import start_scheduler, send_today

SUBQUEUES = [f"{q}.{s}" for q in range(1,7) for s in (1,2)]

def kb_subqueues():
    kb = InlineKeyboardBuilder()
    for sq in SUBQUEUES:
        kb.button(text=sq, callback_data=f"q:{sq}")
    kb.adjust(4)
    return kb.as_markup()

def kb_main():
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Сьогодні", callback_data="today")
    kb.button(text="⚙️ Змінити підчергу", callback_data="change")
    kb.adjust(2)
    return kb.as_markup()

async def get_or_create_user(tg_id: int) -> User:
    async with SessionLocal() as session:
        u = (await session.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
        if u:
            return u
        u = User(
            tg_id=tg_id,
            subqueue="",
            daily_hour=DEFAULT_DAILY_HOUR,
            daily_minute=DEFAULT_DAILY_MINUTE,
            remind_minutes=DEFAULT_REMIND_MINUTES,
            paused=False,
        )
        session.add(u)
        await session.commit()
        return u

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    @dp.message(F.text == "/start")
    async def start(m: Message):
        u = await get_or_create_user(m.from_user.id)
        if not u.subqueue:
            await m.answer(
                "Обери *підчергу* (1.1–6.2).\n"
                "Після цього натисни 'Сьогодні' — я покажу дані з сайту Рівнеобленерго.",
                parse_mode="Markdown",
                reply_markup=kb_subqueues()
            )
        else:
            await m.answer(f"Твоя підчерга: *{u.subqueue}*.", parse_mode="Markdown", reply_markup=kb_main())

    @dp.message(F.text.in_({"/today", "/сегодня", "/сьогодні"}))
    async def today_cmd(m: Message):
        async with SessionLocal() as session:
            u = (await session.execute(select(User).where(User.tg_id == m.from_user.id))).scalar_one_or_none()
        if not u or not u.subqueue:
            await m.answer("Спочатку вибери підчергу командою /start")
            return
        await send_today(bot, u)

    @dp.callback_query(F.data.startswith("q:"))
    async def setq(c: CallbackQuery):
        sq = c.data.split(":")[1]
        async with SessionLocal() as session:
            u = (await session.execute(select(User).where(User.tg_id == c.from_user.id))).scalar_one_or_none()
            if not u:
                u = User(tg_id=c.from_user.id)
                session.add(u)
            u.subqueue = sq
            u.paused = False
            await session.commit()
        await c.message.edit_text(
            f"✅ Підчерга збережена: *{sq}*\n\nНатисни 'Сьогодні', щоб перевірити.",
            parse_mode="Markdown",
            reply_markup=kb_main()
        )
        await c.answer()

    @dp.callback_query(F.data == "today")
    async def today_btn(c: CallbackQuery):
        async with SessionLocal() as session:
            u = (await session.execute(select(User).where(User.tg_id == c.from_user.id))).scalar_one()
        await send_today(bot, u)
        await c.answer("Ок")

    @dp.callback_query(F.data == "change")
    async def change_btn(c: CallbackQuery):
        await c.message.edit_text("Обери іншу підчергу:", reply_markup=kb_subqueues())
        await c.answer()

    start_scheduler(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
