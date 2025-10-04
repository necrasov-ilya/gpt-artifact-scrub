from __future__ import annotations

from . import app, modules
from .modules.text.pipeline import normalization as normalization

# Backwards compatibility aliases
bot = app  # Old import path: src.bot

__all__ = ["app", "bot", "modules", "normalization"]
