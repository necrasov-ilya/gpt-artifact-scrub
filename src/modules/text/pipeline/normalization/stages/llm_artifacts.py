from __future__ import annotations

import re
from typing import Dict, List, Tuple

from ..context import NormalizationContext
from ..pipeline import NormalizationStage
from ..text_utils import cleanup_punctuation_and_spaces, drop_empty_lines_and_list_items, remove_empty_brackets


class LLMArtifactsStage(NormalizationStage):
    name = "llm_artifacts"

    _TYPE_PART = (
        r"(?:search|click|fetch|view|news|image|product|sports|finance|forecast|time|maps|calc|translate|msearch|mclick)"
    )
    TURN_TOKEN_PATTERN = rf"\bturn\d+{_TYPE_PART}\d+\b"
    RE_TURN_TOKEN = re.compile(TURN_TOKEN_PATTERN, re.IGNORECASE)
    RE_TURN_SEQ = re.compile(rf"(?:{TURN_TOKEN_PATTERN})(?:\s+(?:{TURN_TOKEN_PATTERN}))*", re.IGNORECASE)
    RE_CITE_PLUS_SEQ = re.compile(rf"\bcite\b(?:\s+{TURN_TOKEN_PATTERN})+", re.IGNORECASE)

    def apply(self, context: NormalizationContext) -> None:
        text = context.text
        stats = {"llm_tokens": 0, "llm_cite": 0, "llm_bracket_groups": 0}
        for key, value in stats.items():
            if key not in context.stats:
                context.set_stat(key, value)
        
        # Remove bracketed groups containing markers
        text = self._remove_bracketed_groups_with_markers(text, stats)
        
        # Remove "cite" followed by turn tokens (e.g., "cite turn0search1")
        text, n = self.RE_CITE_PLUS_SEQ.subn("", text)
        if n:
            stats["llm_cite"] += n
        
        # Remove standalone turn token sequences
        text, n = self.RE_TURN_SEQ.subn("", text)
        if n:
            stats["llm_tokens"] += n
        
        # Clean up spacing and punctuation
        text = cleanup_punctuation_and_spaces(text)
        
        # Second pass to catch any remaining turn tokens after cleanup
        text = self.RE_TURN_SEQ.sub("", text)
        
        # Remove empty brackets and clean up
        text = remove_empty_brackets(text)
        text = cleanup_punctuation_and_spaces(text)
        text = drop_empty_lines_and_list_items(text)
        
        context.set_text(text)
        for key, value in stats.items():
            if value:
                context.add_stat(key, value)

    @staticmethod
    def _remove_bracketed_groups_with_markers(s: str, stats: Dict[str, int]) -> str:
        pairs = {"(": ")", "[": "]", "{": "}"}
        opens = set(pairs.keys())
        closes = {v: k for k, v in pairs.items()}
        stack: List[dict] = []
        removable: List[Tuple[int, int]] = []

        for i, ch in enumerate(s):
            if ch in opens:
                stack.append({"ch": ch, "pos": i, "has_marker": False})
            elif ch in closes:
                if stack and stack[-1]["ch"] == closes[ch]:
                    top = stack.pop()
                    start = top["pos"]
                    end = i
                    inner = s[start + 1 : end]
                    # Check if inner content has "cite" followed by turn tokens, or just turn tokens
                    has_marker = bool(
                        LLMArtifactsStage.RE_CITE_PLUS_SEQ.search(inner)
                        or LLMArtifactsStage.RE_TURN_TOKEN.search(inner)
                        or top["has_marker"]
                    )
                    if has_marker:
                        removable.append((start, end))
                    if stack:
                        stack[-1]["has_marker"] = stack[-1]["has_marker"] or has_marker

        if not removable:
            return s

        removable.sort()
        merged: List[Tuple[int, int]] = []
        for a, b in removable:
            if not merged or a > merged[-1][1] + 1:
                merged.append((a, b))
            else:
                prev_a, prev_b = merged[-1]
                merged[-1] = (prev_a, max(prev_b, b))

        parts = []
        last = len(s)
        for a, b in reversed(merged):
            parts.append(s[b + 1 : last])
            parts.append("")
            last = a
        parts.append(s[0:last])
        stats["llm_bracket_groups"] = stats.get("llm_bracket_groups", 0) + len(merged)
        return "".join(reversed(parts))
