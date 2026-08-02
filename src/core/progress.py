"""Stage progress / ETA helpers for the dashboard."""

from typing import Dict, Optional, Tuple
from src.core.models import PipelineStage, PipelineContext

# Approximate seconds per stage by job mode (rough ETA only)
_MODE_STAGE_SECONDS: Dict[str, Dict[str, float]] = {
    "full_paper": {
        "LAYER_0_PROFILING": 15,
        "LAYER_1_INGESTION": 30,
        "LAYER_2_CODE_ANALYSIS": 60,
        "LAYER_3_RESEARCH_GROUNDING": 120,
        "LAYER_4_SYNTHESIS": 40,
        "LAYER_5_OUTPUT_GENERATION": 180,
        "LAYER_4_5_QUALITY_AUDIT": 60,
        "COMPLETED": 0,
        "FAILED": 0,
        "IDLE": 5,
    },
    "literature_review": {
        "LAYER_0_PROFILING": 5,
        "LAYER_1_INGESTION": 15,
        "LAYER_3_RESEARCH_GROUNDING": 90,
        "LAYER_4_SYNTHESIS": 20,
        "LAYER_5_OUTPUT_GENERATION": 60,
        "LAYER_4_5_QUALITY_AUDIT": 30,
        "COMPLETED": 0,
        "FAILED": 0,
        "IDLE": 5,
    },
    "research_only": {
        "LAYER_0_PROFILING": 5,
        "LAYER_1_INGESTION": 10,
        "LAYER_3_RESEARCH_GROUNDING": 90,
        "LAYER_4_SYNTHESIS": 15,
        "LAYER_5_OUTPUT_GENERATION": 40,
        "LAYER_4_5_QUALITY_AUDIT": 20,
        "COMPLETED": 0,
        "FAILED": 0,
        "IDLE": 5,
    },
    "complete_draft": {
        "LAYER_0_PROFILING": 5,
        "LAYER_1_INGESTION": 10,
        "LAYER_3_RESEARCH_GROUNDING": 45,
        "LAYER_4_SYNTHESIS": 15,
        "LAYER_5_OUTPUT_GENERATION": 90,
        "LAYER_4_5_QUALITY_AUDIT": 30,
        "COMPLETED": 0,
        "FAILED": 0,
        "IDLE": 5,
    },
}

_STAGE_ORDER = [
    PipelineStage.IDLE,
    PipelineStage.PROFILING,
    PipelineStage.INGESTION,
    PipelineStage.CODE_ANALYSIS,
    PipelineStage.RESEARCH_GROUNDING,
    PipelineStage.SYNTHESIS,
    PipelineStage.OUTPUT_GENERATION,
    PipelineStage.QUALITY_AUDIT,
    PipelineStage.COMPLETED,
]


def update_progress(ctx: PipelineContext, agent_name: str = "", stage: Optional[PipelineStage] = None) -> None:
    if agent_name:
        ctx.current_agent = agent_name
    if stage is not None:
        ctx.stage = stage

    mode = (ctx.job_mode or "full_paper").lower()
    table = _MODE_STAGE_SECONDS.get(mode, _MODE_STAGE_SECONDS["full_paper"])
    stage_key = ctx.stage.value if ctx.stage else "IDLE"

    # Progress from stage index
    try:
        idx = next(i for i, s in enumerate(_STAGE_ORDER) if s == ctx.stage)
        ctx.progress_pct = round(min(99.0, (idx / max(1, len(_STAGE_ORDER) - 1)) * 100.0), 1)
    except StopIteration:
        ctx.progress_pct = 10.0

    if ctx.stage == PipelineStage.COMPLETED:
        ctx.progress_pct = 100.0
        ctx.eta_seconds = 0
        return
    if ctx.stage == PipelineStage.FAILED:
        ctx.eta_seconds = None
        return

    # Remaining ETA: current stage remainder + later stages in table
    remaining = 0.0
    seen = False
    for s in _STAGE_ORDER:
        key = s.value
        if s == ctx.stage:
            seen = True
            remaining += table.get(key, 30) * 0.5  # assume halfway through current
            continue
        if seen:
            remaining += table.get(key, 0)
    ctx.eta_seconds = round(remaining, 0)


def progress_payload(ctx: PipelineContext) -> Dict:
    return {
        "current_agent": ctx.current_agent or "",
        "stage": ctx.stage.value if ctx.stage else "IDLE",
        "progress_pct": ctx.progress_pct,
        "eta_seconds": ctx.eta_seconds,
        "job_mode": getattr(ctx, "job_mode", "full_paper"),
    }
