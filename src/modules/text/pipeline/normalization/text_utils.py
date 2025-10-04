from __future__ import annotations

import re

RE_EMPTY_BRACKETS = re.compile(r"\(\s*\)|\[\s*\]|\{\s*\}")


def remove_empty_brackets(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = RE_EMPTY_BRACKETS.sub("", text)
    return text


def cleanup_punctuation_and_spaces(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\s+([,.;:)\]\}])", r"\1", text)
    text = re.sub(r"([\(\[\{])\s+", r"\1", text)
    text = re.sub(r"([,.;:])\s*\1+", r"\1", text)
    text = re.sub(r"(?m)^[\t ]*([,.;:])\s*", "", text)
    text = re.sub(r"(?m)[ \t]+$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def drop_empty_lines_and_list_items(text: str) -> str:
    def _is_empty_content(value: str) -> bool:
        cleaned = remove_empty_brackets(value)
        return re.fullmatch(r"[ \t*]*", cleaned) is not None

    lines_out = []
    for line in text.splitlines():
        raw = line.rstrip()
        stripped = raw.strip()
        if not stripped:
            lines_out.append("")
            continue
        if re.fullmatch(r"[ \t]*[\-\*\+•][ \t]*", raw):
            continue
        match = re.match(r"^[ \t]*([\-\*\+•])\s+(.*)$", raw)
        if match:
            content = match.group(2)
            if _is_empty_content(content):
                continue
            if not remove_empty_brackets(content).strip():
                continue
            lines_out.append(raw)
            continue
        if _is_empty_content(stripped):
            continue
        if not remove_empty_brackets(stripped).strip():
            continue
        lines_out.append(raw)

    text = "\n".join(lines_out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text
