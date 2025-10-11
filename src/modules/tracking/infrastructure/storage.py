"""
SQLite-based repository for tracking data.
"""
from datetime import UTC, datetime
from pathlib import Path
from typing import List, Optional

import aiosqlite

from src.modules.tracking.domain.interfaces import TrackingRepository
from src.modules.tracking.domain.models import TrackingLink, TrackingEvent, LinkStats


class SQLiteTrackingRepository(TrackingRepository):
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
    
    async def initialize(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tracking_links (
                    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    deleted_at TEXT
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tracking_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    link_id INTEGER NOT NULL,
                    tg_user_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    first_start INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (link_id) REFERENCES tracking_links(link_id)
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_tracking_links_slug 
                ON tracking_links(slug) 
                WHERE deleted_at IS NULL
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_tracking_links_deleted 
                ON tracking_links(deleted_at)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_tracking_events_link_id 
                ON tracking_events(link_id)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_tracking_events_created_at 
                ON tracking_events(created_at)
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_tracking_events_link_user 
                ON tracking_events(link_id, tg_user_id)
            """)
            
            await db.commit()
    
    async def create_link(self, tag: str, slug: str) -> TrackingLink:
        now = datetime.now(UTC)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO tracking_links (tag, slug, created_at, deleted_at)
                VALUES (?, ?, ?, NULL)
                """,
                (tag, slug, now.isoformat())
            )
            link_id = cursor.lastrowid
            await db.commit()
            await cursor.close()
        
        return TrackingLink(
            link_id=link_id,
            tag=tag,
            slug=slug,
            created_at=now,
            deleted_at=None
        )
    
    async def get_link_by_id(self, link_id: int, include_deleted: bool = False) -> Optional[TrackingLink]:
        async with aiosqlite.connect(self.db_path) as db:
            query = "SELECT link_id, tag, slug, created_at, deleted_at FROM tracking_links WHERE link_id = ?"
            if not include_deleted:
                query += " AND deleted_at IS NULL"
            
            cursor = await db.execute(query, (link_id,))
            row = await cursor.fetchone()
            await cursor.close()
        
        if not row:
            return None
        
        return self._row_to_link(row)
    
    async def get_link_by_slug(self, slug: str, include_deleted: bool = False) -> Optional[TrackingLink]:
        async with aiosqlite.connect(self.db_path) as db:
            query = "SELECT link_id, tag, slug, created_at, deleted_at FROM tracking_links WHERE slug = ?"
            if not include_deleted:
                query += " AND deleted_at IS NULL"
            
            cursor = await db.execute(query, (slug,))
            row = await cursor.fetchone()
            await cursor.close()
        
        if not row:
            return None
        
        return self._row_to_link(row)
    
    async def list_links(self, include_deleted: bool = False) -> List[TrackingLink]:
        async with aiosqlite.connect(self.db_path) as db:
            query = "SELECT link_id, tag, slug, created_at, deleted_at FROM tracking_links"
            if not include_deleted:
                query += " WHERE deleted_at IS NULL"
            query += " ORDER BY created_at DESC"
            
            cursor = await db.execute(query)
            rows = await cursor.fetchall()
            await cursor.close()
        
        return [self._row_to_link(row) for row in rows]
    
    async def soft_delete_link(self, link_id: int) -> bool:
        now = datetime.now(UTC)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                UPDATE tracking_links 
                SET deleted_at = ? 
                WHERE link_id = ? AND deleted_at IS NULL
                """,
                (now.isoformat(), link_id)
            )
            affected = cursor.rowcount
            await db.commit()
            await cursor.close()
        
        return affected > 0
    
    async def log_event(
        self,
        link_id: int,
        tg_user_id: int,
        event_type: str,
        first_start: bool
    ) -> TrackingEvent:
        now = datetime.now(UTC)
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO tracking_events (link_id, tg_user_id, event_type, first_start, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (link_id, tg_user_id, event_type, int(first_start), now.isoformat())
            )
            event_id = cursor.lastrowid
            await db.commit()
            await cursor.close()
        
        return TrackingEvent(
            event_id=event_id,
            link_id=link_id,
            tg_user_id=tg_user_id,
            event_type=event_type,
            first_start=first_start,
            created_at=now
        )
    
    async def has_user_started_link(self, link_id: int, tg_user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT 1 FROM tracking_events 
                WHERE link_id = ? AND tg_user_id = ? 
                LIMIT 1
                """,
                (link_id, tg_user_id)
            )
            row = await cursor.fetchone()
            await cursor.close()
        
        return row is not None
    
    async def get_events_for_link(
        self,
        link_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[TrackingEvent]:
        query = """
            SELECT event_id, link_id, tg_user_id, event_type, first_start, created_at 
            FROM tracking_events 
            WHERE link_id = ?
        """
        params = [link_id]
        
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            from datetime import timedelta
            end_date_inclusive = end_date + timedelta(days=1)
            query += " AND created_at < ?"
            params.append(end_date_inclusive.isoformat())
        
        query += " ORDER BY created_at DESC"
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            await cursor.close()
        
        return [self._row_to_event(row) for row in rows]
    
    async def get_aggregated_stats(
        self,
        link_ids: Optional[List[int]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        daily: bool = False
    ) -> List[LinkStats]:
        if daily:
            query = """
                SELECT 
                    l.link_id,
                    l.tag,
                    l.slug,
                    date(e.created_at) as event_date,
                    COUNT(*) as total_events,
                    COUNT(DISTINCT e.tg_user_id) as unique_users,
                    SUM(e.first_start) as first_starts
                FROM tracking_links l
                INNER JOIN tracking_events e ON l.link_id = e.link_id
                WHERE l.deleted_at IS NULL
            """
        else:
            query = """
                SELECT 
                    l.link_id,
                    l.tag,
                    l.slug,
                    NULL as event_date,
                    COUNT(*) as total_events,
                    COUNT(DISTINCT e.tg_user_id) as unique_users,
                    SUM(e.first_start) as first_starts
                FROM tracking_links l
                INNER JOIN tracking_events e ON l.link_id = e.link_id
                WHERE l.deleted_at IS NULL
            """
        
        params = []
        
        if link_ids:
            placeholders = ','.join('?' * len(link_ids))
            query += f" AND l.link_id IN ({placeholders})"
            params.extend(link_ids)
        
        if start_date:
            query += " AND e.created_at >= ?"
            params.append(start_date.isoformat())
        
        if end_date:
            from datetime import timedelta
            end_date_inclusive = end_date + timedelta(days=1)
            query += " AND e.created_at < ?"
            params.append(end_date_inclusive.isoformat())
        
        if daily:
            query += " GROUP BY l.link_id, l.tag, l.slug, event_date ORDER BY event_date, l.link_id"
        else:
            query += " GROUP BY l.link_id, l.tag, l.slug ORDER BY l.link_id"
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            await cursor.close()
        
        results = []
        for row in rows:
            date_str = row[3]
            date_obj = datetime.fromisoformat(date_str).replace(tzinfo=UTC) if date_str else None
            
            results.append(LinkStats(
                link_id=row[0],
                tag=row[1],
                slug=row[2],
                date=date_obj,
                total_events=row[4],
                unique_users=row[5],
                first_starts=row[6] or 0
            ))
        
        return results
    
    def _row_to_link(self, row) -> TrackingLink:
        deleted_at = datetime.fromisoformat(row[4]).replace(tzinfo=UTC) if row[4] else None
        
        return TrackingLink(
            link_id=row[0],
            tag=row[1],
            slug=row[2],
            created_at=datetime.fromisoformat(row[3]).replace(tzinfo=UTC),
            deleted_at=deleted_at
        )
    
    def _row_to_event(self, row) -> TrackingEvent:
        return TrackingEvent(
            event_id=row[0],
            link_id=row[1],
            tg_user_id=row[2],
            event_type=row[3],
            first_start=bool(row[4]),
            created_at=datetime.fromisoformat(row[5]).replace(tzinfo=UTC)
        )
