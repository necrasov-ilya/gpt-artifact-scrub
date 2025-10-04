from __future__ import annotations

import re
import unicodedata

SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(value: str, *, max_length: int = 32) -> str:
    if not value:
        return "user"
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = SLUG_PATTERN.sub("-", value).strip("-")
    value = value or "user"
    return value[:max_length]
