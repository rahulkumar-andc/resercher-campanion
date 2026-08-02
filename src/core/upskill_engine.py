"""
Hugging Face–style Upskill evaluator — honest estimates only.
Fails closed when manuscript or traces are missing.
"""

import time
import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from src.core.models import PipelineContext


@dataclass
class AgentTraceEntry:
    agent_name: str
    layer: int
    timestamp: float
    input_summary: str
    output_summary: str
    accuracy_score: Optional[float] = None
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class SkillEvaluationResult:
    job_id: str
    overall_accuracy: Optional[float]
    academic_accuracy: Optional[float]
    citation_grounding: Optional[float]
    structural_coherence: Optional[float]
    reproducibility_score: Optional[float]
    is_passed: bool
    traces_count: int
    is_estimate: bool = True
    method: str = "local_heuristic_aggregate"
    failure_reason: Optional[str] = None


class AgentTraceLogger:
    """Logs execution traces across pipeline agents."""

    def __init__(self, trace_dir: str = "./output/traces"):
        self.trace_dir = trace_dir
        os.makedirs(self.trace_dir, exist_ok=True)
        self.traces: Dict[str, List[AgentTraceEntry]] = {}

    def log_agent_trace(
        self,
        job_id: str,
        agent_name: str,
        layer: int,
        input_summary: str,
        output_summary: str,
        accuracy_score: Optional[float] = None,
        metrics: Optional[Dict[str, float]] = None,
    ) -> AgentTraceEntry:
        if job_id not in self.traces:
            self.traces[job_id] = []

        entry = AgentTraceEntry(
            agent_name=agent_name,
            layer=layer,
            timestamp=time.time(),
            input_summary=(input_summary or "")[:200],
            output_summary=(output_summary or "")[:200],
            accuracy_score=accuracy_score,
            metrics=metrics or {},
        )
        self.traces[job_id].append(entry)
        return entry

    def export_traces(self, job_id: str) -> str:
        filepath = os.path.join(self.trace_dir, f"trace_{job_id}.json")
        entries = [asdict(t) for t in self.traces.get(job_id, [])]
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"job_id": job_id, "traces": entries}, f, indent=2)
        return filepath


class SkillEvaluator:
    """Heuristic academic-dimension scorer — labeled estimate, fail-closed."""

    def evaluate_pipeline(self, ctx: PipelineContext, traces: List[AgentTraceEntry]) -> SkillEvaluationResult:
        manuscript = (ctx.output.markdown_manuscript or "").strip()
        if not manuscript:
            return SkillEvaluationResult(
                job_id=ctx.job_id,
                overall_accuracy=None,
                academic_accuracy=None,
                citation_grounding=None,
                structural_coherence=None,
                reproducibility_score=None,
                is_passed=False,
                traces_count=len(traces),
                is_estimate=True,
                failure_reason="No manuscript to evaluate",
            )
        if not traces:
            return SkillEvaluationResult(
                job_id=ctx.job_id,
                overall_accuracy=None,
                academic_accuracy=None,
                citation_grounding=None,
                structural_coherence=None,
                reproducibility_score=None,
                is_passed=False,
                traces_count=0,
                is_estimate=True,
                failure_reason="No agent traces recorded",
            )

        code_file_count = ctx.code_analysis.file_count if ctx.code_analysis else 0
        arxiv_count = len(ctx.research.arxiv_papers) if ctx.research else 0
        plagiarism = ctx.quality_audit.plagiarism_percentage
        ai_footprint = ctx.quality_audit.ai_writing_percentage

        if plagiarism is None or ai_footprint is None:
            return SkillEvaluationResult(
                job_id=ctx.job_id,
                overall_accuracy=None,
                academic_accuracy=None,
                citation_grounding=None,
                structural_coherence=None,
                reproducibility_score=None,
                is_passed=False,
                traces_count=len(traces),
                is_estimate=True,
                failure_reason="QA scores unavailable (audit incomplete)",
            )

        academic_acc = max(0.0, min(100.0, 100.0 - (plagiarism * 0.4) - (ai_footprint * 0.5)))
        citation_ground = min(100.0, 50.0 + (arxiv_count * 8.0))
        coherence = 90.0 if ctx.synthesis.unified_context and manuscript else 40.0
        reproducibility = min(100.0, 40.0 + (code_file_count * 5.0))

        overall = round(
            (academic_acc * 0.35)
            + (citation_ground * 0.25)
            + (coherence * 0.20)
            + (reproducibility * 0.20),
            2,
        )
        is_passed = (
            overall >= 70.0
            and plagiarism <= 15.0
            and ai_footprint <= 10.0
            and ctx.quality_audit.is_approved
        )

        return SkillEvaluationResult(
            job_id=ctx.job_id,
            overall_accuracy=overall,
            academic_accuracy=round(academic_acc, 2),
            citation_grounding=round(citation_ground, 2),
            structural_coherence=round(coherence, 2),
            reproducibility_score=round(reproducibility, 2),
            is_passed=is_passed,
            traces_count=len(traces),
            is_estimate=True,
            method="local_heuristic_aggregate",
        )
