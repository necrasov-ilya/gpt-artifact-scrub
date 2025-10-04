from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .context import NormalizationContext


@dataclass
class PipelineResult:
    text: str
    stats: dict[str, int]
    context: NormalizationContext


class NormalizationStage:
    name: str

    def apply(self, context: NormalizationContext) -> None:
        raise NotImplementedError


class NormalizationPipeline:
    def __init__(self, stages: Sequence[NormalizationStage]):
        self._stages: List[NormalizationStage] = list(stages)

    @property
    def stages(self) -> Sequence[NormalizationStage]:
        return tuple(self._stages)

    def run(self, text: str, *, context: NormalizationContext | None = None) -> PipelineResult:
        ctx = context or NormalizationContext(text=text)
        ctx.original_text = text
        ctx.set_text(text)
        for stage in self._stages:
            stage.apply(ctx)
        return PipelineResult(text=ctx.text, stats=dict(ctx.stats), context=ctx)

    def replace(self, stages: Iterable[NormalizationStage]) -> "NormalizationPipeline":
        return NormalizationPipeline(stages=list(stages))
