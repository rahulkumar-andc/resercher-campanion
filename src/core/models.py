import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum


class PipelineStage(Enum):
    IDLE = "IDLE"
    PROFILING = "LAYER_0_PROFILING"
    INGESTION = "LAYER_1_INGESTION"
    CODE_ANALYSIS = "LAYER_2_CODE_ANALYSIS"
    RESEARCH_GROUNDING = "LAYER_3_RESEARCH_GROUNDING"
    SYNTHESIS = "LAYER_4_SYNTHESIS"
    QUALITY_AUDIT = "LAYER_4_5_QUALITY_AUDIT"
    OUTPUT_GENERATION = "LAYER_5_OUTPUT_GENERATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class AgentMessage:
    agent_name: str
    layer: int
    content: str
    timestamp: float = field(default_factory=time.time)
    level: str = "INFO"
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeAnalysisResult:
    function_blocks: List[Dict[str, Any]] = field(default_factory=list)
    algorithms: List[Dict[str, str]] = field(default_factory=list)
    complexities: Dict[str, str] = field(default_factory=dict)
    hardware_mappings: List[Dict[str, str]] = field(default_factory=list)
    bugs_edge_cases: List[Dict[str, str]] = field(default_factory=list)
    total_lines: int = 0
    file_count: int = 0
    language_breakdown: Dict[str, int] = field(default_factory=dict)
    cpu_time_ms: float = 0.0
    peak_memory_mb: float = 0.0
    throughput_ops_sec: float = 0.0



@dataclass
class CitationItem:
    key: str
    title: str
    authors: List[str]
    year: str
    journal_or_arxiv: str
    abstract: str
    url: str
    bibtex: str
    full_text: Optional[str] = None


@dataclass
class ResearchGroundingResult:
    arxiv_papers: List[CitationItem] = field(default_factory=list)
    cs_context: List[str] = field(default_factory=list)
    electronics_context: List[str] = field(default_factory=list)
    faculty_context: List[str] = field(default_factory=list)
    literature_context: List[str] = field(default_factory=list)
    web_context: List[str] = field(default_factory=list)
    literature_summary: str = ""
    novelty_gaps: List[str] = field(default_factory=list)


@dataclass
class SynthesisResult:
    unified_context: str = ""
    outline: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[CitationItem] = field(default_factory=list)
    critic_score: float = 0.0
    critic_feedback: List[str] = field(default_factory=list)
    diagrams: List[str] = field(default_factory=list)


@dataclass
class QualityAuditResult:
    # Compatibility field names. These are local heuristic estimates, not external-service scores.
    plagiarism_percentage: Optional[float] = None
    ai_writing_percentage: Optional[float] = None
    reviewer_answers: Dict[str, str] = field(default_factory=dict)
    grammar_spelling_issues: List[str] = field(default_factory=list)
    format_issues: List[str] = field(default_factory=list)
    is_approved: bool = False
    feedback_reroute_target: Optional[str] = None
    rejection_reasons: List[str] = field(default_factory=list)
    upskill_accuracy_score: Optional[float] = None
    upskill_metrics: Dict[str, float] = field(default_factory=dict)
    qa_method: str = "local_heuristic"
    is_estimate: bool = True
    plagiarism_method: str = "local_ngram_heuristic"
    ai_method: str = "local_style_heuristic"
    fact_check_method: str = "local_reference_context_heuristic"



@dataclass
class OutputResult:
    markdown_manuscript: str = ""
    pdf_path: Optional[str] = None
    pptx_path: Optional[str] = None
    generated_at: float = field(default_factory=time.time)


@dataclass
class PipelineContext:
    job_id: str
    raw_topic: str
    raw_code_paths: List[str] = field(default_factory=list)
    raw_notes_paths: List[str] = field(default_factory=list)
    style_fingerprint: Dict[str, Any] = field(default_factory=dict)
    subtopics: List[str] = field(default_factory=list)

    # Dashboard / job options
    job_mode: str = "full_paper"  # full_paper | literature_review | research_only | complete_draft
    github_url: Optional[str] = None
    writer_mode: str = "multi"  # multi | single
    selected_writers: List[str] = field(default_factory=list)  # e.g. ["Literature Review"]; empty = all / generic
    draft_text: str = ""  # half-written paper for complete_draft
    target_section: Optional[str] = None
    skip_code_analysis: bool = False

    stage: PipelineStage = PipelineStage.IDLE
    code_analysis: CodeAnalysisResult = field(default_factory=CodeAnalysisResult)
    research: ResearchGroundingResult = field(default_factory=ResearchGroundingResult)
    synthesis: SynthesisResult = field(default_factory=SynthesisResult)
    quality_audit: QualityAuditResult = field(default_factory=QualityAuditResult)
    output: OutputResult = field(default_factory=OutputResult)

    logs: List[AgentMessage] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    # Live progress (dashboard)
    current_agent: str = ""
    progress_pct: float = 0.0
    eta_seconds: Optional[float] = None
    work_dir: str = "./output"
