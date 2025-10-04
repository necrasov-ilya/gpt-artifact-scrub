from __future__ import annotations

import asyncio
from typing import Optional, Tuple

from ..domain.models import EmojiJobOutcome, EmojiPackRequest
from .emoji_pack import EmojiPackService


class EmojiProcessingQueue:
    def __init__(self, service: EmojiPackService, *, workers: int = 2) -> None:
        self._service = service
        self._workers = workers
        self._queue: asyncio.Queue[Optional[Tuple[EmojiPackRequest, asyncio.Future[EmojiJobOutcome]]]] = (
            asyncio.Queue()
        )
        self._tasks: list[asyncio.Task] = []
        self._stopped = asyncio.Event()

    async def start(self) -> None:
        if self._tasks:
            return
        self._stopped.clear()
        for _ in range(self._workers):
            self._tasks.append(asyncio.create_task(self._worker()))

    async def stop(self) -> None:
        for _ in range(self._workers):
            await self._queue.put(None)
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._stopped.set()

    async def submit(self, request: EmojiPackRequest) -> asyncio.Future[EmojiJobOutcome]:
        future: asyncio.Future[EmojiJobOutcome] = asyncio.get_running_loop().create_future()
        await self._queue.put((request, future))
        return future

    async def _worker(self) -> None:
        while True:
            item = await self._queue.get()
            if item is None:
                self._queue.task_done()
                break
            request, future = item
            try:
                outcome = await self._service.process(request)
            except Exception as exc:  # noqa: BLE001
                if not future.done():
                    future.set_exception(exc)
            else:
                if not future.done():
                    future.set_result(outcome)
            finally:
                self._queue.task_done()
