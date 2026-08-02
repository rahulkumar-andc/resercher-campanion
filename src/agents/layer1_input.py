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


import json

class StyleAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("StyleAgent", layer=1, bus=bus)
        self.profile_path = os.path.expanduser("~/.arc_style_profile.json")

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Extracting style fingerprint from ingested notes and context...")
        
        fingerprint = {}
        # Load existing profile if it exists
        if os.path.exists(self.profile_path):
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    fingerprint = json.load(f)
                self.log(ctx, "Loaded existing style profile from disk.")
            except Exception as e:
                self.log(ctx, f"Failed to load style profile: {e}", level="WARN")

        # If we have new notes to learn from, analyze and update profile
        notes_text = ctx.research.literature_summary
        if notes_text and notes_text != "No raw notes provided.":
            new_fingerprint = StyleEngine.extract_fingerprint(notes_text)
            
            # Simple merge: prefer newly learned vocabulary density / length if it's more robust
            if new_fingerprint:
                fingerprint.update(new_fingerprint)
                
            # Save updated profile
            try:
                with open(self.profile_path, "w", encoding="utf-8") as f:
                    json.dump(fingerprint, f, indent=2)
                self.log(ctx, "Saved updated style profile to disk.")
            except Exception as e:
                self.log(ctx, f"Failed to save style profile: {e}", level="WARN")
        else:
            if not fingerprint:
                # No notes and no existing profile, use default
                fingerprint = StyleEngine.extract_fingerprint("")
                self.log(ctx, "No documents fed for style learning. Using default academic style.")

        ctx.style_fingerprint.update(fingerprint)
        self.log(ctx, f"Style fingerprint analyzed: Tone={fingerprint.get('academic_tone')}, Sentence Length={fingerprint.get('sentence_length')}, Citation={fingerprint.get('citation_preference')}.")


class QueryParser(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("QueryParser", layer=1, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        topic = ctx.raw_topic.strip()
        self.log(ctx, f"Deconstructing raw topic: '{topic}' into targeted sub-queries...")

        prompt = f"""You are an expert academic research assistant.
Break down the following research topic into exactly 4 targeted sub-queries suitable for searching literature databases like ArXiv and Google Scholar.
Include queries about: algorithms/complexity, architecture/optimization, hardware mapping, and state-of-the-art benchmarks.
Return ONLY a JSON list of 4 strings. No markdown formatting, no explanations.
Topic: {topic}"""

        response = self.llm.generate(prompt=prompt, system_prompt="You are a JSON-only API.", max_tokens=150, temperature=0.3)
        
        try:
            # Clean up potential markdown formatting from LLM response
            clean_json = response.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            
            subtopics = json.loads(clean_json.strip())
            if not isinstance(subtopics, list):
                raise ValueError("Response is not a list")
        except Exception as e:
            self.log(ctx, f"Failed to parse LLM subqueries, falling back to heuristics ({e}).", level="WARN")
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

import subprocess
import tempfile

class GitIngestor(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("GitIngestor", layer=1, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Checking for Git repository URLs...")

        urls = re.findall(
            r"https?://(?:www\.)?(?:github\.com|gitlab\.com)/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+(?:\.git)?",
            ctx.raw_topic or "",
        )
        if ctx.github_url:
            urls.append(ctx.github_url.strip())

        code_urls = [p for p in ctx.raw_code_paths if p.startswith(("http://", "https://", "git@"))]
        urls.extend(code_urls)
        ctx.raw_code_paths = [p for p in ctx.raw_code_paths if p not in code_urls]

        # Deduplicate
        seen = set()
        clean = []
        for u in urls:
            u = u.rstrip("/").removesuffix(".git")
            if u and u not in seen:
                seen.add(u)
                clean.append(u)

        if not clean:
            self.log(ctx, "No Git repository URLs found to ingest.")
            return

        for url in clean:
            self.log(ctx, f"Found Git repository URL: {url}. Cloning...")
            try:
                temp_dir = tempfile.mkdtemp(prefix="git_ingest_")
                result = subprocess.run(
                    ["git", "clone", "--depth", "1", url, temp_dir],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode == 0:
                    self.log(ctx, f"Successfully cloned {url} to {temp_dir}")
                    ctx.raw_code_paths.append(temp_dir)
                else:
                    self.log(ctx, f"Failed to clone {url}: {result.stderr}", level="ERROR")
            except Exception as e:
                self.log(ctx, f"Error during git clone: {e}", level="ERROR")
