from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

if "sqlite" in settings.DATABASE_URL:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
else:
    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_size=20, max_overflow=10)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight in-place migrations for SQLite (adds new columns if missing)
        await _ensure_columns(conn)


async def _ensure_columns(conn):
    """Add new columns to existing tables if they don't exist (SQLite only)."""
    if "sqlite" not in settings.DATABASE_URL:
        return
    from sqlalchemy import text

    async def has_column(table: str, col: str) -> bool:
        res = await conn.execute(text(f"PRAGMA table_info({table})"))
        return any(r[1] == col for r in res.fetchall())

    async def add_column(table: str, definition: str):
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {definition}"))

    try:
        if not await has_column("messages", "allow_download"):
            await add_column("messages", "allow_download BOOLEAN DEFAULT 1")
    except Exception as e:
        print(f"[migrations] messages.allow_download: {e}")
