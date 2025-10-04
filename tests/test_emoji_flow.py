from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image

from src.modules.images.domain.models import EmojiGridOption, EmojiPackRequest, EmojiPackResult
from src.modules.images.infrastructure.storage import Storage
from src.modules.images.services.emoji_pack import EmojiPackService
from src.modules.images.services.queue import EmojiProcessingQueue
from src.modules.images.utils.image import compute_image_hash


class FakeTelegramEmojiClient:
    def __init__(self) -> None:
        self.calls = 0

    async def create_or_extend(self, request: EmojiPackRequest, tile_paths) -> EmojiPackResult:  # type: ignore[override]
        self.calls += 1
        # Ensure files exist during processing
        for path in tile_paths:
            assert Path(path).exists()
        return EmojiPackResult(
            short_name="test_by_bot",
            link="https://t.me/addemoji/test_by_bot",
            custom_emoji_ids=[f"id_{self.calls}"],
        )


@pytest.mark.asyncio
async def test_emoji_queue_always_processes_new_requests(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "state.db")
    await storage.initialize()
    client = FakeTelegramEmojiClient()
    service = EmojiPackService(
        storage=storage,
        telegram_client=client,  # type: ignore[arg-type]
        temp_dir=tmp_path,
        tile_size=100,
    )
    queue = EmojiProcessingQueue(service, workers=1)
    await queue.start()

    image_path = tmp_path / "source.png"
    with Image.new("RGBA", (200, 100), (255, 0, 0, 255)) as image:
        image.save(image_path)
    image_bytes = image_path.read_bytes()
    image_hash = compute_image_hash(image_bytes)

    def build_request(path: Path) -> EmojiPackRequest:
        return EmojiPackRequest(
            user_id=1,
            chat_id=1,
            file_path=path,
            image_hash=image_hash,
            grid=EmojiGridOption(rows=1, cols=2),
            padding=2,
            file_unique_id="file123",
            requested_at=datetime.now(UTC),
        )

    request1_path = tmp_path / "req1.png"
    request1_path.write_bytes(image_bytes)
    try:
        future1 = await queue.submit(build_request(request1_path))
        outcome1 = await future1

        request2_path = tmp_path / "req2.png"
        request2_path.write_bytes(image_bytes)
        future2 = await queue.submit(build_request(request2_path))
        outcome2 = await future2

        assert client.calls == 2
        assert outcome1.result.custom_emoji_ids != outcome2.result.custom_emoji_ids
    finally:
        await queue.stop()
