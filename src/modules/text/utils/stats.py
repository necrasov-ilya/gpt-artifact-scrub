from __future__ import annotations

from typing import Mapping


def format_stats(stats: Mapping[str, int]) -> str:
    mapping = {
        "dashes": "тире",
        "quotes": "кавычки",
        "bullets": "маркеры списков",
        "nbsp": "неразрывные пробелы",
        "llm_tokens": "маркеры LLM",
        "llm_cite": "cite",
        "llm_bracket_groups": "скобочные группы",
    }
    parts = [f"{label}: {stats[key]}" for key, label in mapping.items() if stats.get(key)]
    if not parts:
        return "Ничего не пришлось менять — текст уже аккуратный."
    return "Заменил: " + ", ".join(parts) + "."
