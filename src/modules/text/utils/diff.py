from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable


@dataclass(frozen=True)
class DiffStats:
    inserted: int
    deleted: int
    replaced: int

    def to_summary(self) -> str:
        parts: list[str] = []
        if self.replaced:
            parts.append(f"обновлено {self.replaced} фрагм.")
        if self.inserted:
            parts.append(f"добавлено {self.inserted}")
        if self.deleted:
            parts.append(f"удалено {self.deleted}")
        return ", ".join(parts) if parts else "без изменений"


def _count_words(chunks: Iterable[str]) -> int:
    return sum(1 for chunk in chunks if chunk)


def word_diff_summary(baseline: str, edited: str) -> DiffStats:
    base_words = baseline.split()
    edited_words = edited.split()
    matcher = SequenceMatcher(None, base_words, edited_words)
    inserted = deleted = replaced = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "replace":
            replaced += max(i2 - i1, j2 - j1)
        elif tag == "insert":
            inserted += j2 - j1
        elif tag == "delete":
            deleted += i2 - i1
    return DiffStats(inserted=inserted, deleted=deleted, replaced=replaced)
