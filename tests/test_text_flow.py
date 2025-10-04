from __future__ import annotations

import pytest

from src.modules.text.services.normalization import TextNormalizationService


@pytest.mark.asyncio
async def test_text_message_flow_produces_summary() -> None:
    service = TextNormalizationService()
    result = await service.process("пример текста turn0search1")
    assert "turn0search1" not in result.normalized_text
    assert result.edited_text == result.normalized_text
    assert result.summary == "Подчистил форматирование и маркеры — смысл уже был в порядке."
    assert result.stats["llm_tokens"] >= 1


@pytest.mark.asyncio
async def test_summary_for_formatting_only_changes() -> None:
    service = TextNormalizationService()
    result = await service.process("пример — текста")
    assert result.summary == "Подчистил форматирование и маркеры — смысл уже был в порядке."
    assert any(result.stats.values())


@pytest.mark.asyncio
async def test_summary_when_no_changes_needed() -> None:
    service = TextNormalizationService()
    result = await service.process("Уже чистый текст без артефактов")
    assert result.summary == "Без заметных правок — текст уже аккуратный."
    assert not any(result.stats.values())
