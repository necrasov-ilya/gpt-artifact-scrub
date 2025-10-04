from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.modules.images.domain.models import EmojiGridOption, EmojiPackRequest
from src.modules.images.infrastructure.telegram_emoji import TelegramEmojiClient


@pytest.fixture
def telegram_client() -> TelegramEmojiClient:
    bot = MagicMock()
    return TelegramEmojiClient(
        bot=bot,
        bot_username="TestBot",
        fragment_username=None,
        creation_limit=50,
        total_limit=200,
    )


def make_request(rows: int, cols: int, padding: int, *, requested_at: datetime | None = None) -> EmojiPackRequest:
    ts = requested_at or datetime.now(UTC)
    file_path = Path(f"dummy_{uuid4().hex}.png")
    return EmojiPackRequest(
        user_id=123,
        chat_id=456,
        file_path=file_path,
        image_hash="abcdef1234567890",
        grid=EmojiGridOption(rows=rows, cols=cols),
        padding=padding,
        file_unique_id="unique",
        requested_at=ts,
    )


def test_build_short_name_is_deterministic(telegram_client: TelegramEmojiClient) -> None:
    request = make_request(2, 3, 1)
    slug1 = telegram_client._build_short_name(request, "TestBot")
    slug2 = telegram_client._build_short_name(request, "TestBot")
    assert slug1 == slug2
    assert slug1.endswith("_by_testbot")
    assert len(slug1) <= 64


def test_build_short_name_varies_with_layout(telegram_client: TelegramEmojiClient) -> None:
    base_time = datetime(2025, 1, 1, 0, 0, tzinfo=UTC)
    base_request = make_request(2, 3, 1, requested_at=base_time)
    alt_grid = make_request(3, 2, 1, requested_at=base_time)
    alt_padding = make_request(2, 3, 2, requested_at=base_time)

    base_slug = telegram_client._build_short_name(base_request, "TestBot")
    grid_slug = telegram_client._build_short_name(alt_grid, "TestBot")
    padding_slug = telegram_client._build_short_name(alt_padding, "TestBot")

    assert base_slug != grid_slug
    assert base_slug != padding_slug
    assert grid_slug != padding_slug


def test_build_short_name_changes_on_new_upload(telegram_client: TelegramEmojiClient) -> None:
    first = make_request(2, 3, 1)
    second = make_request(2, 3, 1)

    slug1 = telegram_client._build_short_name(first, "TestBot")
    slug2 = telegram_client._build_short_name(second, "TestBot")

    assert slug1 != slug2
