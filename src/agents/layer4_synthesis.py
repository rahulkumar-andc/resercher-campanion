from typing import List
import re
from src.agents.base_agent import BaseAgent
from src.core.event_bus import SupervisorBus
from src.core.models import PipelineContext


def _join_bullets(items: List[str], empty: str = "None") -> str:
    if not items:
        return empty
    return "\n".join(f"  * {x}" for x in items[:12])


class Connector(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("Connector", layer=4, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Synthesizing unified context from code analysis and full research grounding...")

        code = ctx.code_analysis
        research = ctx.research

        abstracts_str = (
            "\n\n".join(
                f"Title: {p.title}\nAuthors: {', '.join(p.authors)}\nAbstract: {p.abstract}"
                for p in research.arxiv_papers
            )
            if research.arxiv_papers
            else "No ArXiv papers retrieved."
        )

        functions_str = (
            "\n".join(str(b) for b in code.function_blocks[:5])
            if code.function_blocks
            else "No function blocks extracted."
        )
        bugs = code.bugs_edge_cases or []
        edge_cases_str = "\n".join(str(b) for b in bugs[:8]) if bugs else "None identified."
        hw_mapping_str = str(code.hardware_mappings) if code.hardware_mappings else "Generic CPU"

        # Truncate long web/lit blocks
        web_snip = _join_bullets([(w[:400] + "…") if len(w) > 400 else w for w in (research.web_context or [])[:6]])
        lit_snip = _join_bullets(research.literature_context or [])
        cs_snip = _join_bullets(research.cs_context or [])
        elec_snip = _join_bullets(research.electronics_context or [])
        fac_snip = _join_bullets(research.faculty_context or [])

        unified = f"""
# SYSTEM CONTEXT & DEEP RESEARCH GROUNDING
**Topic**: {ctx.raw_topic}

## 1. SOURCE CODE ANALYSIS
- **Metrics**: {code.file_count} files, {code.total_lines} lines ({', '.join(code.language_breakdown.keys()) if code.language_breakdown else 'N/A'})
- **Algorithms Detected**: {', '.join([a.get('name', str(a)) for a in code.algorithms]) if code.algorithms else 'None'}
- **Hardware Profile**: {hw_mapping_str}
- **Critical Edge Cases & Weaknesses**:
{edge_cases_str}

### Core Function Blocks (Sample)
{functions_str}

## 2. THEORETICAL RESEARCH & LITERATURE
- **Primary Novelty Gaps**:
{_join_bullets(research.novelty_gaps or [])}

### Academic Grounding (ArXiv Abstracts)
{abstracts_str}

### CS Context
{cs_snip}

### Electronics / Hardware Context
{elec_snip}

### Literature Review Findings
{lit_snip}

### Web Context
{web_snip}

### Faculty / Institutional Context
{fac_snip}
""".strip()

        # Soft cap to keep LLM prompts manageable
        if len(unified) > 24000:
            unified = unified[:24000] + "\n\n[Context truncated]"

        ctx.synthesis.unified_context = unified
        self.log(ctx, "Connector generated unified context merging arxiv/code/cs/electronics/literature/web/faculty.")


class OutlineBuilder(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("OutlineBuilder", layer=4, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Building document outline aligned with job mode / Writer keys...")
        topic = ctx.raw_topic
        mode = (ctx.job_mode or "full_paper").lower()

        if mode == "literature_review":
            outline = [
                {
                    "section": "1. Literature Review",
                    "topics": ["Related work survey", "Themes", "Gaps", f"Focus: {topic}"],
                }
            ]
        elif mode == "research_only":
            outline = [
                {
                    "section": "1. Research Findings",
                    "topics": ["Key findings", "Sources", "Gaps", "Implications"],
                }
            ]
        elif mode == "complete_draft":
            outline = [
                {
                    "section": "1. Manuscript Continuation",
                    "topics": ["Continue and complete the provided draft", f"Topic: {topic}"],
                }
            ]
        else:
            outline = [
                {"section": "1. Abstract", "topics": ["Problem statement", "Approach", "Key findings"]},
                {"section": "2. Introduction", "topics": [f"Background on {topic}", "Motivation", "Contributions"]},
                {"section": "3. Literature Review", "topics": ["Related work", "Gaps", "Comparison"]},
                {"section": "4. Proposed Method / Methodology", "topics": ["Methods", "Evaluation strategy"]},
                {"section": "5. System Architecture", "topics": ["Agent layers", "Module interactions"]},
                {"section": "6. Algorithm / Flowchart", "topics": ["Algorithm steps", "Flow narrative"]},
                {"section": "7. Results", "topics": ["Metrics", "Throughput", "Edge cases"]},
                {"section": "8. Discussion", "topics": ["Interpretation", "Limitations"]},
                {"section": "9. Conclusion", "topics": ["Summary", "Outlook"]},
            ]
            # Filter to selected writers when multi + subset chosen
            if ctx.writer_mode == "multi" and ctx.selected_writers:
                wanted = {w.strip().lower() for w in ctx.selected_writers}
                filtered = []
                for s in outline:
                    base = re.sub(r"^\d+\.\s*", "", s["section"]).strip().lower()
                    if base in wanted or s["section"].strip().lower() in wanted:
                        filtered.append(s)
                if filtered:
                    outline = filtered

        ctx.synthesis.outline = outline
        self.log(ctx, f"OutlineBuilder created {len(outline)}-section outline (mode={mode}).")


class CitationAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("CitationAgent", layer=4, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Formatting citations into IEEE-style reference list...")
        papers = ctx.research.arxiv_papers
        formatted_citations = []

        for idx, paper in enumerate(papers, 1):
            authors_str = ", ".join(paper.authors[:3]) + (" et al." if len(paper.authors) > 3 else "")
            formatted_citations.append(paper)
            self.log(ctx, f"[{idx}] {authors_str}, \"{paper.title},\" {paper.journal_or_arxiv}, {paper.year}.")

        ctx.synthesis.citations = formatted_citations
        self.log(ctx, f"CitationAgent processed {len(formatted_citations)} references (no fabricated entries).")


class CriticAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("CriticAgent", layer=4, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Pre-write critique on synthesized structure...")
        feedback = []
        score = 85.0

        if not ctx.code_analysis.function_blocks:
            feedback.append("Critique: Code analysis yielded no function blocks.")
            score -= 15.0

        if len(ctx.research.arxiv_papers) < 2:
            feedback.append("Critique: Fewer than 2 ArXiv citations. Proceeding without fabricated refs.")
            score -= 10.0

        if not ctx.synthesis.unified_context:
            feedback.append("Critique: Empty unified context.")
            score -= 20.0

        if ctx.research.novelty_gaps:
            feedback.append("Validation: Novelty gaps present for outline grounding.")
        else:
            feedback.append("Critique: No novelty gaps identified.")
            score -= 5.0

        ctx.synthesis.critic_score = max(0.0, score)
        ctx.synthesis.critic_feedback = feedback
        self.log(ctx, f"CriticAgent completed evaluation. Quality Score: {ctx.synthesis.critic_score}/100.")
