import os
from src.core.models import PipelineContext


class BibTeXExporter:
    """Exports raw .bib bibliography files and Markdown manuscripts."""

    @staticmethod
    def export(ctx: PipelineContext, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        bib_filename = os.path.join(output_dir, "references.bib")
        md_filename = os.path.join(output_dir, "ResearchPaper.md")

        # 1. Export BibTeX
        bib_entries = []
        for paper in ctx.synthesis.citations:
            if paper.bibtex:
                bib_entries.append(paper.bibtex)
            else:
                first_author = paper.authors[0].split()[-1] if paper.authors else "Author"
                entry = f"@article{{{first_author}{paper.year},\n  title={{{paper.title}}},\n  author={{{' and '.join(paper.authors)}}},\n  journal={{{paper.journal_or_arxiv}}},\n  year={{{paper.year}}}\n}}"
                bib_entries.append(entry)

        bib_content = "\n\n".join(bib_entries)
        with open(bib_filename, "w", encoding="utf-8") as f:
            f.write(bib_content)

        # 2. Export Raw Markdown Manuscript
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(ctx.output.markdown_manuscript or "# Research Paper Manuscript\n")

        return bib_filename
