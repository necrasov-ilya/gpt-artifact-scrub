import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from src.normalize import NormalizationStage, normalize_text
from src.normalization import default_registry, run_pipeline


def _guarantees(text: str) -> None:
    assert not re.search(r"\bturn\d+(?:search|click|fetch|view|news|image|product|sports|finance|forecast|time|maps|calc|translate|msearch|mclick)\d+\b", text, re.I)
    assert not re.search(r"\bcite\b", text, re.I)


def main():
    cases = [
        (
            "Unicode cleanup baseline",
            "Пример — текста с «ёлочками», ‘кавычками’ и • маркерами.\u00A0\n\t— Пункт 1\n– Пункт 2\n- Пункт 3",
        ),
        (
            "Single token",
            "Это тест turn0search18 и всё.",
        ),
        (
            "Token sequence",
            "Метки: turn0search18 turn0search16 turn3click1 в тексте",
        ),
        (
            "Cite before tokens",
            "(cite turn0search18) cite turn1view2 and text",
        ),
        (
            "Bracketed groups with domain",
            "Ссылки: (bigw.com.au; turn0search21 turn0search16) и [cite turn2fetch3 example.com]",
        ),
        (
            "Mixed braces",
            "Проверка {cite turn10msearch2} и {обычный блок} завершена.",
        ),
        (
            "Empty list items after removal",
            "- cite turn0search1\n-   *   \n- ( )\n- []\n- { }\n- * *   *  ",
        ),
        (
            "Nested bracket group with markers",
            "См. [animals [dot] net] и (cite turn1news2 внутри) конец.",
        ),
        (
            "Non-empty list preserved",
            "- Полезный пункт\n- (*) Всё равно не пусто\n- [сайт] пример",
        ),
    ]

    for title, raw in cases:
        cleaned, stats = normalize_text(raw)
        print(f"=== {title} ===")
        print("RAW:", raw)
        print("CLEANED:", cleaned)
        print("STATS:", stats)
        _guarantees(cleaned)
        assert "()" not in cleaned and "[]" not in cleaned and "{}" not in cleaned
        for line in cleaned.splitlines():
            assert not re.fullmatch(r"[ \t*]*", line), f"Empty line of asterisks: {line!r}"
        for key in ("llm_tokens", "llm_cite", "llm_bracket_groups"):
            assert key in stats

    class UpperCaseStage(NormalizationStage):
        name = "uppercase_test"

        def apply(self, context):
            context.set_text(context.text.upper())

    demo_pipeline = default_registry.create_pipeline()
    assert demo_pipeline.stages, "Default pipeline must include at least one stage"
    result = run_pipeline("Тест cite turn0search1", list(demo_pipeline.stages) + [UpperCaseStage()])
    assert result.text == "ТЕСТ", "Custom stage should run after default pipeline"

if __name__ == "__main__":
    main()
