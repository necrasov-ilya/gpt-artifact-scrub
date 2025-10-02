import re
from typing import Tuple, Dict

RE_DASHES = re.compile(r"[\u2012\u2013\u2014\u2015\u2212]")
RE_QUOTES = re.compile(r"[\u00AB\u00BB\u201C\u201D\u201E\u201F\u2039\u203A\u2018\u2019]")
RE_BULLETS = re.compile(r"^[\s\t]*([\u2022\u2023\u25E6\u2043\u2219\-–—])\s+", re.MULTILINE)
RE_NBSP = re.compile(r"\u00A0")

_TYPE_PART = (
  r"(?:search|click|fetch|view|news|image|product|sports|finance|forecast|time|maps|calc|translate|msearch|mclick)"
)
TURN_TOKEN_PATTERN = rf"\bturn\d+{_TYPE_PART}\d+\b"
RE_TURN_TOKEN = re.compile(TURN_TOKEN_PATTERN, re.IGNORECASE)
RE_TURN_SEQ = re.compile(rf"(?:{TURN_TOKEN_PATTERN})(?:\s+(?:{TURN_TOKEN_PATTERN}))*", re.IGNORECASE)
RE_CITE_WORD = re.compile(r"\bcite\b", re.IGNORECASE)
RE_CITE_PLUS_SEQ = re.compile(rf"\bcite\b(?:\s+{TURN_TOKEN_PATTERN})+", re.IGNORECASE)


def _remove_bracketed_groups_with_markers(s: str, stats: Dict[str, int]) -> str:
  """
  Remove entire groups in (), [] or {} if anywhere inside (including nested levels)
  appears the word 'cite' or any LLM turn token. Uses a stack-based scan to support
  nesting and removes the widest enclosing groups that contain markers.
  Updates stats['llm_bracket_groups'] with the number of groups removed.
  """
  pairs = {'(': ')', '[': ']', '{': '}'}
  opens = set(pairs.keys())
  closes = {v: k for k, v in pairs.items()}
  stack: list[dict] = []  
  removable: list[tuple[int, int]] = []

  for i, ch in enumerate(s):
    if ch in opens:
      stack.append({'ch': ch, 'pos': i, 'has_marker': False})
    elif ch in closes:
      if stack and stack[-1]['ch'] == closes[ch]:
        top = stack.pop()
        start = top['pos']
        end = i
        inner = s[start+1:end]
        has_marker = bool(RE_CITE_WORD.search(inner) or RE_TURN_TOKEN.search(inner) or top['has_marker'])
        if has_marker:
          removable.append((start, end))
        if stack:
          stack[-1]['has_marker'] = stack[-1]['has_marker'] or has_marker
      else:
        continue

  if not removable:
    return s

  removable.sort()
  merged: list[tuple[int, int]] = []
  for a, b in removable:
    if not merged or a > merged[-1][1] + 1:
      merged.append((a, b))
    else:
      prev_a, prev_b = merged[-1]
      merged[-1] = (prev_a, max(prev_b, b))

  parts = []
  last = len(s)
  for a, b in reversed(merged):
    parts.append(s[b+1:last])
    parts.append("") 
    last = a
  parts.append(s[0:last])
  new_s = "".join(reversed(parts))
  stats["llm_bracket_groups"] = stats.get("llm_bracket_groups", 0) + len(merged)
  return new_s


def _remove_empty_brackets(s: str) -> str:
  """Remove empty bracket pairs like (), [], {} with only whitespace inside. Repeat until stable."""
  pattern = re.compile(r"\(\s*\)|\[\s*\]|\{\s*\}")
  prev = None
  while prev != s:
    prev = s
    s = pattern.sub("", s)
  return s


def _cleanup_punctuation_and_spaces(s: str) -> str:
  """
  Clean extra whitespace and punctuation artifacts left after removals.
  - Collapse multiple spaces/tabs to single spaces (preserves newlines)
  - Remove spaces before common punctuation , . ; : ) ] }
  - Remove spaces after opening brackets ( ( [ { )
  - Collapse duplicate commas/periods/semicolons/colons
  - Trim spaces at line ends
  """
  # Collapse consecutive spaces/tabs but keep newlines intact
  s = re.sub(r"[ \t]{2,}", " ", s)
  # Remove space before punctuation like ", . ; : ) ] }"
  s = re.sub(r"\s+([,.;:)\]\}])", r"\1", s)
  # Remove space right after opening brackets
  s = re.sub(r"([\(\[\{])\s+", r"\1", s)
  # Collapse duplicate punctuation
  s = re.sub(r"([,.;:])\s*\1+", r"\1", s)
  # Remove punctuation that appears at line start
  s = re.sub(r"(?m)^[\t ]*([,.;:])\s*", "", s)
  # Trim trailing spaces on each line
  s = re.sub(r"(?m)[ \t]+$", "", s)
  # Normalize multiple blank lines to max two
  s = re.sub(r"\n{3,}", "\n\n", s)
  return s


