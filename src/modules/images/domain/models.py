from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Sequence


@dataclass(frozen=True)
class EmojiGridOption:
    rows: int
    cols: int

    @property
    def tiles(self) -> int:
        return self.rows * self.cols

    def as_label(self) -> str:
        return f"{self.rows}×{self.cols} ({self.tiles})"

    def encode(self) -> str:
        return f"{self.rows}x{self.cols}"

    @staticmethod
    def decode(value: str) -> "EmojiGridOption":
        sanitized = value.lower().replace("×", "x")
        rows_str, cols_str = sanitized.split("x", 1)
        return EmojiGridOption(rows=int(rows_str), cols=int(cols_str))


@dataclass(frozen=True)
class EmojiPackRequest:
    user_id: int
    chat_id: int
    file_path: Path
    image_hash: str
    grid: EmojiGridOption
    padding: int
    file_unique_id: str
    requested_at: datetime


@dataclass(frozen=True)
class EmojiPackResult:
    short_name: str
    link: str
    custom_emoji_ids: Sequence[str]
    fragment_preview_id: str | None = None


@dataclass(frozen=True)
class EmojiQueuedJob:
    request: EmojiPackRequest


@dataclass(frozen=True)
class EmojiJobOutcome:
    request: EmojiPackRequest
    result: EmojiPackResult


@dataclass(frozen=True)
class UserSettings:
    user_id: int
    default_grid: EmojiGridOption
    default_padding: int


@dataclass(frozen=True)
class SuggestedGridPlan:
    options: List[EmojiGridOption]
    fallback: EmojiGridOption


def normalize_grid_string(grid: str) -> str:
    rows, cols = grid.lower().split("x", 1)
    return f"{int(rows)}x{int(cols)}"
