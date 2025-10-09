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
    service = TextNormalizationService()
    text = "Проверка ссылки [ssi.inc][3] в тексте без определений"
    result = await service.process(text)
    assert "[3]" not in result.normalized_text
    # ssi.inc is a domain, so it should get https:// prefix
    assert "https://ssi.inc" in result.normalized_text
    assert result.stats.get("reference_links", 0) >= 1


@pytest.mark.asyncio
async def test_removes_multiple_reference_links() -> None:
    service = TextNormalizationService()
    text = "Текст с [example.com][1] и [github.com/user][2] без определений"
    result = await service.process(text)
    assert "[1]" not in result.normalized_text
    assert "[2]" not in result.normalized_text
    # Domains should get https:// prefix
    assert "https://example.com" in result.normalized_text
    assert "https://github.com/user" in result.normalized_text
    assert result.stats.get("reference_links", 0) >= 2


@pytest.mark.asyncio
async def test_converts_plain_text_without_url() -> None:
    """Plain text without URL should be extracted without link syntax."""
    service = TextNormalizationService()
    text = "Обычный [текст][1] без URL"
    result = await service.process(text)
    assert "[1]" not in result.normalized_text
    assert result.normalized_text == "Обычный текст без URL"
    assert result.stats.get("reference_links", 0) >= 1


@pytest.mark.asyncio
async def test_preserves_reference_links_with_definitions() -> None:
    service = TextNormalizationService()
    text = """Проверка [ссылки][1] с определением.

[1]: https://example.com
"""
    result = await service.process(text)
    # Should preserve both the link and its definition
    assert "ссылки" in result.normalized_text
    assert result.stats.get("reference_links", 0) == 0


@pytest.mark.asyncio
async def test_removes_reference_link_with_spaces() -> None:
    service = TextNormalizationService()
    text = "Проверка [stackoverflow.com] [1] с пробелами"
    result = await service.process(text)
    assert "[1]" not in result.normalized_text
    # stackoverflow.com is a domain, should get https:// prefix
    assert "https://stackoverflow.com" in result.normalized_text
    assert result.stats.get("reference_links", 0) >= 1


@pytest.mark.asyncio
async def test_handles_mixed_reference_links() -> None:
    service = TextNormalizationService()
    text = """Текст с [example.com][1] и [docs.python.org][2] ссылками.

[2]: https://docs.python.org
"""
    result = await service.process(text)
    # [1] should be converted (no definition), [2] should remain (has definition)
    assert "[1]" not in result.normalized_text
    assert "https://example.com" in result.normalized_text
    # [2] link should be preserved as is
    assert "[docs.python.org][2]" in result.normalized_text
    assert result.stats.get("reference_links", 0) >= 1


@pytest.mark.asyncio
async def test_handles_full_urls_in_reference_links() -> None:
    """Full URLs should be kept as-is (already have protocol)."""
    service = TextNormalizationService()
    text = "См. [https://example.com/docs][1] для деталей"
    result = await service.process(text)
    assert "[1]" not in result.normalized_text
    # URL already has https://, should remain unchanged
    assert "https://example.com/docs" in result.normalized_text
    assert result.stats.get("reference_links", 0) >= 1


@pytest.mark.asyncio
async def test_strips_punctuation_from_reference_link_content() -> None:
    """Content with surrounding punctuation should be cleaned before URL detection."""
    service = TextNormalizationService()
    text = "Ссылка на [(ssi.inc)][3] с лишними скобками"
    result = await service.process(text)
    assert "[3]" not in result.normalized_text
    # Should strip parentheses and add https:// prefix
    assert "https://ssi.inc" in result.normalized_text
    assert result.stats.get("reference_links", 0) >= 1

