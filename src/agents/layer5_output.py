import os
from src.agents.base_agent import BaseAgent
from src.core.event_bus import SupervisorBus
from src.core.models import PipelineContext
from src.exporters.bibtex_exporter import BibTeXExporter
from src.exporters.pdf_exporter import PDFExporter
from src.exporters.pptx_exporter import PPTXExporter


class WriterAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("WriterAgent", layer=5, bus=bus)

    def run(self, ctx: PipelineContext, output_dir: str = "./output") -> None:
        self.log(ctx, "Drafting full manuscript markdown using autonomous LLM synthesis...")
        topic = ctx.raw_topic
        outline = ctx.synthesis.outline
        code = ctx.code_analysis
        research = ctx.research
        synthesis = ctx.synthesis

        # Build context prompt for the LLM
        outline_str = "\n".join([f"- {s['section']}: " + ", ".join(s['topics']) for s in outline])
        gaps_str = "\n".join([f"- {g}" for g in research.novelty_gaps]) if hasattr(research, 'novelty_gaps') and research.novelty_gaps else "None found"
        algos_str = ", ".join([a['name'] for a in code.algorithms]) if code.algorithms else "N/A"
        
        prompt = f"""
You are an elite academic researcher and technical writer. Write a comprehensive, multi-page academic manuscript on the topic: "{topic}".
Use the following structured outline and research context. The manuscript must sound highly professional, technical, and strictly analytical. Do not use conversational AI filler. 
Make sure the content reflects the specific topic of "{topic}" deeply. Do not write generic boilerplate!

### OUTLINE ###
{outline_str}

### CODE METRICS (Analyzed from Source Files) ###
- Total Files: {code.file_count}
- Total Lines: {code.total_lines}
- Detected Algorithms & Patterns: {algos_str}

### IDENTIFIED NOVELTY GAPS ###
{gaps_str}

### EXPECTED OUTPUT ###
Generate the FULL Markdown content of the manuscript, complete with deep analysis, theoretical background, methodology (based on the code metrics), and detailed conclusions. Use academic headings (1. Introduction, 2. Literature Review, etc.). Ensure a minimum of 800 words.
"""
        
        system_prompt = "You are an AI autonomous research assistant that synthesizes code and literature into high-quality IEEE/ACM style markdown papers."
        
        # Generate the main manuscript content using the LLM
        generated_manuscript = self.llm.generate(prompt=prompt, system_prompt=system_prompt, temperature=0.3, max_tokens=3000)
        
        # Check if fallback happened (Ollama not connected or Timeout)
        if "[LocalLLM Offline Fallback" in generated_manuscript or "[LLM " in generated_manuscript:
            self.log(ctx, f"LLM Generation failed or offline: {generated_manuscript[:50]}... Generating a rich dynamic template instead...", level="WARN")
            # Create a more rich fallback template based on the actual variables so it doesn't look totally useless
            generated_manuscript = f"# Technical Manuscript: {topic}\n\n"
            generated_manuscript += f"**Authors:** AntiGravity Multi-Agent Research System\n\n"
            generated_manuscript += f"## 1. Abstract\nThis paper presents an automated investigation into **{topic}**. By combining static code profiling (analyzing {code.total_lines} lines across {code.file_count} files) with academic synthesis, we identify key structural implementations such as {algos_str}.\n\n"
            generated_manuscript += f"## 2. Research Context and Outline\nThe following areas were synthesized:\n{outline_str}\n\n"
            generated_manuscript += f"## 3. Findings and Novelty Gaps\nOur agents identified the following crucial research gaps requiring further theoretical exploration:\n{gaps_str}\n\n"
            generated_manuscript += f"## 4. Conclusion\nIn conclusion, {topic} presents multiple avenues for algorithmic refinement. *(Note: Full LLM synthesis was skipped due to offline mode)*.\n\n"

        # Format Final Document
        md_content = generated_manuscript + "\n\n"

        # Inject DataViz Mermaid diagrams if available
        if hasattr(ctx.synthesis, 'diagrams') and ctx.synthesis.diagrams:
            md_content += "### Appendix: System Architecture & Data Flow\n\n"
            for diagram in ctx.synthesis.diagrams:
                md_content += f"{diagram}\n\n"

        ctx.output.markdown_manuscript = md_content
        
        # Export BibTeX references & markdown file
        try:
            bib_path = BibTeXExporter.export(ctx, output_dir)
            self.log(ctx, f"WriterAgent exported BibTeX bibliography to: {bib_path}")
        except Exception as e:
            self.log(ctx, f"BibTeX export failed: {e}", level="WARN")

        self.log(ctx, f"WriterAgent completed Markdown manuscript ({len(md_content)} chars).")



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

