from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, MutableMapping


@dataclass
class NormalizationContext:
    text: str
    stats: MutableMapping[str, int] = field(default_factory=dict)
    metadata: MutableMapping[str, Any] = field(default_factory=dict)
    original_text: str = field(init=False)

    def __post_init__(self) -> None:
        self.original_text = self.text

    def set_text(self, value: str) -> None:
        self.text = value

    def add_stat(self, key: str, value: int) -> None:
        self.stats[key] = self.stats.get(key, 0) + value

    def set_stat(self, key: str, value: int) -> None:
        self.stats[key] = value

    def get_stat(self, key: str, default: int = 0) -> int:
        return int(self.stats.get(key, default))
