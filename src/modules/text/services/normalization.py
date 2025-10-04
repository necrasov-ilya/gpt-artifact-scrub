from __future__ import annotations

import logging

from ..pipeline.normalization import normalize_text

from ..domain.interfaces import TextEditorLLM
from ..domain.models import TextCorrectionResult
from ..utils.diff import word_diff_summary

logger = logging.getLogger(__name__)


class IdentityTextEditor(TextEditorLLM):
    """Fallback editor that returns normalized text without LLM calls."""

    async def edit_text(self, *, original: str, normalized: str) -> str:  # noqa: D401
        return normalized


class TextNormalizationService:
    def __init__(self, llm: TextEditorLLM) -> None:
        self._llm = llm

    async def process(self, text: str) -> TextCorrectionResult:
        normalized_text, stats = normalize_text(text)
        try:
            edited_text = await self._llm.edit_text(original=text, normalized=normalized_text)
        except Exception:
            logger.exception("LLM editing failed; falling back to normalized text")
            edited_text = normalized_text

        if not edited_text.strip():
            edited_text = normalized_text

        diff = word_diff_summary(normalized_text, edited_text)
        diff_summary = diff.to_summary()
        has_normalization_changes = any(value for value in stats.values())
        if diff_summary == "без изменений":
            if has_normalization_changes:
                summary = "Подчистил форматирование и маркеры — смысл уже был в порядке."
            else:
                summary = "Без заметных правок — текст уже аккуратный."
        else:
            summary = diff_summary[0].upper() + diff_summary[1:] if diff_summary else diff_summary

        return TextCorrectionResult(
            normalized_text=normalized_text,
            edited_text=edited_text,
            stats=stats,
            summary=summary,
        )