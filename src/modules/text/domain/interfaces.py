from __future__ import annotations

from typing import Protocol


class TextEditorLLM(Protocol):
    async def edit_text(self, *, original: str, normalized: str) -> str:
        """Return the edited text keeping facts intact."""
