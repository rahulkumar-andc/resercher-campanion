"""
Context metrics stub — lightweight token/paper estimates for logging.
Not a real Mamba SSM or Transformer attention engine.
"""

from typing import Dict, List, Any
from dataclasses import dataclass, field


@dataclass
class ContextScanResult:
    token_count: int
    processing_time_ms: float = 0.0
    notes: str = "local_token_estimate"


@dataclass
class CitationLinkResult:
    paper_count: int
    grounded_citations: List[str] = field(default_factory=list)


class ContextMetricsStub:
    """Summarizes context size and citation count for supervisor logs."""

    def summarize(self, raw_code_text: List[str], arxiv_papers: List[Any]) -> Dict[str, Any]:
        blocks = [str(b) for b in (raw_code_text or [])]
        token_estimate = sum(len(block.split()) for block in blocks)
        titles = []
        for p in (arxiv_papers or [])[:5]:
            title = getattr(p, "title", None) or (p.get("title") if isinstance(p, dict) else None)
            if title:
                titles.append(title)
        return {
            "token_estimate": token_estimate,
            "paper_count": len(arxiv_papers or []),
            "sample_titles": titles,
            "hybrid_status": "CONTEXT_METRICS_STUB",
        }


# Back-compat alias — callers expecting the old name get the stub
HybridNeuralEngine = ContextMetricsStub
