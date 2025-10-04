from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    bot_username: Optional[str] = Field(None, alias="TELEGRAM_BOT_USERNAME")
    fragment_username: Optional[str] = Field(None, alias="FRAGMENT_USERNAME")

    openai_api_key: Optional[str] = Field(None, alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o-mini", alias="OPENAI_MODEL")
    openai_temperature: float = Field(0.2, ge=0.0, le=1.0, alias="OPENAI_TEMPERATURE")

    storage_path: Path = Field(Path("./data/state.db"), alias="STORAGE_PATH")
    temp_dir: Path = Field(Path("./data/tmp"), alias="TMP_DIR")
    temp_retention_minutes: int = Field(15, ge=1, le=120, alias="TMP_RETENTION_MINUTES")

    emoji_padding_default: int = Field(2, ge=0, le=5, alias="EMOJI_PADDING_DEFAULT")
    emoji_grid_default: str = Field("2x2", alias="EMOJI_GRID_DEFAULT")
    emoji_queue_workers: int = Field(2, ge=1, le=8, alias="EMOJI_QUEUE_WORKERS")
    emoji_max_tiles: int = Field(200, ge=1, alias="EMOJI_MAX_TILES")
    emoji_creation_limit: int = Field(50, ge=1, alias="EMOJI_CREATION_LIMIT")
    emoji_tile_size: int = Field(100, ge=64, le=512, alias="EMOJI_TILE_SIZE")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field("INFO", alias="LOG_LEVEL")

    def ensure_dirs(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
