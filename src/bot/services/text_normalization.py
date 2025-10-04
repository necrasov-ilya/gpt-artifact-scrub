from __future__ import annotations

from ...modules.text.pipeline.normalization import normalize_text
from ...modules.text.domain.models import TextCorrectionResult


class TextNormalizationService:
    async def process(self, text: str) -> TextCorrectionResult:
        normalized_text, stats = normalize_text(text)
        if any(stats.values()):
            summary = "Подчистил форматирование и маркеры — смысл уже был в порядке."
        else:
            summary = "Без заметных правок — текст уже аккуратный."

        return TextCorrectionResult(
            normalized_text=normalized_text,
            edited_text=normalized_text,
            stats=stats,
            summary=summary,
        )