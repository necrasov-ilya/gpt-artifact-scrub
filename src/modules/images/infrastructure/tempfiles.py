from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import uuid4

import aiofiles


class TempFileManager:
    def __init__(self, base_dir: Path, *, retention_minutes: int) -> None:
        self._base_dir = base_dir
        self._retention = timedelta(minutes=retention_minutes)
        self._cleanup_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._base_dir.mkdir(parents=True, exist_ok=True)

    async def start(self) -> None:
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None

    async def write_bytes(self, data: bytes, suffix: str = ".bin") -> Path:
        if not suffix.startswith("."):
            suffix = f".{suffix}"
        filename = f"tmp_{uuid4().hex}{suffix}"
        path = self._base_dir / filename
        async with aiofiles.open(path, "wb") as f:
            await f.write(data)
        return path

    async def _cleanup_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(60)
                await self.cleanup()
        except asyncio.CancelledError:
            pass

    async def cleanup(self) -> None:
        cutoff = datetime.utcnow() - self._retention
        async with self._lock:
            for path in self._base_dir.glob("tmp_*"):
                try:
                    stat = await asyncio.to_thread(path.stat)
                except FileNotFoundError:
                    continue
                mtime = datetime.utcfromtimestamp(stat.st_mtime)
                if mtime < cutoff:
                    await asyncio.to_thread(path.unlink)
