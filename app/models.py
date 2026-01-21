from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subqueue: Mapped[str] = mapped_column(String(8), default="")  # 1.1 .. 6.2
    daily_hour: Mapped[int] = mapped_column(Integer, default=7)
    daily_minute: Mapped[int] = mapped_column(Integer, default=30)
    remind_minutes: Mapped[int] = mapped_column(Integer, default=60)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
