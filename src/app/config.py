from __future__ import annotations

import re

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    bot_username: Optional[str] = Field(None, alias="TELEGRAM_BOT_USERNAME")
    fragment_username: Optional[str] = Field(None, alias="FRAGMENT_USERNAME")

    storage_path: Path = Field(Path("./data/state.db"), alias="STORAGE_PATH")
    temp_dir: Path = Field(Path("./data/tmp"), alias="TMP_DIR")
    temp_retention_minutes: int = Field(15, ge=1, le=120, alias="TMP_RETENTION_MINUTES")

    emoji_padding_default: int = Field(2, ge=0, le=5, alias="EMOJI_PADDING_DEFAULT")
    emoji_grid_default: str = Field("2x2", alias="EMOJI_GRID_DEFAULT")
    emoji_queue_workers: int = Field(2, ge=1, le=8, alias="EMOJI_QUEUE_WORKERS")
    emoji_max_tiles: int = Field(200, ge=1, alias="EMOJI_MAX_TILES")
    emoji_creation_limit: int = Field(50, ge=1, alias="EMOJI_CREATION_LIMIT")
    emoji_tile_size: int = Field(100, ge=64, le=512, alias="EMOJI_TILE_SIZE")
    emoji_grid_tile_cap: int | None = Field(
        None,
        ge=1,
        alias="EMOJI_GRID_TILE_CAP",
        description="Максимальное количество тайлов в опциях сетки (если указано)",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field("INFO", alias="LOG_LEVEL")
    logs_page_size: int = Field(20, ge=1, alias="LOGS_PAGE_SIZE")

    # Keep the raw env value as a string to avoid dotenv provider attempting JSON decode
    admin_user_ids_raw: Optional[str] = Field(None, alias="ADMIN_USER_IDS")

    @property
    def admin_user_ids(self) -> set[int]:
        raw = self.admin_user_ids_raw
        if raw is None or raw == "":
            return set()
        # Support comma/space/semicolon separation
        tokens = [token for token in re.split(r"[\s,;]+", raw.strip()) if token]
        ids: set[int] = set()
        for token in tokens:
            try:
                ids.add(int(token))
            except ValueError:
                # ignore non-integer tokens
                continue
        return ids

    def ensure_dirs(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
