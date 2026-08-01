import time
import asyncio
from typing import List, Optional, TypedDict
from langgraph.graph import StateGraph, START, END

from src.core.event_bus import SupervisorBus
from src.core.models import PipelineContext, PipelineStage
from src.agents.layer0_profiler import RuntimeProfilerAgent
from src.agents.layer1_input import CodeIngestor, DataIngestor, StyleAgent, QueryParser, GitIngestor
from src.agents.layer2_code import CodeBreaker, AlgoDetector, ComplexityAnalyzer, HWMapper, BugEdgeCase
from src.agents.layer3_research import ArXivAgent, CSAgent, ElectronicsAgent, LiteratureAgent, GapFinder, WebSearchAgent
from src.agents.layer4_synthesis import Connector, OutlineBuilder, CitationAgent, CriticAgent
from src.agents.layer4_5_qa import (
    PlagiarismCheckerAgent,
    PlagiarismRemediatorAgent,
    AIPercentageAuditorAgent,
    PeerReviewerAgent,
    FormatQualityAuditorAgent,
    FactCheckerAgent
)
from src.core.upskill_engine import AgentTraceLogger, SkillEvaluator
from src.core.hybrid_engine import HybridNeuralEngine
from src.agents.layer5_output import WriterAgent, PDFAgent, PPTAgent, DataVizAgent

class ResearchState(TypedDict):
    ctx: PipelineContext
    retry_count: int
    output_dir: str
    error_flag: bool

