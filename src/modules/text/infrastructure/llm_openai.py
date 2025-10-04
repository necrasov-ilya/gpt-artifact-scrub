from __future__ import annotations

import textwrap

from openai import AsyncOpenAI

from ..domain.interfaces import TextEditorLLM


SYSTEM_PROMPT = """You are an expert Russian copy editor. Fix spelling, punctuation, and tone while preserving facts.
Do not invent information. Avoid markdown code fences unless user provided them. Return plain text."""


class OpenAITextEditor(TextEditorLLM):
    def __init__(self, client: AsyncOpenAI, model: str, *, temperature: float = 0.2) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature

    async def edit_text(self, *, original: str, normalized: str) -> str:
        user_prompt = textwrap.dedent(
            f"""
            Отредактируй сообщение на русском языке. Сохрани факты и смысл. Улучши орфографию, пунктуацию и стиль.
            Исходный текст:
            ---
            {original.strip()}
            ---
            Предварительно нормализованный текст:
            ---
            {normalized.strip()}
            ---
            Верни только отредактированный текст без пояснений.
            """
        ).strip()

        response = await self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        choice = response.choices[0]
        content = choice.message.content if choice.message else ""
        return content.strip()
