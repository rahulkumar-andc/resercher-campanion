import os
import json
import re
import concurrent.futures
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from src.agents.base_agent import BaseAgent
from src.core.event_bus import SupervisorBus
from src.core.models import PipelineContext
from src.core.skills_loader import load_skill_prompt
from src.exporters.bibtex_exporter import BibTeXExporter
from src.exporters.pdf_exporter import PDFExporter
from src.exporters.pptx_exporter import PPTXExporter
from src.core.llm_client import LocalLLMClient, cloud_write_completion
from src.core.llm_utils import strip_code_fence
from src.core.humanizer import HumanizerPipeline

class SectionOutput(BaseModel):
    content: str = Field(..., description="The markdown content for the section.")
    citations: List[str] = Field(default_factory=list, description="List of citations used in this section.")

class CriticFeedback(BaseModel):
    approved: bool = Field(..., description="Whether the content is approved.")
    feedback: str = Field(..., description="Specific feedback or corrections needed.")

def _style_hint(ctx: PipelineContext) -> str:
    fp = ctx.style_fingerprint or {}
    if not fp:
        return ""
    tone = fp.get("academic_tone") or fp.get("tone") or "formal academic"
    length = fp.get("sentence_length") or "balanced"
    return f"\nSTYLE FINGERPRINT: tone={tone}; sentence_length={length}. Match this voice.\n"

def _generate_section_content(agent: BaseAgent, ctx: PipelineContext, section_name: str, section_topics: str, skill_name: str, user_existing_text: str = None) -> SectionOutput:
    system_prompt = load_skill_prompt(skill_name, fallback="generic")
    system_prompt += _style_hint(ctx)
    system_prompt += "\n\nCRITICAL: You MUST output ONLY valid JSON conforming to this schema:\n{\"content\": \"markdown text here\", \"citations\": [\"author2024\"]}"
    topic = ctx.raw_topic
    unified_context = ctx.synthesis.unified_context if hasattr(ctx.synthesis, 'unified_context') else "No deep context available."
    
    if user_existing_text and user_existing_text.strip():
        section_prompt = f"""The user has partially written the {section_name} section below.
Your ONLY job is to CONTINUE it seamlessly — same tone, same style, same voice.

Topic: {topic}

USER'S WRITTEN CONTENT:
{user_existing_text}

RULES (CRITICAL):
1. Output ONLY your continuation — DO NOT repeat the user's text
2. Start exactly where the user's text ends — no overlap, no summary
3. Match sentence length, vocabulary, voice, and tense EXACTLY
4. Complete the section to reach ~800-1200 words total length
5. The join between user's text and your text must be INVISIBLE to a reader
6. Base technical facts on this context:
{unified_context}

Your continuation (start immediately, no preamble):"""
    else:
        section_prompt = f"""Write the {section_name} section for the research paper below.

Topic       : {topic}
Domain      : Computer Science / Engineering

Key Contributions / Sub-Topics:
{section_topics}

Methodology & Results Summary (Context):
{unified_context}

REQUIREMENTS:
- Target length: 800-1200 words
- No section heading needed (I will add it)
- No placeholder text like "[insert X here]"
- Every sentence must carry real information — zero filler
- Academic journal quality

{section_name}:"""

    # Writing-only cloud path; research/QA agents never call this helper.
    content_str = cloud_write_completion(system_prompt, section_prompt)
    if content_str:
        try:
            return SectionOutput.model_validate_json(strip_code_fence(content_str))
        except Exception as e:
            agent.log(ctx, f"Cloud writing JSON parse failed on {section_name}: {e}. Local fallback.", level="WARN")
    else:
        agent.log(ctx, f"Cloud writing unavailable for {section_name}; using local LLM.", level="INFO")

    fallback_prompt = f"{system_prompt}\n\n{section_prompt}"
    res_str = agent.llm.generate(prompt=fallback_prompt, system_prompt=system_prompt, temperature=0.3, max_tokens=3000)
    res_str = strip_code_fence(res_str)
    try:
        return SectionOutput.model_validate_json(res_str)
    except:
        return SectionOutput(content=res_str, citations=[])

# --- EXPLICIT 8-10 SECTION AGENTS ---

class AbstractAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("AbstractAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> SectionOutput:
        self.log(ctx, "Drafting Abstract...")
        return _generate_section_content(self, ctx, "Abstract", section_topics, "abstract", user_existing_text)

class IntroductionAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("IntroductionAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> SectionOutput:
        self.log(ctx, "Drafting Introduction...")
        return _generate_section_content(self, ctx, "Introduction", section_topics, "introduction", user_existing_text)

class LiteratureReviewAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("LiteratureReviewAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> SectionOutput:
        self.log(ctx, "Drafting Literature Review...")
        return _generate_section_content(self, ctx, "Literature Review", section_topics, "literature_review", user_existing_text)

class MethodologyAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("MethodologyAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> SectionOutput:
        self.log(ctx, "Drafting Proposed Method / Methodology...")
        return _generate_section_content(self, ctx, "Proposed Method / Methodology", section_topics, "methodology", user_existing_text)

class ResultsAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("ResultsAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> SectionOutput:
        self.log(ctx, "Drafting Results...")
        return _generate_section_content(self, ctx, "Results", section_topics, "results", user_existing_text)

class DiscussionAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("DiscussionAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> SectionOutput:
        self.log(ctx, "Drafting Discussion...")
        return _generate_section_content(self, ctx, "Discussion", section_topics, "discussion", user_existing_text)

class ConclusionAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("ConclusionAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> SectionOutput:
        self.log(ctx, "Drafting Conclusion...")
        return _generate_section_content(self, ctx, "Conclusion", section_topics, "conclusion", user_existing_text)

class SystemArchitectureAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("SystemArchitectureAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> SectionOutput:
        self.log(ctx, "Drafting System Architecture...")
        return _generate_section_content(self, ctx, "System Architecture", section_topics, "system_architecture", user_existing_text)

class AlgorithmAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("AlgorithmAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> SectionOutput:
        self.log(ctx, "Drafting Algorithm / Flowchart...")
        return _generate_section_content(self, ctx, "Algorithm / Flowchart", section_topics, "algorithm", user_existing_text)

class GenericSectionAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("GenericSectionAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_name: str, section_topics: str, user_existing_text: str = None) -> SectionOutput:
        self.log(ctx, f"Drafting {section_name}...")
        return _generate_section_content(self, ctx, section_name, section_topics, "generic", user_existing_text)

class SectionCriticAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("SectionCriticAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_name: str, output: SectionOutput) -> CriticFeedback:
        self.log(ctx, f"Critic Agent validating {section_name}...")
        
        system_prompt = load_skill_prompt("critic")
        system_prompt += "\n\nCRITICAL: You are validating an academic paper section. You MUST output ONLY valid JSON conforming to this schema:\n{\"approved\": true/false, \"feedback\": \"detailed feedback here\"}"
        
        review_prompt = f"Review the following {section_name} section for academic rigor, logic, and style:\n\n{output.content}\n\nProvide your JSON verdict:"
        
        res_str = self.llm.generate(prompt=review_prompt, system_prompt=system_prompt, temperature=0.2, max_tokens=1000)
        
        res_str = strip_code_fence(res_str)
        
        try:
            feedback = CriticFeedback.model_validate_json(res_str)
            return feedback
        except Exception as e:
            self.log(ctx, f"Critic JSON parsing failed: {e}. Defaulting to manual logic.", level="WARN")
            if len(output.content) < 50:
                return CriticFeedback(approved=False, feedback="Content too short (fallback).")
            return CriticFeedback(approved=True, feedback="Fallback approval.")

# --- THE ORCHESTRATOR ---

class WriterAgent(BaseAgent):
    """Now acts as the Section Orchestrator Agent that delegates to the 8 specialized sub-agents."""
    def __init__(self, bus: SupervisorBus):
        super().__init__("WriterAgent", layer=5, bus=bus)
        self.agents = {
            "Abstract": AbstractAgent(bus),
            "Introduction": IntroductionAgent(bus),
            "Literature Review": LiteratureReviewAgent(bus),
            "Proposed Method / Methodology": MethodologyAgent(bus),
            "Results": ResultsAgent(bus),
            "Discussion": DiscussionAgent(bus),
            "Conclusion": ConclusionAgent(bus),
            "System Architecture": SystemArchitectureAgent(bus),
            "Algorithm / Flowchart": AlgorithmAgent(bus)
        }
        self.generic_agent = GenericSectionAgent(bus)

    def run(self, ctx: PipelineContext, output_dir: str = "./output") -> None:
        self.log(ctx, "Drafting manuscript (respecting job_mode / writer_mode)...")
        topic = ctx.raw_topic
        outline = ctx.synthesis.outline or []
        mode = (ctx.job_mode or "full_paper").lower()
        writer_mode = (ctx.writer_mode or "multi").lower()
        draft = (ctx.draft_text or "").strip()
        target_section = ctx.target_section
        user_existing_text = draft if draft else None

        # --- complete_draft: continue half paper with one writer ---
        if mode == "complete_draft" and draft:
            self.log(ctx, "complete_draft mode: single writer continuing user manuscript...")
            agent_key = (ctx.selected_writers[0] if ctx.selected_writers else None)
            section_topics = f"Complete and polish the draft for topic: {topic}"
            if agent_key and agent_key in self.agents:
                out = self.agents[agent_key].run(ctx, section_topics, draft)
            else:
                out = self.generic_agent.run(
                    ctx,
                    "Manuscript Continuation",
                    section_topics,
                    draft,
                )
            continuation = out.content or ""
            # Avoid duplicating if model echoed the draft
            if continuation.strip().startswith(draft[:80]):
                ctx.output.markdown_manuscript = continuation
            else:
                ctx.output.markdown_manuscript = draft.rstrip() + "\n\n" + continuation
            self._finalize_exports(ctx, output_dir)
            return

        # --- research_only: one research findings report ---
        if mode == "research_only":
            self.log(ctx, "research_only mode: synthesizing findings report...")
            findings = ctx.synthesis.unified_context or ""
            gaps = "\n".join(f"- {g}" for g in (ctx.research.novelty_gaps or []))
            lit = "\n".join(f"- {x}" for x in (ctx.research.literature_context or [])[:8])
            papers = "\n".join(
                f"- {p.title} ({p.year}) {p.url}" for p in (ctx.research.arxiv_papers or [])[:8]
            )
            section_topics = (
                f"Summarize research findings for '{topic}'. "
                f"Gaps:\n{gaps}\nLiterature:\n{lit}\nPapers:\n{papers}\nContext:\n{findings[:6000]}"
            )
            out = self.generic_agent.run(ctx, "Research Findings", section_topics, None)
            ctx.output.markdown_manuscript = f"# Research Findings: {topic}\n\n{out.content}\n"
            self._finalize_exports(ctx, output_dir)
            return

        # --- targeted single section (legacy + literature_review default) ---
        if target_section or (mode == "literature_review" and writer_mode == "single"):
            section = target_section or "Literature Review"
            self.log(ctx, f"Targeted generation for section: {section}")
            section_topics = ""
            for s in outline:
                base = re.sub(r"^\d+\.\s*", "", s["section"]).strip()
                if base == section or s["section"] == section:
                    section_topics = ", ".join(s["topics"])
                    break
            if not section_topics:
                section_topics = f"Literature review on {topic}"
            if section in self.agents:
                out = self.agents[section].run(ctx, section_topics, user_existing_text)
            else:
                # strip number prefix match
                matched = None
                for key in self.agents:
                    if key.lower() == section.lower():
                        matched = key
                        break
                if matched:
                    out = self.agents[matched].run(ctx, section_topics, user_existing_text)
                else:
                    out = self.generic_agent.run(ctx, section, section_topics, user_existing_text)
            if user_existing_text:
                final_content = user_existing_text + "\n\n" + out.content
            else:
                final_content = out.content
            ctx.output.markdown_manuscript = f"## {section}\n\n{final_content}"
            self._finalize_exports(ctx, output_dir)
            return

        # --- single writer for whole outline (one agent only) ---
        if writer_mode == "single":
            agent_key = ctx.selected_writers[0] if ctx.selected_writers else None
            self.log(ctx, f"single writer mode: agent={agent_key or 'GenericSectionAgent'}")
            topics_blob = "; ".join(
                f"{s['section']}: {', '.join(s['topics'])}" for s in outline
            )
            prompt_topics = f"Write a cohesive paper covering: {topics_blob}"
            if agent_key and agent_key in self.agents:
                out = self.agents[agent_key].run(ctx, prompt_topics, user_existing_text)
                title = agent_key
            else:
                out = self.generic_agent.run(ctx, "Full Paper", prompt_topics, user_existing_text)
                title = "Full Paper"
            body = out.content
            if user_existing_text:
                body = user_existing_text.rstrip() + "\n\n" + body
            ctx.output.markdown_manuscript = f"# {topic}\n\n## {title}\n\n{body}\n"
            self._finalize_exports(ctx, output_dir)
            return

        # --- multi section agents (default full_paper / literature with multi) ---
        self.log(ctx, "Multi-agent section synthesis...")
        full_manuscript = f"# {topic}\n\n"
        critic = SectionCriticAgent(self.bus)

        def generate_and_critique(section_dict):
            section_title = section_dict["section"]
            section_topics = ", ".join(section_dict["topics"])
            base_title = re.sub(r"^\d+\.\s*", "", section_title).strip()

            if base_title in self.agents:
                out = self.agents[base_title].run(ctx, section_topics, None)
            else:
                out = self.generic_agent.run(ctx, section_title, section_topics, None)

            feedback = critic.run(ctx, base_title, out)
            if not feedback.approved:
                self.log(ctx, f"Critic rejected {base_title}: {feedback.feedback}", level="WARN")
            return section_title, out.content

        sections = outline
        if ctx.selected_writers:
            wanted = {w.strip().lower() for w in ctx.selected_writers}
            sections = [
                s
                for s in outline
                if re.sub(r"^\d+\.\s*", "", s["section"]).strip().lower() in wanted
            ] or outline

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(5, max(1, len(sections)))) as executor:
            futures = [executor.submit(generate_and_critique, s) for s in sections]
            for future in futures:
                title, content = future.result()
                full_manuscript += f"\n\n## {title}\n\n{content}"

        md_content = full_manuscript + "\n\n"
        if ctx.synthesis.diagrams:
            md_content += "### Appendix: System Architecture & Data Flow\n\n"
            for diagram in ctx.synthesis.diagrams:
                md_content += f"{diagram}\n\n"

        ctx.output.markdown_manuscript = md_content
        if ctx.style_fingerprint:
            try:
                style_docs = [ctx.draft_text] if ctx.draft_text.strip() else []
                humanizer = HumanizerPipeline(self.llm, user_style_docs=style_docs)
                ctx.output.markdown_manuscript = humanizer.humanize(md_content)
                self.log(ctx, "Applied full HumanizerPipeline (regex, burstiness, perplexity, style, adversarial).")
            except Exception as e:
                self.log(ctx, f"Humanizer skipped: {e}", level="WARN")

        self._finalize_exports(ctx, output_dir)

    def _finalize_exports(self, ctx: PipelineContext, output_dir: str) -> None:
        try:
            bib_path = BibTeXExporter.export(ctx, output_dir)
            self.log(ctx, f"WriterAgent exported BibTeX bibliography to: {bib_path}")
        except Exception as e:
            self.log(ctx, f"BibTeX export failed: {e}", level="WARN")
        self.log(
            ctx,
            f"WriterAgent completed Markdown manuscript ({len(ctx.output.markdown_manuscript or '')} chars).",
        )



class PDFAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("PDFAgent", layer=5, bus=bus)

    def run(self, ctx: PipelineContext, output_dir: str = "./output") -> None:
        pdf_filename = f"{ctx.job_id}_ResearchPaper.pdf"
        self.log(ctx, f"Compiling PDF manuscript ({pdf_filename})...")
        pdf_path = os.path.join(output_dir, pdf_filename)
        try:
            generated_path = PDFExporter.export(ctx, pdf_path)
            ctx.output.pdf_path = generated_path
            self.log(ctx, f"PDFAgent successfully generated PDF at: {generated_path}")
        except Exception as e:
            self.log(ctx, f"PDFAgent failed to export PDF: {e}", level="ERROR")
            ctx.errors.append(f"PDF Export Error: {e}")


class PPTAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("PPTAgent", layer=5, bus=bus)

    def run(self, ctx: PipelineContext, output_dir: str = "./output") -> None:
        pptx_filename = f"{ctx.job_id}_Presentation.pptx"
        self.log(ctx, f"Generating structured presentation deck ({pptx_filename})...")
        pptx_path = os.path.join(output_dir, pptx_filename)
        try:
            generated_path = PPTXExporter.export(ctx, pptx_path)
            ctx.output.pptx_path = generated_path
            self.log(ctx, f"PPTAgent successfully generated PowerPoint deck at: {generated_path}")
        except Exception as e:
            self.log(ctx, f"PPTAgent failed to export PPTX: {e}", level="ERROR")
            ctx.errors.append(f"PPT Export Error: {e}")

class DataVizAgent(BaseAgent):
    """Generates Mermaid.js diagrams to visualize algorithms and system architectures."""

    def __init__(self, bus: SupervisorBus):
        super().__init__("DataVizAgent", layer=5, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Synthesizing data visualization diagrams (Mermaid.js)...")
        
        # We simulate generating a Mermaid chart based on the top algorithm
        code = ctx.code_analysis
        algo_name = code.algorithms[0]['name'] if code.algorithms else "Data Processing Pipeline"
        
        mermaid_chart = (
            "```mermaid\n"
            f"graph TD;\n"
            f"    A[Input Data] --> B({algo_name});\n"
            f"    B --> C{{Decision Engine}};\n"
            f"    C -- Valid --> D[Final Output];\n"
            f"    C -- Invalid --> E[Error Handler];\n"
            "```"
        )
        
        # Inject the diagram into the unified context or outline so WriterAgent picks it up
        if not hasattr(ctx.synthesis, 'diagrams'):
            ctx.synthesis.diagrams = []
        ctx.synthesis.diagrams.append(mermaid_chart)
        
        self.log(ctx, f"DataVizAgent successfully generated architectural diagram for '{algo_name}'.")
