"""SQLite persistence for per-guild Groq keys and enabled channels."""

from __future__ import annotations

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS guilds (
    guild_id INTEGER PRIMARY KEY,
    groq_key TEXT,
    model TEXT,
    interval_seconds REAL,
    message_threshold INTEGER
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
        for col, col_type in [("interval_seconds", "REAL"), ("message_threshold", "INTEGER")]:
            try:
                await self._db.execute(f"ALTER TABLE guilds ADD COLUMN {col} {col_type}")
            except Exception:
                pass
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    def _require_db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Store.connect() must be awaited first")
        return self._db

    async def settings(self, guild_id: int) -> tuple[str | None, str | None, float | None, int | None]:
        """Return (groq_key, model, interval_seconds, message_threshold) for a guild."""
        db = self._require_db()
        async with db.execute(
            "SELECT groq_key, model, interval_seconds, message_threshold FROM guilds WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return (row[0], row[1], row[2], row[3]) if row else (None, None, None, None)

    async def set_interval(self, guild_id: int, seconds: float) -> None:
        db = self._require_db()
        await db.execute(
            "INSERT INTO guilds (guild_id, interval_seconds) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET interval_seconds = excluded.interval_seconds",
            (guild_id, seconds),
        )
        await db.commit()

    async def set_threshold(self, guild_id: int, count: int) -> None:
        db = self._require_db()
        await db.execute(
            "INSERT INTO guilds (guild_id, message_threshold) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET message_threshold = excluded.message_threshold",
            (guild_id, count),
        )
        await db.commit()

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
