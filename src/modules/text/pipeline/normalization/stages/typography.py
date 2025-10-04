from __future__ import annotations

import re

from ..context import NormalizationContext
from ..pipeline import NormalizationStage
from ..text_utils import cleanup_punctuation_and_spaces, drop_empty_lines_and_list_items, remove_empty_brackets


class TypographyStage(NormalizationStage):
    name = "typography"

    RE_DASHES = re.compile(r"[\u2012\u2013\u2014\u2015\u2212]")
    RE_QUOTES = re.compile(r"[\u00AB\u00BB\u201C\u201D\u201E\u201F\u2039\u203A\u2018\u2019]")
    RE_BULLETS = re.compile(r"^[\s\t]*([\u2022\u2023\u25E6\u2043\u2219\-–—])\s+", re.MULTILINE)
    RE_NBSP = re.compile(r"\u00A0")

    def apply(self, context: NormalizationContext) -> None:
        text = context.text
        text = self.RE_DASHES.sub("-", text)
        text = self.RE_QUOTES.sub('"', text)
        text = self.RE_BULLETS.sub(self._bullet_repl, text)
        text = self.RE_NBSP.sub(" ", text)
        text = remove_empty_brackets(text)
        text = cleanup_punctuation_and_spaces(text)
        text = drop_empty_lines_and_list_items(text)
        context.set_text(text)

    @staticmethod
    def _bullet_repl(_match: re.Match[str]) -> str:
        return "- "
