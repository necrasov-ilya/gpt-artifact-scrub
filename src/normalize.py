import sys
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src.normalization import (
        NormalizationContext,
        NormalizationPipeline,
        NormalizationStage,
        PipelineResult,
        normalize_text,
        register_stage,
        run_pipeline,
        scrub_llm_artifacts,
    )
else:
    from .normalization import (
        NormalizationContext,
        NormalizationPipeline,
        NormalizationStage,
        PipelineResult,
        normalize_text,
        register_stage,
        run_pipeline,
        scrub_llm_artifacts,
    )

__all__ = [
    "NormalizationContext",
    "NormalizationPipeline",
    "NormalizationStage",
    "PipelineResult",
    "normalize_text",
    "register_stage",
    "run_pipeline",
    "scrub_llm_artifacts",
]
