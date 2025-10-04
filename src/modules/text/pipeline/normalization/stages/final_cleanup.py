from __future__ import annotations

from ..context import NormalizationContext
from ..pipeline import NormalizationStage
from ..text_utils import cleanup_punctuation_and_spaces, drop_empty_lines_and_list_items, remove_empty_brackets


class FinalCleanupStage(NormalizationStage):
    name = "final_cleanup"

    def apply(self, context: NormalizationContext) -> None:
        text = remove_empty_brackets(context.text)
        text = cleanup_punctuation_and_spaces(text)
        text = drop_empty_lines_and_list_items(text)
        context.set_text(text)
