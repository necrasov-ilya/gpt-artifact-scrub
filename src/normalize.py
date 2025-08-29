import re
from typing import Tuple, Dict

RE_DASHES = re.compile(r"[\u2012\u2013\u2014\u2015\u2212]")
RE_QUOTES = re.compile(r"[\u00AB\u00BB\u201C\u201D\u201E\u201F\u2039\u203A\u2018\u2019]")
RE_BULLETS = re.compile(r"^[\s\t]*([\u2022\u2023\u25E6\u2043\u2219\-–—])\s+", re.MULTILINE)
RE_NBSP = re.compile(r"\u00A0")


def normalize_text(s: str) -> Tuple[str, Dict[str, int]]:
  stats = {"dashes": 0, "quotes": 0, "bullets": 0, "nbsp": 0}

  stats["dashes"] = len(RE_DASHES.findall(s))
  stats["quotes"] = len(RE_QUOTES.findall(s))
  stats["bullets"] = len(RE_BULLETS.findall(s))
  stats["nbsp"] = len(RE_NBSP.findall(s))

  s = RE_DASHES.sub("-", s)
  s = RE_QUOTES.sub('"', s)

  def _bullet_repl(_m):
    return "- "

  s = RE_BULLETS.sub(_bullet_repl, s)
  s = RE_NBSP.sub(" ", s)

  return s, stats
