import time
import sqlite3
import concurrent.futures
from typing import Optional, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from src.core.database import DatabaseEngine
from src.core.event_bus import SupervisorBus
from src.core.models import PipelineContext, PipelineStage
from src.agents.layer0_profiler import RuntimeProfilerAgent
from src.agents.layer1_input import CodeIngestor, DataIngestor, StyleAgent, QueryParser, GitIngestor
from src.agents.layer2_code import CodeBreaker, AlgoDetector, ComplexityAnalyzer, HWMapper, BugEdgeCase
from src.agents.layer3_research import ResearchOrchestrator, FacultyProfileAgent
from src.agents.layer4_synthesis import Connector, OutlineBuilder, CitationAgent, CriticAgent
from src.agents.layer4_5_qa import (
    PlagiarismCheckerAgent,
    PlagiarismRemediatorAgent,
    AIPercentageAuditorAgent,
    PeerReviewerAgent,
    FormatQualityAuditorAgent,
    FactCheckerAgent,
)
from src.core.upskill_engine import AgentTraceLogger, SkillEvaluator
from src.core.hybrid_engine import ContextMetricsStub
from src.core.progress import update_progress
from src.agents.layer5_output import WriterAgent, PDFAgent, PPTAgent, DataVizAgent

MAX_QA_RETRIES = 2


class ResearchState(TypedDict):
    ctx: PipelineContext
    retry_count: int
    output_dir: str
    error_flag: bool


