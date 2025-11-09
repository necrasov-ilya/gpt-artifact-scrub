from __future__ import annotations

import asyncio
import logging
from typing import Optional, Tuple

from ..domain.models import EmojiJobOutcome, EmojiPackRequest
from .emoji_pack import EmojiPackService

logger = logging.getLogger(__name__)


class EmojiProcessingQueue:
    def __init__(
        self,
        service: EmojiPackService,
        *,
        workers: int = 2,
        job_timeout: float = 120.0,
    ) -> None:
        self._service = service
        self._workers = workers
        self._job_timeout = job_timeout
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
                outcome = await asyncio.wait_for(
                    self._service.process(request),
                    timeout=self._job_timeout,
                )
            except asyncio.TimeoutError:
                exc = RuntimeError(
                    f"Emoji pack processing timed out after {self._job_timeout}s for user {request.user_id}"
                )
                logger.error(
                    "Job timeout: user_id=%s, file=%s, grid=%s",
                    request.user_id,
                    request.file_path,
                    request.grid.encode(),
                    exc_info=True,
                )
                if not future.done():
                    future.set_exception(exc)
            except asyncio.CancelledError:
                logger.warning("Worker cancelled during job processing for user %s", request.user_id)
                raise  # Re-raise to allow clean shutdown
            except Exception as exc:
                logger.exception(
                    "Unexpected error processing emoji pack for user %s: %s",
                    request.user_id,
                    exc,
                )
                if not future.done():
                    future.set_exception(exc)
            else:
                if not future.done():
                    future.set_result(outcome)
            finally:
                self._queue.task_done()
