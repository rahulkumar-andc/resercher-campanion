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
        unified_context = ctx.synthesis.unified_context if hasattr(ctx.synthesis, 'unified_context') else "No deep context available."
        
        system_prompt = "You are an elite academic researcher and tenured professor. Write strictly in IEEE/ACM academic journal format. Be exhaustive, mathematically rigorous, and highly analytical."
        
        import requests
        import os
        
        api_key = os.environ.get("CLOUD_LLM_API_KEY")
        if not api_key:
            try:
                with open(".env", "r") as f:
                    for line in f:
                        if line.startswith("CLOUD_LLM_API_KEY="):
                            api_key = line.strip().split("=", 1)[1]
                            break
            except Exception:
                pass
                
        if not api_key:
            self.log(ctx, "CLOUD_LLM_API_KEY not found in .env. Falling back to Local LLM.", level="WARN")
        
        self.log(ctx, "Initiating DEEP MULTI-PASS ACADEMIC SYNTHESIS. Generating paper section by section for maximum depth...")
        
        full_manuscript = f"# {topic}\n\n"
        
        if api_key:
            try:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                
                # Iterate through each section and generate massive depth
                for section_dict in outline:
                    section_title = section_dict['section']
                    section_topics = ", ".join(section_dict['topics'])
                    self.log(ctx, f"Drafting intensive academic content for: {section_title}...")
                    
                    section_prompt = f"""
You are writing a top-tier academic research paper on: "{topic}".
You are currently drafting ONLY this specific section: **{section_title}**.

### SUB-TOPICS TO COVER IN THIS SECTION ###
{section_topics}

### SYSTEM UNIFIED CONTEXT (Code, Algorithms & Literature) ###
{unified_context}

### PREVIOUSLY WRITTEN SECTIONS (For flow and continuity) ###
{full_manuscript[-2000:] if len(full_manuscript) > 2000 else full_manuscript}

### INSTRUCTIONS ###
1. Write ONLY the content for **{section_title}**. Do not write other sections.
2. Be extremely exhaustive, theoretical, and highly technical. 
3. If this is Methodology or Code Analysis, cite specific code metrics, time complexities (Big-O), and edge cases provided in the context.
4. If this is Literature, cite the provided ArXiv abstracts.
5. Write at least 800-1200 words for this section alone. Do NOT use conversational AI filler.
"""
                    payload = {
                        "model": "mistral-large-latest",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": section_prompt}
                        ],
                        "temperature": 0.2,
                        "max_tokens": 4000
                    }
                    
                    resp = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload, timeout=180)
                    
                    if resp.status_code == 200:
                        section_content = resp.json()["choices"][0]["message"]["content"]
                        full_manuscript += f"\n\n## {section_title}\n\n{section_content}"
                        self.log(ctx, f"Completed {section_title} ({len(section_content)} chars).")
                    else:
                        self.log(ctx, f"Cloud API Error on {section_title}: {resp.status_code}. Skipping.", level="WARN")
                        
                self.log(ctx, "Deep multi-pass synthesis completed successfully.")
            except Exception as e:
                self.log(ctx, f"Deep synthesis failed: {e}. Falling back to single-pass.", level="WARN")
                api_key = None # Trigger fallback
                
        # Fallback to local single-pass
        if not api_key:
            fallback_prompt = f"Write a full research paper on {topic} using context:\n{unified_context}\nOutline:\n{outline_str}"
            full_manuscript = self.llm.generate(prompt=fallback_prompt, system_prompt=system_prompt, temperature=0.3, max_tokens=3000)

        # Format Final Document
        md_content = full_manuscript + "\n\n"

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

