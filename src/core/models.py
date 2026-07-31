import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum


class PipelineStage(Enum):
    IDLE = "IDLE"
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


@dataclass
class ResearchGroundingResult:
    arxiv_papers: List[CitationItem] = field(default_factory=list)
    cs_context: List[str] = field(default_factory=list)
    electronics_context: List[str] = field(default_factory=list)
    literature_summary: str = ""
    novelty_gaps: List[str] = field(default_factory=list)


@dataclass
class SynthesisResult:
    unified_context: str = ""
    outline: List[Dict[str, Any]] = field(default_factory=list)
    citations: List[CitationItem] = field(default_factory=list)
    critic_score: float = 0.0
    critic_feedback: List[str] = field(default_factory=list)


@dataclass
class QualityAuditResult:
    plagiarism_percentage: float = 0.0
    ai_writing_percentage: float = 0.0
    reviewer_answers: Dict[str, str] = field(default_factory=dict)
    grammar_spelling_issues: List[str] = field(default_factory=list)
    format_issues: List[str] = field(default_factory=list)
    is_approved: bool = True
    feedback_reroute_target: Optional[str] = None
    rejection_reasons: List[str] = field(default_factory=list)


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

