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
        self.log(ctx, "Drafting full manuscript markdown using style fingerprint...")
        topic = ctx.raw_topic
        outline = ctx.synthesis.outline
        code = ctx.code_analysis

        md_content = f"# Technical Manuscript: {topic}\n\n"
        md_content += f"**Authors:** AntiGravity Multi-Agent Research System\n"
        md_content += f"**Supervisor Engine:** Layer 6 Event Bus Router\n\n"

        for section in outline:
            md_content += f"## {section['section']}\n"
            for sub in section['topics']:
                md_content += f"- {sub}\n"
            md_content += "\n"

        md_content += f"### Algorithmic Breakdown\n"
        md_content += f"- Total Files: {code.file_count}\n"
        md_content += f"- Total Lines: {code.total_lines}\n"
        md_content += f"- Primary Algorithms: {', '.join([a['name'] for a in code.algorithms])}\n\n"

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
        self.log(ctx, "Compiling PDF manuscript (ResearchPaper.pdf)...")
        pdf_path = os.path.join(output_dir, "ResearchPaper.pdf")
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
        self.log(ctx, "Generating structured presentation deck (Presentation.pptx)...")
        pptx_path = os.path.join(output_dir, "Presentation.pptx")
        try:
            generated_path = PPTXExporter.export(ctx, pptx_path)
            ctx.output.pptx_path = generated_path
            self.log(ctx, f"PPTAgent successfully generated PowerPoint deck at: {generated_path}")
        except Exception as e:
            self.log(ctx, f"PPTAgent failed to export PPTX: {e}", level="ERROR")
            ctx.errors.append(f"PPT Export Error: {e}")
