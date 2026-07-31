import os
import re
from typing import List, Dict, Any
from src.agents.base_agent import BaseAgent
from src.core.event_bus import SupervisorBus
from src.core.models import PipelineContext
from src.core.style_engine import StyleEngine

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


class CodeIngestor(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("CodeIngestor", layer=1, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, f"Ingesting code files from {len(ctx.raw_code_paths)} paths...")
        total_lines = 0
        file_count = 0
        lang_breakdown: Dict[str, int] = {}
        processed_files = []

        ext_map = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".cpp": "C++", ".c": "C", ".h": "C/C++ Header", ".rs": "Rust",
            ".go": "Go", ".java": "Java", ".kt": "Kotlin", ".sh": "Shell"
        }

        for path in ctx.raw_code_paths:
            if not os.path.exists(path):
                self.log(ctx, f"Code path not found: {path}", level="WARN")
                continue

            files_to_check = []
            if os.path.isdir(path):
                for root, _, files in os.walk(path):
                    for f in files:
                        ext = os.path.splitext(f)[1].lower()
                        if ext in ext_map:
                            files_to_check.append(os.path.join(root, f))
            else:
                files_to_check.append(path)

            for file_path in files_to_check:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    lines = content.splitlines()
                    num_lines = len(lines)
                    total_lines += num_lines
                    file_count += 1

                    ext = os.path.splitext(file_path)[1].lower()
                    lang = ext_map.get(ext, "Other")
                    lang_breakdown[lang] = lang_breakdown.get(lang, 0) + 1

                    processed_files.append({
                        "path": file_path,
                        "name": os.path.basename(file_path),
                        "language": lang,
                        "lines": num_lines,
                        "content": content
                    })
                except Exception as e:
                    self.log(ctx, f"Failed reading code file {file_path}: {e}", level="WARN")

        ctx.code_analysis.total_lines = total_lines
        ctx.code_analysis.file_count = file_count
        ctx.code_analysis.language_breakdown = lang_breakdown
        ctx.style_fingerprint["code_files"] = processed_files

        self.log(ctx, f"Code ingestion complete: {file_count} files processed ({total_lines} total lines across {list(lang_breakdown.keys())}).")


class DataIngestor(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("DataIngestor", layer=1, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, f"Ingesting notes/PDF data from {len(ctx.raw_notes_paths)} sources...")
        notes_text = []

        for path in ctx.raw_notes_paths:
            if not os.path.exists(path):
                self.log(ctx, f"Notes path not found: {path}", level="WARN")
                continue

            if path.lower().endswith(".pdf"):
                if PdfReader:
                    try:
                        reader = PdfReader(path)
                        text = "\n".join([page.extract_text() or "" for page in reader.pages])
                        notes_text.append(text)
                        self.log(ctx, f"Extracted {len(reader.pages)} pages from PDF: {os.path.basename(path)}")
                    except Exception as e:
                        self.log(ctx, f"Error reading PDF {path}: {e}", level="WARN")
                else:
                    self.log(ctx, f"pypdf library not available to parse PDF: {path}", level="WARN")
            else:
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                    notes_text.append(text)
                    self.log(ctx, f"Read text file: {os.path.basename(path)} ({len(text)} chars)")
                except Exception as e:
                    self.log(ctx, f"Error reading file {path}: {e}", level="WARN")

        combined_notes = "\n\n".join(notes_text)
        ctx.research.literature_summary = combined_notes[:2000] if combined_notes else "No raw notes provided."
        self.log(ctx, f"Data ingestion finished. Collected {len(combined_notes)} characters of notes.")


class StyleAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("StyleAgent", layer=1, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Extracting style fingerprint from ingested notes and context...")
        notes_text = ctx.research.literature_summary
        fingerprint = StyleEngine.extract_fingerprint(notes_text)
        ctx.style_fingerprint.update(fingerprint)
        self.log(ctx, f"Style fingerprint analyzed: Tone={fingerprint['academic_tone']}, Sentence Length={fingerprint['sentence_length']}, Citation={fingerprint['citation_preference']}.")


class QueryParser(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("QueryParser", layer=1, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        topic = ctx.raw_topic.strip()
        self.log(ctx, f"Deconstructing raw topic: '{topic}' into targeted sub-queries...")

        words = [w for w in re.findall(r'\b\w+\b', topic) if len(w) > 2]
        base_query = " ".join(words[:4]) if words else topic

        subtopics = [
            f"{base_query} algorithms and complexity analysis",
            f"{base_query} architecture and system optimization",
            f"{base_query} hardware mapping and execution bottlenecks",
            f"{base_query} state-of-the-art benchmarks and related work"
        ]

        ctx.subtopics = subtopics
        self.log(ctx, f"Generated {len(subtopics)} research sub-queries: {subtopics}")
