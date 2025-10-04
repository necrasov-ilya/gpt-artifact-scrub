from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from ..domain.models import EmojiJobOutcome, EmojiPackRequest, EmojiPackResult, EmojiGridOption, UserSettings


@dataclass(frozen=True)
class UsageStatRow:
    user_id: int
    username: str | None
    display_name: str | None
    total_count: int


@dataclass
class Storage:
    path: Path

    async def initialize(self) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    default_grid TEXT NOT NULL,
                    default_padding INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS emoji_jobs (
                    user_id INTEGER NOT NULL,
                    image_hash TEXT NOT NULL,
                    grid TEXT NOT NULL,
                    padding INTEGER NOT NULL,
                    short_name TEXT NOT NULL,
                    link TEXT NOT NULL,
                    custom_emoji_ids TEXT NOT NULL,
                    fragment_preview_id TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, image_hash, grid, padding)
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_stats (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    display_name TEXT,
                    total_count INTEGER NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                )
                """
            )
            await db.commit()

    async def get_user_settings(self, user_id: int) -> UserSettings | None:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT default_grid, default_padding FROM user_settings WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
        if not row:
            return None
        grid = EmojiGridOption.decode(row[0])
        return UserSettings(user_id=user_id, default_grid=grid, default_padding=int(row[1]))

    async def upsert_user_settings(self, settings: UserSettings) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO user_settings (user_id, default_grid, default_padding, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    default_grid = excluded.default_grid,
                    default_padding = excluded.default_padding,
                    updated_at = excluded.updated_at
                """,
                (
                    settings.user_id,
                    settings.default_grid.encode(),
                    settings.default_padding,
                    datetime.now(UTC).isoformat(),
                ),
            )
            await db.commit()

    async def get_cached_job(self, request: EmojiPackRequest) -> EmojiJobOutcome | None:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT short_name, link, custom_emoji_ids, fragment_preview_id
                FROM emoji_jobs
                WHERE user_id = ? AND image_hash = ? AND grid = ? AND padding = ?
                """,
                (
                    request.user_id,
                    request.image_hash,
                    request.grid.encode(),
                    request.padding,
                ),
            )
            row = await cursor.fetchone()
            await cursor.close()
        if not row:
            return None
        custom_ids = json.loads(row[2])
        result = EmojiPackResult(
            short_name=row[0],
            link=row[1],
            custom_emoji_ids=custom_ids,
            fragment_preview_id=row[3],
        )
        return EmojiJobOutcome(request=request, result=result)

    async def save_job_outcome(self, outcome: EmojiJobOutcome) -> None:
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO emoji_jobs (
                    user_id, image_hash, grid, padding,
                    short_name, link, custom_emoji_ids, fragment_preview_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outcome.request.user_id,
                    outcome.request.image_hash,
                    outcome.request.grid.encode(),
                    outcome.request.padding,
                    outcome.result.short_name,
                    outcome.result.link,
                    json.dumps(list(outcome.result.custom_emoji_ids)),
                    outcome.result.fragment_preview_id,
                    datetime.now(UTC).isoformat(),
                ),
            )
            await db.commit()

    async def increment_usage(
        self,
        *,
        user_id: int,
        username: str | None,
        display_name: str | None,
    ) -> None:
        normalized_username = (username or "").strip() or None
        normalized_display = (display_name or "").strip() or None
        now = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                """
                INSERT INTO usage_stats (user_id, username, display_name, total_count, first_seen, last_seen)
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    total_count = usage_stats.total_count + 1,
                    username = CASE
                        WHEN excluded.username IS NOT NULL AND excluded.username != '' THEN excluded.username
                        ELSE usage_stats.username
                    END,
                    display_name = CASE
                        WHEN excluded.display_name IS NOT NULL AND excluded.display_name != '' THEN excluded.display_name
                        ELSE usage_stats.display_name
                    END,
                    last_seen = excluded.last_seen
                """,
                (
                    user_id,
                    normalized_username,
                    normalized_display,
                    now,
                    now,
                ),
            )
            await db.commit()

    async def get_usage_stats(self, *, offset: int, limit: int) -> tuple[list[UsageStatRow], int, int]:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                """
                SELECT user_id, username, display_name, total_count
                FROM usage_stats
                ORDER BY total_count DESC, last_seen DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = await cursor.fetchall()
            await cursor.close()
            cursor = await db.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(total_count), 0)
                FROM usage_stats
                """
            )
            totals_row = await cursor.fetchone()
            await cursor.close()
        entries = [
            UsageStatRow(
                user_id=int(row[0]),
                username=row[1],
                display_name=row[2],
                total_count=int(row[3]),
            )
            for row in rows
        ]
        total_users = int(totals_row[0]) if totals_row and totals_row[0] is not None else 0
        total_events = int(totals_row[1]) if totals_row and totals_row[1] is not None else 0
        return entries, total_users, total_events
