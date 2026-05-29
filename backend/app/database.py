import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event

from app.config import settings

logger = logging.getLogger("db")


def _build_engine():
    """Создаёт async engine с учётом TLS / SQLCipher."""
    url = settings.DATABASE_URL
    connect_args = {}

    if "sqlite" in url:
        # SQLCipher: если задан DB_ENCRYPTION_KEY и доступен драйвер
        eng = create_async_engine(url, echo=False, connect_args=connect_args)
        if settings.DB_ENCRYPTION_KEY:
            # Применяем PRAGMA key на каждом соединении (работает только если используется
            # sqlcipher-совместимый драйвер; на обычном aiosqlite будет проигнорировано).
            @event.listens_for(eng.sync_engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, _):
                try:
                    cur = dbapi_connection.cursor()
                    cur.execute(f"PRAGMA key='{settings.DB_ENCRYPTION_KEY}';")
                    cur.execute("PRAGMA cipher_compatibility=4;")
                    cur.close()
                    logger.info("SQLCipher: ключ применён")
                except Exception as e:
                    logger.warning("SQLCipher недоступен (%s) — БД работает без шифрования", e)
        return eng

    # PostgreSQL/другие — принудительный TLS если включено
    if settings.DB_REQUIRE_TLS and "postgresql" in url:
        if "sslmode" not in url and "ssl=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}ssl=require"
        connect_args["ssl"] = True
    return create_async_engine(url, echo=False, pool_size=20, max_overflow=10, connect_args=connect_args)


engine = _build_engine()

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
