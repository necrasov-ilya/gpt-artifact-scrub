from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Dict


@dataclass
class _AntiSpamState:
    busy: bool
    last_action: float


class AntiSpamGuard:
    def __init__(self, cooldown_seconds: float = 2.0) -> None:
        self._cooldown = cooldown_seconds
        self._states: Dict[int, _AntiSpamState] = {}
        self._lock = asyncio.Lock()

    async def try_acquire(self, user_id: int) -> bool:
        now = time.monotonic()
        async with self._lock:
            state = self._states.get(user_id)
            if state:
                if state.busy or now - state.last_action < self._cooldown:
                    state.last_action = now
                    self._states[user_id] = state
                    return False
            self._states[user_id] = _AntiSpamState(busy=True, last_action=now)
            return True

    async def release(self, user_id: int) -> None:
        now = time.monotonic()
        async with self._lock:
            self._states[user_id] = _AntiSpamState(busy=False, last_action=now)

    async def reset(self, user_id: int) -> None:
        async with self._lock:
            self._states.pop(user_id, None)