class SupervisorAgent:
    """Layer 6 Central Orchestrator powered by LangGraph."""

    def __init__(
        self,
        bus: Optional[SupervisorBus] = None,
        database: Optional[DatabaseEngine] = None,
        checkpoint_path: str = "checkpoints.sqlite",
    ):
        self.bus = bus or SupervisorBus()
        self.db = database or DatabaseEngine()
        self.checkpoint_path = checkpoint_path
        self.trace_logger = AgentTraceLogger()
        self.skill_evaluator = SkillEvaluator()
        self.context_metrics = ContextMetricsStub()

        self.profiler_agent = RuntimeProfilerAgent(self.bus)

        self.git_ingestor = GitIngestor(self.bus)
        self.code_ingestor = CodeIngestor(self.bus)
        self.data_ingestor = DataIngestor(self.bus)
        self.style_agent = StyleAgent(self.bus)
        self.query_parser = QueryParser(self.bus)

        self.code_breaker = CodeBreaker(self.bus)
        self.algo_detector = AlgoDetector(self.bus)
        self.complexity_analyzer = ComplexityAnalyzer(self.bus)
        self.hw_mapper = HWMapper(self.bus)
        self.bug_edge_case = BugEdgeCase(self.bus)

        self.research_orchestrator = ResearchOrchestrator(self.bus)
        self.faculty_agent = FacultyProfileAgent(self.bus)

        self.connector = Connector(self.bus)
        self.outline_builder = OutlineBuilder(self.bus)
        self.citation_agent = CitationAgent(self.bus)
        self.critic_agent = CriticAgent(self.bus)

        self.plagiarism_checker = PlagiarismCheckerAgent(self.bus, max_threshold=15.0)
        self.plagiarism_remediator = PlagiarismRemediatorAgent(self.bus)
        self.ai_percentage_auditor = AIPercentageAuditorAgent(self.bus, max_ai_threshold=10.0)
        self.peer_reviewer = PeerReviewerAgent(self.bus)
        self.format_quality_auditor = FormatQualityAuditorAgent(self.bus)
        self.fact_checker = FactCheckerAgent(self.bus)

        self.writer_agent = WriterAgent(self.bus)
        self.pdf_agent = PDFAgent(self.bus)
        self.ppt_agent = PPTAgent(self.bus)
        self.dataviz_agent = DataVizAgent(self.bus)

    def _trace(self, ctx: PipelineContext, agent_name: str, layer: int, inp: str, out: str):
        self.trace_logger.log_agent_trace(ctx.job_id, agent_name, layer, inp, out)
        update_progress(ctx, agent_name=agent_name)

    def _save_job(self, ctx: PipelineContext) -> None:
        try:
            self.db.save_job(ctx)
        except Exception as exc:
            self.bus.publish(
                ctx,
                "SupervisorAgent",
                6,
                f"Job persistence failed: {exc}",
                level="WARN",
            )

    def _open_graph(self):
        """Create a graph with a checkpoint connection scoped to one invocation."""
        conn = sqlite3.connect(self.checkpoint_path, check_same_thread=False)
        try:
            graph = self._build_graph(SqliteSaver(conn))
        except Exception:
            conn.close()
            raise
        return graph, conn

    # --- NODE WRAPPERS ---

    def _node_profiler(self, state: ResearchState):
        ctx = state["ctx"]
        self.bus.set_stage(ctx, PipelineStage.PROFILING, "Layer 0 subprocess sandbox profiling")
        try:
            self.profiler_agent.run(ctx)
            self._trace(ctx, "RuntimeProfilerAgent", 0, f"files={len(ctx.raw_code_paths)}", f"cpu={ctx.code_analysis.cpu_time_ms}")
        except Exception as e:
            self.bus.publish(ctx, "SupervisorAgent", 6, f"Profiler failed (non-fatal): {e}", level="WARN")
        return {"ctx": ctx, "error_flag": state.get("error_flag", False)}

    def _node_git(self, state: ResearchState):
        ctx = state["ctx"]
        self.bus.set_stage(ctx, PipelineStage.INGESTION, "Layer 1 parsing user inputs")
        self.git_ingestor.run(ctx)
        self._trace(ctx, "GitIngestor", 1, ctx.raw_topic, "git ingest done")
        return {"ctx": ctx}

    def _node_code_ingestor(self, state: ResearchState):
        self.code_ingestor.run(state["ctx"])
        self._trace(state["ctx"], "CodeIngestor", 1, "code paths", f"files={state['ctx'].code_analysis.file_count}")
        return {"ctx": state["ctx"]}

    def _node_data_ingestor(self, state: ResearchState):
        self.data_ingestor.run(state["ctx"])
        self._trace(state["ctx"], "DataIngestor", 1, "notes", "data ingest done")
        return {"ctx": state["ctx"]}

    def _node_style_agent(self, state: ResearchState):
        self.style_agent.run(state["ctx"])
        self._trace(state["ctx"], "StyleAgent", 1, "style", str(state["ctx"].style_fingerprint)[:100])
        return {"ctx": state["ctx"]}

    def _node_query_parser(self, state: ResearchState):
        self.query_parser.run(state["ctx"])
        self._trace(state["ctx"], "QueryParser", 1, state["ctx"].raw_topic, f"subtopics={len(state['ctx'].subtopics)}")
        return {"ctx": state["ctx"]}

    def _node_faculty(self, state: ResearchState):
        ctx = state["ctx"]
        self.faculty_agent.run(ctx)
        self._trace(ctx, "FacultyProfileAgent", 3, "faculty_profiles/", f"n={len(ctx.research.faculty_context)}")
        return {"ctx": ctx}

    def _node_parallel_research(self, state: ResearchState):
        """Run L2/L3 with mode-aware skipping of code analysis."""
        ctx = state["ctx"]
        self.bus.set_stage(ctx, PipelineStage.RESEARCH_GROUNDING, "Layer 2 & 3 research grounding")
        mode = (ctx.job_mode or "full_paper").lower()
        skip_l2 = ctx.skip_code_analysis or (
            mode in ("literature_review", "research_only", "complete_draft")
            and not any(
                p and not str(p).startswith(("http://", "https://", "git@"))
                for p in (ctx.raw_code_paths or [])
            )
            and not ctx.github_url
        )

        def run_l2():
            try:
                self.code_breaker.run(ctx)
                self.algo_detector.run(ctx)
                self.complexity_analyzer.run(ctx)
                self.hw_mapper.run(ctx)
                self.bug_edge_case.run(ctx)
            except Exception as e:
                return f"L2 Error: {e}"
            return None

        def run_l3():
            try:
                self.research_orchestrator.run(ctx)
            except Exception as e:
                return f"L3 Error: {e}"
            return None

        tasks = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            if skip_l2:
                self.bus.publish(ctx, "SupervisorAgent", 6, f"Skipping L2 code analysis (mode={mode})")
            else:
                tasks["L2"] = executor.submit(run_l2)
            tasks["L3"] = executor.submit(run_l3)
            errors = [future.result() for future in tasks.values()]

        ctx.errors.extend(error for error in errors if error)
        self._trace(
            ctx,
            "ResearchOrchestrator",
            3,
            ctx.raw_topic,
            f"mode={mode} arxiv={len(ctx.research.arxiv_papers)} gaps={len(ctx.research.novelty_gaps)}",
        )
        return {"ctx": ctx}

    def _router_after_research(self, state: ResearchState):
        ctx = state["ctx"]
        hard_errors = [e for e in ctx.errors if e.startswith("L2 Error:") or e.startswith("L3 Error:")]
        if hard_errors and not ctx.research.arxiv_papers and not ctx.code_analysis.function_blocks:
            return "error_handler"
        if ctx.research.arxiv_papers or state["retry_count"] >= 2:
            return "connector"
        return "retry_arxiv"

    def _node_retry_arxiv(self, state: ResearchState):
        ctx = state["ctx"]
        self.bus.publish(ctx, "SupervisorAgent", 6, "No papers found. Retrying ArXiv Agent...", level="WARN")
        self.research_orchestrator.arxiv_agent.run(ctx)
        self._trace(ctx, "ArXivAgent", 3, "retry", f"papers={len(ctx.research.arxiv_papers)}")
        return {"retry_count": state["retry_count"] + 1, "ctx": ctx}

    def _node_connector(self, state: ResearchState):
        ctx = state["ctx"]
        self.bus.set_stage(ctx, PipelineStage.SYNTHESIS, "Layer 4 synthesizing context")
        self.connector.run(ctx)
        metrics = self.context_metrics.summarize(
            raw_code_text=ctx.raw_code_paths,
            arxiv_papers=ctx.research.arxiv_papers if ctx.research else [],
        )
        self.bus.publish(
            ctx,
            "SupervisorAgent",
            6,
            f"Context metrics stub: tokens≈{metrics['token_estimate']} papers={metrics['paper_count']}",
        )
        self._trace(ctx, "Connector", 4, "merge contexts", f"len={len(ctx.synthesis.unified_context)}")
        return {"ctx": ctx}

    def _node_outline_builder(self, state: ResearchState):
        self.outline_builder.run(state["ctx"])
        self._trace(state["ctx"], "OutlineBuilder", 4, "outline", f"sections={len(state['ctx'].synthesis.outline)}")
        return {"ctx": state["ctx"]}

    def _node_citation_agent(self, state: ResearchState):
        self.citation_agent.run(state["ctx"])
        self._trace(state["ctx"], "CitationAgent", 4, "cites", f"n={len(state['ctx'].synthesis.citations)}")
        return {"ctx": state["ctx"]}

    def _node_critic_agent(self, state: ResearchState):
        ctx = state["ctx"]
        self.critic_agent.run(ctx)
        self._trace(ctx, "CriticAgent", 4, "pre-write critique", f"score={ctx.synthesis.critic_score}")
        return {"ctx": ctx}

    def _node_dataviz(self, state: ResearchState):
        self.dataviz_agent.run(state["ctx"])
        self._trace(state["ctx"], "DataVizAgent", 5, "diagrams", f"n={len(state['ctx'].synthesis.diagrams)}")
        return {"ctx": state["ctx"]}

    def _node_writer(self, state: ResearchState):
        ctx = state["ctx"]
        self.bus.set_stage(ctx, PipelineStage.OUTPUT_GENERATION, "Layer 5 generating manuscript")
        # Require post-write QA to explicitly approve the manuscript.
        ctx.quality_audit.is_approved = False
        ctx.quality_audit.rejection_reasons = []
        self.writer_agent.run(ctx, output_dir=state["output_dir"])
        self._trace(ctx, "WriterAgent", 5, "outline", f"chars={len(ctx.output.markdown_manuscript or '')}")
        return {"ctx": ctx}

    def _node_plagiarism(self, state: ResearchState):
        ctx = state["ctx"]
        self.bus.set_stage(ctx, PipelineStage.QUALITY_AUDIT, "Layer 4.5 heuristic QA on manuscript")
        self.plagiarism_checker.run(ctx)
        self._trace(ctx, "PlagiarismCheckerAgent", 4, "manuscript", f"pct={ctx.quality_audit.plagiarism_percentage}")
        return {"ctx": ctx}

    def _node_ai_auditor(self, state: ResearchState):
        self.ai_percentage_auditor.run(state["ctx"])
        self._trace(
            state["ctx"],
            "AIPercentageAuditorAgent",
            4,
            "manuscript",
            f"pct={state['ctx'].quality_audit.ai_writing_percentage}",
        )
        return {"ctx": state["ctx"]}

    def _node_peer_reviewer(self, state: ResearchState):
        self.peer_reviewer.run(state["ctx"])
        self._trace(state["ctx"], "PeerReviewerAgent", 4, "manuscript", f"answers={len(state['ctx'].quality_audit.reviewer_answers)}")
        return {"ctx": state["ctx"]}

    def _node_format_quality(self, state: ResearchState):
        self.format_quality_auditor.run(state["ctx"])
        self._trace(state["ctx"], "FormatQualityAuditorAgent", 4, "manuscript", "format done")
        return {"ctx": state["ctx"]}

    def _node_fact_checker(self, state: ResearchState):
        ctx = state["ctx"]
        self.fact_checker.run(ctx)
        # The final QA gate is the only place that can approve a manuscript.
        if not ctx.quality_audit.rejection_reasons:
            ctx.quality_audit.is_approved = True
        self._trace(ctx, "FactCheckerAgent", 5, "manuscript", f"approved={ctx.quality_audit.is_approved}")
        return {"ctx": ctx}

    def _router_after_audit(self, state: ResearchState):
        ctx = state["ctx"]
        retries = state.get("retry_count", 0)
        if not ctx.quality_audit.is_approved and retries < MAX_QA_RETRIES:
            return "remediation"
        # Pass or max retries → export (may still be unapproved; export with reasons)
        if not ctx.quality_audit.is_approved:
            self.bus.publish(
                ctx,
                "SupervisorAgent",
                6,
                f"Max QA retries reached; exporting with is_approved=False. Reasons: "
                f"{' | '.join(ctx.quality_audit.rejection_reasons)}",
                level="WARN",
            )
        return "pdf"

    def _node_remediation(self, state: ResearchState):
        ctx = state["ctx"]
        reasons = " | ".join(ctx.quality_audit.rejection_reasons)
        self.bus.publish(
            ctx,
            "SupervisorAgent",
            6,
            f"Quality Audit REJECTED. Remediation then re-write. Reasons: {reasons}",
            level="WARN",
        )
        joined = " ".join(ctx.quality_audit.rejection_reasons)
        if "overlap" in joined.lower():
            if ctx.output.markdown_manuscript:
                ctx.output.markdown_manuscript = self.plagiarism_remediator.remediate(
                    ctx, ctx.output.markdown_manuscript
                )
        # Do NOT force-approve — next writer→QA pass must re-score
        self._trace(ctx, "PlagiarismRemediatorAgent", 4, reasons[:100], "remediated; awaiting re-audit")
        return {"ctx": ctx, "retry_count": state.get("retry_count", 0) + 1}

    def _node_pdf(self, state: ResearchState):
        self.pdf_agent.run(state["ctx"], output_dir=state["output_dir"])
        self._trace(state["ctx"], "PDFAgent", 5, "manuscript", state["ctx"].output.pdf_path or "")
        return {"ctx": state["ctx"]}

    def _node_ppt(self, state: ResearchState):
        self.ppt_agent.run(state["ctx"], output_dir=state["output_dir"])
        self._trace(state["ctx"], "PPTAgent", 5, "manuscript", state["ctx"].output.pptx_path or "")
        return {"ctx": state["ctx"]}

    def _node_evaluator(self, state: ResearchState):
        ctx = state["ctx"]
        traces = self.trace_logger.traces.get(ctx.job_id, [])
        eval_res = self.skill_evaluator.evaluate_pipeline(ctx, traces)
        ctx.quality_audit.upskill_accuracy_score = eval_res.overall_accuracy
        ctx.quality_audit.upskill_metrics = {
            name: score
            for name, score in {
                "academic_accuracy": eval_res.academic_accuracy,
                "citation_grounding": eval_res.citation_grounding,
                "structural_coherence": eval_res.structural_coherence,
                "reproducibility_score": eval_res.reproducibility_score,
            }.items()
            if score is not None
        }
        ctx.quality_audit.is_estimate = True
        ctx.quality_audit.qa_method = eval_res.method
        if eval_res.overall_accuracy is not None:
            status = "PASSED" if eval_res.is_passed else "NOT PASSED"
            self.bus.publish(
                ctx,
                "SupervisorAgent",
                6,
                f"Heuristic Upskill Eval {status}: {eval_res.overall_accuracy}% "
                f"(estimate; traces={eval_res.traces_count})",
            )
        else:
            self.bus.publish(
                ctx,
                "SupervisorAgent",
                6,
                f"Heuristic Upskill Eval incomplete: {eval_res.failure_reason}",
                level="WARN",
            )
        try:
            self.trace_logger.export_traces(ctx.job_id)
        except Exception:
            pass
        self.bus.set_stage(ctx, PipelineStage.COMPLETED, "Pipeline finished via LangGraph orchestration")
        return {"ctx": ctx}

    def _node_error_handler(self, state: ResearchState):
        self.bus.publish(
            state["ctx"],
            "SupervisorAgent",
            6,
            "Error Handler Node: hard failure path.",
            level="ERROR",
        )
        self.bus.set_stage(state["ctx"], PipelineStage.FAILED, "Pipeline failed")
        return {"ctx": state["ctx"]}

    def _build_graph(self, checkpointer: SqliteSaver) -> StateGraph:
        builder = StateGraph(ResearchState)

        builder.add_node("profiler", self._node_profiler)
        builder.add_node("git", self._node_git)
        builder.add_node("code", self._node_code_ingestor)
        builder.add_node("data", self._node_data_ingestor)
        builder.add_node("style", self._node_style_agent)
        builder.add_node("query", self._node_query_parser)
        builder.add_node("faculty", self._node_faculty)
        builder.add_node("parallel_research", self._node_parallel_research)
        builder.add_node("retry_arxiv", self._node_retry_arxiv)
        builder.add_node("connector", self._node_connector)
        builder.add_node("outline", self._node_outline_builder)
        builder.add_node("citation", self._node_citation_agent)
        builder.add_node("critic", self._node_critic_agent)
        builder.add_node("dataviz", self._node_dataviz)
        builder.add_node("writer", self._node_writer)
        builder.add_node("plagiarism", self._node_plagiarism)
        builder.add_node("ai_auditor", self._node_ai_auditor)
        builder.add_node("peer_reviewer", self._node_peer_reviewer)
        builder.add_node("format_quality", self._node_format_quality)
        builder.add_node("fact_checker", self._node_fact_checker)
        builder.add_node("remediation", self._node_remediation)
        builder.add_node("pdf", self._node_pdf)
        builder.add_node("ppt", self._node_ppt)
        builder.add_node("evaluator", self._node_evaluator)
        builder.add_node("error_handler", self._node_error_handler)

        # Ingest
        builder.add_edge(START, "profiler")
        builder.add_edge("profiler", "git")
        builder.add_edge("git", "code")
        builder.add_edge("code", "data")
        builder.add_edge("data", "style")
        builder.add_edge("style", "query")
        builder.add_edge("query", "faculty")
        builder.add_edge("faculty", "parallel_research")

        builder.add_conditional_edges(
            "parallel_research",
            self._router_after_research,
            {"connector": "connector", "retry_arxiv": "retry_arxiv", "error_handler": "error_handler"},
        )
        builder.add_edge("retry_arxiv", "connector")

        # Synthesis → pre-write critic → writer → QA
        builder.add_edge("connector", "outline")
        builder.add_edge("outline", "citation")
        builder.add_edge("citation", "critic")
        builder.add_edge("critic", "dataviz")
        builder.add_edge("dataviz", "writer")
        builder.add_edge("writer", "plagiarism")
        builder.add_edge("plagiarism", "ai_auditor")
        builder.add_edge("ai_auditor", "peer_reviewer")
        builder.add_edge("peer_reviewer", "format_quality")
        builder.add_edge("format_quality", "fact_checker")

        builder.add_conditional_edges(
            "fact_checker",
            self._router_after_audit,
            {"remediation": "remediation", "pdf": "pdf"},
        )
        # Remediate then re-write (QA will run again)
        builder.add_edge("remediation", "writer")

        builder.add_edge("pdf", "ppt")
        builder.add_edge("ppt", "evaluator")
        builder.add_edge("evaluator", END)
        builder.add_edge("error_handler", END)

        return builder.compile(checkpointer=checkpointer)

    def execute_pipeline(self, ctx: PipelineContext, output_dir: str = "./output") -> PipelineContext:
        ctx.start_time = time.time()
        self.bus.publish(ctx, "SupervisorAgent", 6, f"Starting LangGraph execution for job: {ctx.job_id}")

        conn = None
        try:
            graph, conn = self._open_graph()
            config = {"configurable": {"thread_id": ctx.job_id}}
            final_state = graph.invoke(
                {
                    "ctx": ctx,
                    "retry_count": 0,
                    "output_dir": output_dir,
                    "error_flag": False,
                },
                config=config,
            )
            ctx = final_state["ctx"]
        except Exception as e:
            err_msg = f"LangGraph execution fault: {str(e)}"
            ctx.errors.append(err_msg)
            self.bus.publish(ctx, "SupervisorAgent", 6, err_msg, level="ERROR")
            self.bus.set_stage(ctx, PipelineStage.FAILED, err_msg)
        finally:
            if conn is not None:
                conn.close()

        ctx.end_time = time.time()
        self._save_job(ctx)
        return ctx

    def resume_pipeline(self, job_id: str) -> PipelineContext:
        """Resume from SqliteSaver checkpoint using sync invoke."""
        config = {"configurable": {"thread_id": job_id}}
        conn = None
        try:
            graph, conn = self._open_graph()
            final_state = graph.invoke(None, config=config)
        finally:
            if conn is not None:
                conn.close()
        ctx = final_state["ctx"]
        ctx.end_time = time.time()
        self._save_job(ctx)
        return ctx
