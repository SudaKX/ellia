from __future__ import annotations

from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def ensure_sqlite_database_directory(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or url.database in {None, ":memory:"}:
        return
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)


def _configure_sqlite_connection(dbapi_connection: object, _: object) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[union-attr]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


class Database:
    def __init__(self, database_url: str) -> None:
        ensure_sqlite_database_directory(database_url)
        url = make_url(database_url)
        connect_args = {"check_same_thread": False} if url.get_backend_name() == "sqlite" else {}
        self.engine: AsyncEngine = create_async_engine(
            database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        if url.get_backend_name() == "sqlite":
            event.listen(self.engine.sync_engine, "connect", _configure_sqlite_connection)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def dispose(self) -> None:
        await self.engine.dispose()
