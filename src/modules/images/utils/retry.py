from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def retry_async(
    func: Callable[[], Awaitable[T]],
    *,
    attempts: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    factor: float = 2.0,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    delay = initial_delay
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await func()
        except retry_exceptions as exc:  # type: ignore[misc]
            last_exc = exc
            if attempt == attempts:
                raise
            await asyncio.sleep(delay)
            delay = min(delay * factor, max_delay)
    assert last_exc is not None
    raise last_exc
