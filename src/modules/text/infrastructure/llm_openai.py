from __future__ import annotations


class OpenAITextEditor:  # pragma: no cover - kept for backward compatibility only
    """Placeholder that signals OpenAI editing has been disabled."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: D401, ANN002, ANN003
        raise RuntimeError("OpenAI-based text editing is disabled in this build.")

    async def edit_text(self, *, original: str, normalized: str) -> str:  # pragma: no cover
        raise RuntimeError("OpenAI-based text editing is disabled in this build.")
