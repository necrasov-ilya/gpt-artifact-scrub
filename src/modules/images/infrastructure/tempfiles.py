from __future__ import annotations

import asyncio
import contextlib
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union
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

    async def write_bytes(self, data: bytes, suffix: str = ".bin", *, subdir: Union[str, Path, None] = None) -> Path:
        if not suffix.startswith("."):
            suffix = f".{suffix}"
        filename = f"tmp_{uuid4().hex}{suffix}"
        target_dir = self._base_dir / Path(subdir) if subdir else self._base_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / filename
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
            for path in self._base_dir.iterdir():
                try:
                    stat = await asyncio.to_thread(path.stat)
                except FileNotFoundError:
                    continue
                mtime = datetime.utcfromtimestamp(stat.st_mtime)
                if path.is_dir():
                    if mtime < cutoff:
                        await asyncio.to_thread(shutil.rmtree, path, True)
                elif path.name.startswith("tmp_") and mtime < cutoff:
                    await asyncio.to_thread(path.unlink)
