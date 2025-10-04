from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextCorrectionResult:
    normalized_text: str
    edited_text: str
    stats: dict[str, int]
    summary: str
