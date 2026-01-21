from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .config import DB_URL

engine = create_async_engine(DB_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
