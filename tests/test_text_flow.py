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


@pytest.mark.asyncio
async def test_removes_reference_style_links_without_definitions() -> None:
    """Converts malformed reference links: domains → URLs, plain text → as-is."""
    service = TextNormalizationService()
    
    # Domains with and without punctuation
    result = await service.process("Проверка [ssi.inc][1] и [(example.com)][2] и [https://github.com/user][3]")
    assert "[1]" not in result.normalized_text and "[2]" not in result.normalized_text and "[3]" not in result.normalized_text
    assert "https://ssi.inc" in result.normalized_text
    assert "https://example.com" in result.normalized_text
    assert "https://github.com/user" in result.normalized_text
    
    # Plain text extraction
    result = await service.process("Обычный [текст][99] без URL")
    assert "[99]" not in result.normalized_text
    assert "текст" in result.normalized_text
    assert result.stats.get("reference_links", 0) >= 1


@pytest.mark.asyncio
async def test_preserves_reference_links_with_definitions() -> None:
    """Correctly formatted reference links with definitions should be preserved."""
    service = TextNormalizationService()
    text = """Текст с [правильной ссылкой][1] и [неправильной][2].

[1]: https://example.com
"""
    result = await service.process(text)
    # [1] has definition → preserve, [2] has no definition → convert
    assert "[правильной ссылкой][1]" in result.normalized_text
    assert "[2]" not in result.normalized_text
    assert result.stats.get("reference_links", 0) >= 1

