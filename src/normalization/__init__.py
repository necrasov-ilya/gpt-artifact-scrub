from __future__ import annotations

from typing import Dict, Iterable, Optional, Sequence

from .context import NormalizationContext
from .pipeline import NormalizationPipeline, NormalizationStage, PipelineResult
from .registry import default_registry, register_stage
from .stages.final_cleanup import FinalCleanupStage
from .stages.llm_artifacts import LLMArtifactsStage
from .stages.preflight import PreflightStatsStage
from .stages.typography import TypographyStage


def _register_builtin_stages() -> None:
    names = set(default_registry.list_stage_names())
    if "preflight_stats" not in names:
        register_stage(PreflightStatsStage, name=PreflightStatsStage.name)
    if "llm_artifacts" not in names:
        register_stage(LLMArtifactsStage, name=LLMArtifactsStage.name)
    if "typography" not in names:
        register_stage(TypographyStage, name=TypographyStage.name)
    if "final_cleanup" not in names:
        register_stage(FinalCleanupStage, name=FinalCleanupStage.name)


_register_builtin_stages()


class PipelineBuilder:
    def __init__(self, registry=default_registry) -> None:
        self._registry = registry

    def build(self) -> NormalizationPipeline:
        return self._registry.create_pipeline()

    def with_stages(self, stages: Iterable[NormalizationStage]) -> NormalizationPipeline:
        return self._registry.create_pipeline(overrides=list(stages))


_PIPELINE_CACHE: tuple[int, NormalizationPipeline] | None = None


def _get_default_pipeline() -> NormalizationPipeline:
    global _PIPELINE_CACHE
    version = default_registry.version
    if _PIPELINE_CACHE is None or _PIPELINE_CACHE[0] != version:
        pipeline = default_registry.create_pipeline()
        _PIPELINE_CACHE = (version, pipeline)
    return _PIPELINE_CACHE[1]


def normalize_text(text: str, *, pipeline: Optional[NormalizationPipeline] = None) -> tuple[str, Dict[str, int]]:
    pipe = pipeline or _get_default_pipeline()
    result = pipe.run(text)
    return result.text, result.stats


def run_pipeline(text: str, stages: Sequence[NormalizationStage]) -> PipelineResult:
    pipeline = NormalizationPipeline(stages)
    return pipeline.run(text)


def scrub_llm_artifacts(text: str) -> tuple[str, Dict[str, int]]:
    context = NormalizationContext(text)
    stage = LLMArtifactsStage()
    stage.apply(context)
    stats = {key: context.stats.get(key, 0) for key in ("llm_tokens", "llm_cite", "llm_bracket_groups")}
    return context.text, stats


__all__ = [
    "NormalizationContext",
    "NormalizationPipeline",
    "NormalizationStage",
    "PipelineResult",
    "PipelineBuilder",
    "default_registry",
    "register_stage",
    "normalize_text",
    "run_pipeline",
    "scrub_llm_artifacts",
]
