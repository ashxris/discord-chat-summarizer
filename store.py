"""SQLite persistence for per-guild Groq keys and enabled channels."""

from __future__ import annotations

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS guilds (
    guild_id INTEGER PRIMARY KEY,
    groq_key TEXT,
    model TEXT
);
CREATE TABLE IF NOT EXISTS channels (
    channel_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL
);
"""


class Store:
    """Small async wrapper around the settings database."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self.path)
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    def _require_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Store.connect() must be awaited first")
        return self._db

    async def settings(self, guild_id: int) -> tuple[str | None, str | None]:
        """Return (groq_key, model) for a guild; either may be None."""
        db = self._require_db()
        async with db.execute(
            "SELECT groq_key, model FROM guilds WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return (row[0], row[1]) if row else (None, None)

    async def set_key(self, guild_id: int, key: str) -> None:
        db = self._require_db()
        await db.execute(
            "INSERT INTO guilds (guild_id, groq_key) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET groq_key = excluded.groq_key",
            (guild_id, key),
        )
        await db.commit()

    async def clear_key(self, guild_id: int) -> None:
        db = self._require_db()
        await db.execute("UPDATE guilds SET groq_key = NULL WHERE guild_id = ?", (guild_id,))
        await db.commit()

    async def set_model(self, guild_id: int, model: str) -> None:
        db = self._require_db()
        await db.execute(
            "INSERT INTO guilds (guild_id, model) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET model = excluded.model",
            (guild_id, model),
        )
        await db.commit()

    async def enable_channel(self, guild_id: int, channel_id: int) -> None:
        db = self._require_db()
        await db.execute(
            "INSERT OR IGNORE INTO channels (channel_id, guild_id) VALUES (?, ?)",
            (channel_id, guild_id),
        )
        await db.commit()

    async def disable_channel(self, channel_id: int) -> None:
        db = self._require_db()
        await db.execute("DELETE FROM channels WHERE channel_id = ?", (channel_id,))
        await db.commit()

    async def enabled_channels(self) -> dict[int, int]:
        """Return {channel_id: guild_id} for every enabled channel."""
        db = self._require_db()
        async with db.execute("SELECT channel_id, guild_id FROM channels") as cursor:
            rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}