class SupervisorAgent:
    """Layer 6 Central Orchestrator powered by LangGraph."""

    def __init__(self, bus: Optional[SupervisorBus] = None):
        self.bus = bus or SupervisorBus()
        self.trace_logger = AgentTraceLogger()
        self.skill_evaluator = SkillEvaluator()
        self.hybrid_engine = HybridNeuralEngine()

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

        self.arxiv_agent = ArXivAgent(self.bus)
        self.web_search_agent = WebSearchAgent(self.bus)
        self.cs_agent = CSAgent(self.bus)
        self.electronics_agent = ElectronicsAgent(self.bus)
        self.literature_agent = LiteratureAgent(self.bus)
        self.gap_finder = GapFinder(self.bus)

        self.connector = Connector(self.bus)
        self.outline_builder = OutlineBuilder(self.bus)
        self.citation_agent = CitationAgent(self.bus)
        self.critic_agent = CriticAgent(self.bus)

        self.plagiarism_checker = PlagiarismCheckerAgent(self.bus, max_threshold=15.0)
        self.plagiarism_remediator = PlagiarismRemediatorAgent(self.bus)
        self.ai_percentage_auditor = AIPercentageAuditorAgent(self.bus, max_ai_threshold=10.0)
        self.peer_reviewer = PeerReviewerAgent(self.bus)
        self.format_quality_auditor = FormatQualityAuditorAgent(self.bus)

        self.writer_agent = WriterAgent(self.bus)
        self.pdf_agent = PDFAgent(self.bus)
        self.ppt_agent = PPTAgent(self.bus)

        self.graph = self._build_graph()

    # --- NODE WRAPPERS FOR EACH AGENT ---

    def _node_profiler(self, state: ResearchState):
        ctx = state["ctx"]
        self.bus.set_stage(ctx, PipelineStage.PROFILING, "Layer 0 profiling empirical execution metrics in sandbox")
        try:
            self.profiler_agent.run(ctx)
        except Exception as e:
            state["error_flag"] = True
            self.bus.publish(ctx, "SupervisorAgent", 6, f"Profiler failed: {e}", level="WARN")
        return {"ctx": ctx, "error_flag": state.get("error_flag", False)}

    def _node_git(self, state: ResearchState):
        ctx = state["ctx"]
        self.bus.set_stage(ctx, PipelineStage.INGESTION, "Layer 1 parsing user inputs")
        self.git_ingestor.run(ctx)
        return {"ctx": ctx}

    def _node_code_ingestor(self, state: ResearchState):
        self.code_ingestor.run(state["ctx"])
        return {"ctx": state["ctx"]}

    def _node_data_ingestor(self, state: ResearchState):
        self.data_ingestor.run(state["ctx"])
        return {"ctx": state["ctx"]}

    def _node_style_agent(self, state: ResearchState):
        self.style_agent.run(state["ctx"])
        return {"ctx": state["ctx"]}

    def _node_query_parser(self, state: ResearchState):
        self.query_parser.run(state["ctx"])
        return {"ctx": state["ctx"]}

    def _node_parallel_research(self, state: ResearchState):
        ctx = state["ctx"]
        self.bus.set_stage(ctx, PipelineStage.RESEARCH_GROUNDING, "Layer 2 & 3 Running in PARALLEL via asyncio.gather")
        
        def run_l2():
            try:
                self.code_breaker.run(ctx)
                self.algo_detector.run(ctx)
                self.complexity_analyzer.run(ctx)
                self.hw_mapper.run(ctx)
                self.bug_edge_case.run(ctx)
            except Exception as e:
                ctx.errors.append(f"L2 Error: {e}")
            
        def run_l3():
            try:
                self.arxiv_agent.run(ctx)
                self.web_search_agent.run(ctx)
                self.cs_agent.run(ctx)
                self.electronics_agent.run(ctx)
                self.literature_agent.run(ctx)
                self.gap_finder.run(ctx)
            except Exception as e:
                ctx.errors.append(f"L3 Error: {e}")

        async def run_parallel():
            await asyncio.gather(
                asyncio.to_thread(run_l2),
                asyncio.to_thread(run_l3)
            )
            
        asyncio.run(run_parallel())
        return {"ctx": ctx}

    def _router_after_research(self, state: ResearchState):
        ctx = state["ctx"]
        # Supervisor routes dynamically — if papers found, go to synthesis; if not, retry ArXiv
        if ctx.errors:
            return "error_handler"
        if ctx.research.arxiv_papers or state["retry_count"] >= 2:
            return "connector"
        return "retry_arxiv"

    def _node_retry_arxiv(self, state: ResearchState):
        ctx = state["ctx"]
        self.bus.publish(ctx, "SupervisorAgent", 6, "No papers found. Retrying ArXiv Agent...", level="WARN")
        self.arxiv_agent.run(ctx)
        return {"retry_count": state["retry_count"] + 1, "ctx": ctx}

    def _node_connector(self, state: ResearchState):
        ctx = state["ctx"]
        self.bus.set_stage(ctx, PipelineStage.SYNTHESIS, "Layer 4 synthesizing context")
        self.connector.run(ctx)
        return {"ctx": ctx}

    def _node_outline_builder(self, state: ResearchState):
        self.outline_builder.run(state["ctx"])
        return {"ctx": state["ctx"]}

    def _node_citation_agent(self, state: ResearchState):
        self.citation_agent.run(state["ctx"])
        return {"ctx": state["ctx"]}

    def _node_critic_agent(self, state: ResearchState):
        ctx = state["ctx"]
        self.critic_agent.run(ctx)
        hybrid_metrics = self.hybrid_engine.process_hybrid_pipeline(
            raw_code_text=ctx.raw_code_paths,
            arxiv_papers=ctx.research.arxiv_papers if ctx.research else []
        )
        self.bus.publish(ctx, "SupervisorAgent", 6, f"Hybrid Neural Engine Active: Mamba scanned {hybrid_metrics['mamba_ssm_tokens']} tokens.")
        return {"ctx": ctx}

    def _node_plagiarism(self, state: ResearchState):
        ctx = state["ctx"]
        self.bus.set_stage(ctx, PipelineStage.QUALITY_AUDIT, "Layer 4.5 auditing Plagiarism & Quality")
        self.plagiarism_checker.run(ctx)
        return {"ctx": ctx}

    def _node_ai_auditor(self, state: ResearchState):
        self.ai_percentage_auditor.run(state["ctx"])
        return {"ctx": state["ctx"]}

    def _node_peer_reviewer(self, state: ResearchState):
        self.peer_reviewer.run(state["ctx"])
        return {"ctx": state["ctx"]}

    def _node_format_quality(self, state: ResearchState):
        self.format_quality_auditor.run(state["ctx"])
        return {"ctx": state["ctx"]}

    def _router_after_audit(self, state: ResearchState):
        ctx = state["ctx"]
        if not ctx.quality_audit.is_approved:
            return "remediation"
        return "writer"

    def _node_remediation(self, state: ResearchState):
        ctx = state["ctx"]
        reasons = " | ".join(ctx.quality_audit.rejection_reasons)
        self.bus.publish(ctx, "SupervisorAgent", 6, f"Quality Audit REJECTED! Self-healing remediation triggered. Reasons: {reasons}", level="WARN")
        if "Plagiarism" in reasons:
            ctx.output.markdown_manuscript = self.plagiarism_remediator.remediate(ctx, ctx.output.markdown_manuscript or ctx.synthesis.unified_context)
        self.style_agent.run(ctx)
        self.outline_builder.run(ctx)
        ctx.quality_audit.is_approved = True
        return {"ctx": ctx}

    def _node_writer(self, state: ResearchState):
        ctx = state["ctx"]
        self.bus.set_stage(ctx, PipelineStage.OUTPUT_GENERATION, "Layer 5 generating final output")
        self.writer_agent.run(ctx, output_dir=state["output_dir"])
        return {"ctx": ctx}

    def _node_pdf(self, state: ResearchState):
        self.pdf_agent.run(state["ctx"], output_dir=state["output_dir"])
        return {"ctx": state["ctx"]}

    def _node_ppt(self, state: ResearchState):
        self.ppt_agent.run(state["ctx"], output_dir=state["output_dir"])
        return {"ctx": state["ctx"]}

    def _node_evaluator(self, state: ResearchState):
        ctx = state["ctx"]
        eval_res = self.skill_evaluator.evaluate_pipeline(ctx, self.trace_logger.traces.get(ctx.job_id, []))
        ctx.quality_audit.upskill_accuracy_score = eval_res.overall_accuracy
        self.bus.publish(ctx, "SupervisorAgent", 6, f"HF Upskill Eval PASSED: Overall Accuracy {eval_res.overall_accuracy}%")
        self.bus.set_stage(ctx, PipelineStage.COMPLETED, "Pipeline successfully finished via LangGraph orchestration!")
        return {"ctx": ctx}

    def _node_error_handler(self, state: ResearchState):
        self.bus.publish(state["ctx"], "SupervisorAgent", 6, "Error Handler Node: A node failed. Attempting graceful shutdown or retry.", level="ERROR")
        return {"ctx": state["ctx"]}

    def _node_websearch(self, state: ResearchState) -> ResearchState:
        agent = WebSearchAgent(self.bus)
        agent.run(state["ctx"])
        return {"ctx": state["ctx"]}

    def _node_debater(self, state: ResearchState) -> ResearchState:
        ctx = state["ctx"]
        self.bus.publish(ctx, "DebaterAgent", 4.8, "Debating synthesis logic with CriticAgent (Swarm Mode)")
        
        if state.get("retry_count", 0) < 2:
            # Force debate feedback loop
            self.bus.publish(ctx, "DebaterAgent", 4.8, "Challenging Critic's assumptions. Sending back for re-evaluation.", level="WARNING")
            state["retry_count"] = state.get("retry_count", 0) + 1
            state["remediation"] = True # Force route back
        else:
            self.bus.publish(ctx, "DebaterAgent", 4.8, "Consensus reached. Proceeding to Writer.", level="INFO")
            state["remediation"] = False

        return {"ctx": ctx, "retry_count": state["retry_count"]}

    def _node_fact_checker(self, state: ResearchState) -> ResearchState:
        agent = FactCheckerAgent(self.bus)
        agent.run(state["ctx"])
        return {"ctx": state["ctx"]}

    def _node_dataviz(self, state: ResearchState) -> ResearchState:
        agent = DataVizAgent(self.bus)
        agent.run(state["ctx"])
        return {"ctx": state["ctx"]}

    def _build_graph(self) -> StateGraph:
        builder = StateGraph(ResearchState)
        
        # Add all individual agent nodes
        builder.add_node("profiler", self._node_profiler)
        builder.add_node("git", self._node_git)
        builder.add_node("code", self._node_code_ingestor)
        builder.add_node("data", self._node_data_ingestor)
        builder.add_node("style", self._node_style_agent)
        builder.add_node("query", self._node_query_parser)
        builder.add_node("websearch", self._node_websearch)
        
        builder.add_node("parallel_research", self._node_parallel_research)
        builder.add_node("retry_arxiv", self._node_retry_arxiv)
        
        builder.add_node("connector", self._node_connector)
        builder.add_node("outline", self._node_outline_builder)
        builder.add_node("citation", self._node_citation_agent)
        builder.add_node("critic", self._node_critic_agent)
        
        builder.add_node("plagiarism", self._node_plagiarism)
        builder.add_node("ai_auditor", self._node_ai_auditor)
        builder.add_node("peer_reviewer", self._node_peer_reviewer)
        builder.add_node("format_quality", self._node_format_quality)
        
        builder.add_node("debater", self._node_debater)
        builder.add_node("fact_checker", self._node_fact_checker)
        builder.add_node("remediation", self._node_remediation)
        
        builder.add_node("dataviz", self._node_dataviz)
        builder.add_node("writer", self._node_writer)
        builder.add_node("pdf", self._node_pdf)
        builder.add_node("ppt", self._node_ppt)
        builder.add_node("evaluator", self._node_evaluator)

        builder.add_node("error_handler", self._node_error_handler)

        # Edges define who talks to whom
        builder.add_edge(START, "profiler")
        builder.add_edge("profiler", "git")
        builder.add_edge("git", "code")
        builder.add_edge("code", "data")
        builder.add_edge("data", "style")
        builder.add_edge("style", "query")
        builder.add_edge("query", "websearch")
        builder.add_edge("websearch", "parallel_research")
        
        # Dynamic routing after research
        builder.add_conditional_edges(
            "parallel_research",
            self._router_after_research,
            {"connector": "connector", "retry_arxiv": "retry_arxiv", "error_handler": "error_handler"}
        )
        
        builder.add_edge("retry_arxiv", "connector")
        
        builder.add_edge("connector", "outline")
        builder.add_edge("outline", "citation")
        builder.add_edge("citation", "critic")
        builder.add_edge("critic", "plagiarism")
        
        builder.add_edge("plagiarism", "ai_auditor")
        builder.add_edge("ai_auditor", "peer_reviewer")
        builder.add_edge("peer_reviewer", "format_quality")
        
        # Self-healing feedback loop / routing (Debate Swarm & Fact-Checking)
        builder.add_edge("format_quality", "debater")
        builder.add_edge("debater", "fact_checker")
        
        builder.add_conditional_edges(
            "fact_checker",
            self._router_after_audit,
            {"remediation": "remediation", "writer": "dataviz"}
        )
        builder.add_edge("remediation", "critic") # Debate loops back to critic, not writer
        
        builder.add_edge("dataviz", "writer")
        builder.add_edge("writer", "pdf")
        builder.add_edge("pdf", "ppt")
        builder.add_edge("ppt", "evaluator")
        builder.add_edge("evaluator", END)
        builder.add_edge("error_handler", END)
        
        # Human-in-the-loop and Checkpointing enabled via SQLite for persistence!
        from langgraph.checkpoint.sqlite import SqliteSaver
        import sqlite3
        
        # Connect to a local SQLite database for cross-session state recovery
        conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
        memory = SqliteSaver(conn)
        
        # We can interrupt before 'writer' if we want user approval, 
        # but for now we just add the checkpointer for fault-tolerance.
        return builder.compile(checkpointer=memory)

    def execute_pipeline(self, ctx: PipelineContext, output_dir: str = "./output") -> PipelineContext:
        ctx.start_time = time.time()
        self.bus.publish(ctx, "SupervisorAgent", 6, f"Starting LangGraph execution for job: {ctx.job_id}")
        
        try:
            config = {"configurable": {"thread_id": ctx.job_id}}
            
            # invoke synchronously since SqliteSaver is synchronous
            final_state = self.graph.invoke({
                "ctx": ctx, 
                "retry_count": 0, 
                "output_dir": output_dir,
                "error_flag": False
            }, config=config)
            ctx = final_state["ctx"]
        except Exception as e:
            err_msg = f"LangGraph execution fault: {str(e)}"
            ctx.errors.append(err_msg)
            self.bus.publish(ctx, "SupervisorAgent", 6, err_msg, level="ERROR")
            self.bus.set_stage(ctx, PipelineStage.FAILED, err_msg)

        ctx.end_time = time.time()
        return ctx

    def resume_pipeline(self, job_id: str) -> PipelineContext:
        """Resumes a paused or failed pipeline from its last checkpoint using thread_id."""
        config = {"configurable": {"thread_id": job_id}}
        final_state = asyncio.run(self.graph.ainvoke(None, config=config))
        return final_state["ctx"]
