from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from dataclasses import dataclass


@dataclass
class _AntiSpamState:
    busy: bool
    last_action: float


class AntiSpamGuard:
    def __init__(self, cooldown_seconds: float = 2.0, max_entries: int = 10_000) -> None:
        self._cooldown = cooldown_seconds
        self._max_entries = max_entries
        self._states: OrderedDict[int, _AntiSpamState] = OrderedDict()
        self._lock = asyncio.Lock()

    async def try_acquire(self, user_id: int) -> bool:
        now = time.monotonic()
        async with self._lock:
            # Evict oldest entry if dict is full (LRU)
            if len(self._states) >= self._max_entries and user_id not in self._states:
                self._states.popitem(last=False)
            
            state = self._states.get(user_id)
            if state:
                if state.busy or now - state.last_action < self._cooldown:
                    state.last_action = now
                    self._states[user_id] = state
                    self._states.move_to_end(user_id)  # Mark as recently used
                    return False
            self._states[user_id] = _AntiSpamState(busy=True, last_action=now)
            self._states.move_to_end(user_id)  # Mark as recently used
            return True

    async def release(self, user_id: int) -> None:
        now = time.monotonic()
        async with self._lock:
            self._states[user_id] = _AntiSpamState(busy=False, last_action=now)
            self._states.move_to_end(user_id)  # Mark as recently used

    async def reset(self, user_id: int) -> None:
        async with self._lock:
            self._states.pop(user_id, None)