def _drop_empty_lines_and_list_items(s: str) -> str:
  """
  Drop lines or list items that, after scrubbing, consist only of asterisks, spaces,
  or empty brackets. Recognizes common list prefixes (-, *, +, •) and removes the
  entire line if its content is empty by these rules.
  """
  def _is_empty_content(text: str) -> bool:
    t = _remove_empty_brackets(text)
    return re.fullmatch(r"[ \t*]*", t) is not None

  out_lines = []
  for line in s.splitlines():
    raw = line.rstrip()  
    stripped = raw.strip()
    if not stripped:
      out_lines.append("")
      continue
    if re.fullmatch(r"[ \t]*[\-\*\+•][ \t]*", raw):
      continue
    # Detect list prefix
    m = re.match(r"^[ \t]*([\-\*\+•])\s+(.*)$", raw)
    if m:
      content = m.group(2)
      if _is_empty_content(content):
        # drop empty list item
        continue
      # also drop if after cleaning brackets content is empty
      content2 = _remove_empty_brackets(content).strip()
      if not content2:
        continue
      out_lines.append(raw)
      continue
    # Non-list line: drop if empty content by rules
    if _is_empty_content(stripped):
      continue
    # Also drop if becomes empty after removing empty brackets
    if not _remove_empty_brackets(stripped).strip():
      continue
    out_lines.append(raw)

  # Collapse multiple blank lines to a single blank line
  text = "\n".join(out_lines)
  text = re.sub(r"\n{3,}", "\n\n", text)
  return text


def scrub_llm_artifacts(s: str) -> Tuple[str, Dict[str, int]]:
  r"""
  Удаляет служебные маркеры LLM:
    - turn{n}{type}{m} (и их последовательности)
    - cite перед одним/несколькими такими токенами
    - целиком скобочные группы (), [], {} с такими маркерами/"cite" (поддерживает вложенность)
  Возвращает (очищенный_текст, счётчики_удалений).
  """
  stats: Dict[str, int] = {"llm_tokens": 0, "llm_cite": 0, "llm_bracket_groups": 0}

  # NBSP не трогаем здесь, чтобы корректно посчитать их позже в normalize_text

  # Step 1: remove bracketed groups that contain markers or cite
  before = s
  s = _remove_bracketed_groups_with_markers(s, stats)
  # Step 2: remove 'cite' followed by one-or-more tokens (outside brackets)
  s, n = RE_CITE_PLUS_SEQ.subn("", s)
  if n:
    stats["llm_cite"] += n
  # Step 3: remove any remaining standalone or spaced sequences of turn tokens
  s, n = RE_TURN_SEQ.subn("", s)
  if n:
    stats["llm_tokens"] += n
  # Step 4: ensure plain 'cite' not left anywhere
  s, n = RE_CITE_WORD.subn("", s)
  if n:
    stats["llm_cite"] += n
  # Шаг 5: подчистка пробелов и пунктуации вокруг удалений
  s = _cleanup_punctuation_and_spaces(s)
  # Шаг 6: финальный проход на всякий случай
  s = RE_TURN_SEQ.sub("", s)
  s = RE_CITE_WORD.sub("", s)
  # Remove empty bracket pairs that may be left after removals
  s = _remove_empty_brackets(s)
  s = _cleanup_punctuation_and_spaces(s)
  # Finally drop empty lines/list items
  s = _drop_empty_lines_and_list_items(s)
  return s, stats


def normalize_text(s: str) -> Tuple[str, Dict[str, int]]:
  # Посчитаем, что предстоит заменить, на исходном тексте
  stats = {
    "dashes": len(RE_DASHES.findall(s)),
    "quotes": len(RE_QUOTES.findall(s)),
    "bullets": len(RE_BULLETS.findall(s)),
    "nbsp": len(RE_NBSP.findall(s)),
  }

  # Сначала удаляем LLM-артефакты
  s, llm_stats = scrub_llm_artifacts(s)

  # Нормализуем типографику
  s = RE_DASHES.sub("-", s)
  s = RE_QUOTES.sub('"', s)

  def _bullet_repl(_m):
    return "- "

  s = RE_BULLETS.sub(_bullet_repl, s)
  s = RE_NBSP.sub(" ", s)

  # Финальная подчищка
  s = _remove_empty_brackets(s)
  s = _cleanup_punctuation_and_spaces(s)
  s = _drop_empty_lines_and_list_items(s)

  # Добавим счётчики LLM-удалений
  stats.update(llm_stats)
  return s, stats
