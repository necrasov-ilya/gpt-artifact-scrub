from __future__ import annotations

import re

from ..context import NormalizationContext
from ..pipeline import NormalizationStage


class PreflightStatsStage(NormalizationStage):
    name = "preflight_stats"

    RE_DASHES = re.compile(r"[\u2012\u2013\u2014\u2015\u2212]")
    RE_QUOTES = re.compile(r"[\u00AB\u00BB\u201C\u201D\u201E\u201F\u2039\u203A\u2018\u2019]")
    RE_BULLETS = re.compile(r"^[\s\t]*([\u2022\u2023\u25E6\u2043\u2219\-–—])\s+", re.MULTILINE)
    RE_NBSP = re.compile(r"\u00A0")

    def apply(self, context: NormalizationContext) -> None:
        text = context.text
        context.set_stat("dashes", len(self.RE_DASHES.findall(text)))
        context.set_stat("quotes", len(self.RE_QUOTES.findall(text)))
        context.set_stat("bullets", len(self.RE_BULLETS.findall(text)))
        context.set_stat("nbsp", len(self.RE_NBSP.findall(text)))
