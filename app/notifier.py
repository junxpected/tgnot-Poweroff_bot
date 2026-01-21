import datetime as dt
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from aiogram import Bot
from .db import SessionLocal
from .models import User
from .schedule_source import get_schedule_for_date

scheduler = AsyncIOScheduler()

def _fmt_ranges(ranges):
    if not ranges:
        return "⏳ *Очікується* (години ще не опубліковані)"
    return "\n".join([f"• {a.strftime('%H:%M')}–{b.strftime('%H:%M')}" for a, b in ranges])

async def send_today(bot: Bot, user: User):
    if user.paused or not user.subqueue:
        return
    today = dt.date.today()
    updated, schedule = await get_schedule_for_date(today)
    ranges = schedule.get(user.subqueue, [])

    text = (
        f"⚡️ *Графік на {today.strftime('%d.%m.%Y')}*\n"
        f"Підчерга: *{user.subqueue}*\n\n"
        f"{_fmt_ranges(ranges)}\n\n"
        f"{('🕒 ' + updated + '\n') if updated else ''}"
        f"_Якщо на сайті 'Очікується' — це нормально, графік ще не дали._"
    )
    await bot.send_message(user.tg_id, text, parse_mode="Markdown")
    await plan_reminders(bot, user, ranges)

async def plan_reminders(bot: Bot, user: User, ranges):
    for job in scheduler.get_jobs():
        if job.id.startswith(f"rem_{user.tg_id}_"):
            job.remove()

    if not ranges or user.paused:
        return

    remind = int(user.remind_minutes)
    now = dt.datetime.now()

    for idx, (a, b) in enumerate(ranges):
        start_dt = dt.datetime.combine(dt.date.today(), a)
        end_dt = dt.datetime.combine(dt.date.today(), b)

        off_at = start_dt - dt.timedelta(minutes=remind)
        on_at = end_dt - dt.timedelta(minutes=remind)

        if off_at > now:
            scheduler.add_job(
                bot.send_message,
                "date",
                run_date=off_at,
                args=[user.tg_id, f"⏳ Через {remind} хв можливе *вимкнення*: {a.strftime('%H:%M')}–{b.strftime('%H:%M')}"],
                kwargs={"parse_mode": "Markdown"},
                id=f"rem_{user.tg_id}_{idx}_off",
                replace_existing=True,
            )
        if on_at > now:
            scheduler.add_job(
                bot.send_message,
                "date",
                run_date=on_at,
                args=[user.tg_id, f"✅ Через {remind} хв планове *увімкнення*: о {b.strftime('%H:%M')}"],
                kwargs={"parse_mode": "Markdown"},
                id=f"rem_{user.tg_id}_{idx}_on",
                replace_existing=True,
            )

def start_scheduler(bot: Bot):
    async def tick():
        now = dt.datetime.now()
        async with SessionLocal() as session:
            users = (await session.execute(select(User))).scalars().all()
        for u in users:
            if u.paused or not u.subqueue:
                continue
            if now.hour == u.daily_hour and now.minute == u.daily_minute:
                try:
                    await send_today(bot, u)
                except Exception:
                    pass

    scheduler.add_job(tick, "interval", minutes=1, id="tick", replace_existing=True)
    scheduler.start()
