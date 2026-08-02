import csv
import json
import hashlib
import ipaddress
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
import socket
import time
import tempfile
import os
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from src.agents.base_agent import BaseAgent
from src.core.event_bus import SupervisorBus
from src.core.models import PipelineContext, CitationItem
from src.core.skills_loader import load_skill_prompt, faculty_skill_addendum, select_research_skill
from src.core.llm_utils import strip_code_fence

class ResearchFindings(BaseModel):
    findings: List[str] = Field(description="List of key research findings")


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects whose target fails the same SSRF validation."""

    def __init__(self, validator):
        super().__init__()
        self.validator = validator

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not self.validator(newurl):
            raise urllib.error.HTTPError(newurl, 403, "Unsafe redirect target", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

import chromadb

class ArXivAgent(BaseAgent):
    _METADATA_HOSTS = {
        "metadata.google.internal",
        "metadata.aws.internal",
        "instance-data.ec2.internal",
    }

    def __init__(self, bus: SupervisorBus):
        super().__init__("ArXivAgent", layer=3, bus=bus)
        
        # Semantic Cache setup via ChromaDB
        self.chroma_path = os.path.expanduser("~/.arc_arxiv_chroma")
        try:
            self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
            self.collection = self.chroma_client.get_or_create_collection(
                name="arxiv_semantic_cache",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            self.collection = None

    def _load_cache(self, topic: str, threshold: float = 0.15) -> List[CitationItem]:
        if not self.collection: return []
        try:
            results = self.collection.query(
                query_texts=[topic],
                n_results=1
            )
            if results['distances'] and len(results['distances'][0]) > 0:
                distance = results['distances'][0][0]
                # distance is typically 1 - cosine similarity. 
                # If distance < threshold (0.15), the queries are very semantically similar.
                if distance < threshold:
                    papers_json = results['metadatas'][0][0].get("papers", "[]")
                    papers_list = json.loads(papers_json)
                    return [CitationItem(**item) for item in papers_list]
        except Exception:
            pass
        return []

    def _save_cache(self, topic: str, papers: List[CitationItem]) -> None:
        if not self.collection: return
        try:
            papers_json = json.dumps([p.__dict__ for p in papers])
            topic_id = hashlib.md5(topic.encode()).hexdigest()
            self.collection.upsert(
                documents=[topic],
                metadatas=[{"papers": papers_json}],
                ids=[topic_id]
            )
        except Exception:
            pass

    def is_safe_url(self, url: str) -> bool:
        """Allow only public HTTP(S) hosts after resolving every address."""
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        hostname = hostname.rstrip(".").lower()
        if hostname in {"localhost", *self._METADATA_HOSTS}:
            return False
        try:
            addresses = {
                info[4][0]
                for info in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
            }
            if not addresses:
                return False
            for address in addresses:
                ip = ipaddress.ip_address(address)
                if (
                    ip.is_private
                    or ip.is_loopback
                    or ip.is_link_local
                    or ip.is_reserved
                    or ip.is_unspecified
                    or ip.is_multicast
                ):
                    return False
        except (socket.gaierror, ValueError):
            return False
        return True

    def _safe_urlopen(self, request: urllib.request.Request, timeout: int):
        if not self.is_safe_url(request.full_url):
            raise ValueError("SSRF blocked: unsafe URL")
        opener = urllib.request.build_opener(_SafeRedirectHandler(self.is_safe_url))
        return opener.open(request, timeout=timeout)

    def fetch_pdf_text(self, pdf_url: str) -> str:
        if not fitz:
            return ""
        try:
            req = urllib.request.Request(pdf_url, headers={'User-Agent': 'Mozilla/5.0'})
            with self._safe_urlopen(req, timeout=10) as response:
                pdf_data = response.read()
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(pdf_data)
                tmp_path = tmp.name
            
            text = ""
            try:
                doc = fitz.open(tmp_path)
                for page in doc:
                    text += page.get_text() + "\n"
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            
            # Truncate to avoid extreme token limits, keep first ~15,000 chars which contains intro/methodology
            return text[:15000]
        except Exception as e:
            return ""

    def run(self, ctx: PipelineContext) -> None:
        topic = ctx.raw_topic
        self.log(ctx, f"Querying ArXiv API for peer-reviewed papers matching '{topic}'...")
        
        cached_papers = self._load_cache(topic)
        if cached_papers:
            self.log(ctx, f"Semantic Cache HIT! Loaded {len(cached_papers)} papers instantly.")
            ctx.research.arxiv_papers = cached_papers
            return

        papers = []

        try:
            query = urllib.parse.quote(topic)
            url = f"http://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results=4"
            
            if not self.is_safe_url(url):
                raise ValueError("SSRF Blocked: Unsafe internal URL detected.")

            # Rate Limiting & Backoff Implementation
            xml_data = None
            for attempt in range(3):
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with self._safe_urlopen(req, timeout=5) as response:
                        xml_data = response.read()
                    break
                except Exception as net_e:
                    self.log(ctx, f"ArXiv API attempt {attempt+1} failed: {net_e}. Backing off...", level="WARN")
                    time.sleep(1.5 * (attempt + 1))
            
            if not xml_data:
                raise Exception("Max retries exceeded for ArXiv API.")

            root = ET.fromstring(xml_data)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}

            for idx, entry in enumerate(root.findall('atom:entry', ns)):
                title = entry.find('atom:title', ns).text.strip().replace("\n", " ")
                summary = entry.find('atom:summary', ns).text.strip().replace("\n", " ")
                authors = [a.find('atom:name', ns).text for a in entry.findall('atom:author', ns)]
                published = entry.find('atom:published', ns).text[:4]
                link = entry.find('atom:id', ns).text
                
                pdf_link = link.replace("abs", "pdf") + ".pdf"
                
                self.log(ctx, f"Fetching full-text PDF for {title[:30]}...")
                full_text = self.fetch_pdf_text(pdf_link)

                key = f"arxiv_{published}_{idx+1}"
                first_author_last = authors[0].split()[-1] if authors else "Author"
                bibtex = f"@article{{{first_author_last}{published},\n  title={{{title}}},\n  author={{{' and '.join(authors)}}},\n  journal={{arXiv preprint {link}}},\n  year={{{published}}}\n}}"

                papers.append(CitationItem(
                    key=key,
                    title=title,
                    authors=authors,
                    year=published,
                    journal_or_arxiv=f"arXiv:{link.split('/')[-1]}",
                    abstract=summary,
                    url=link,
                    bibtex=bibtex,
                    full_text=full_text
                ))

            self._save_cache(topic, papers)
            self.log(ctx, f"Successfully retrieved {len(papers)} papers live from ArXiv.")
        except Exception as e:
            papers = []
            warn = f"ArXiv API query failed/offline ({e}). No fabricated citations; papers list empty."
            self.log(ctx, warn, level="WARN")
            if warn not in ctx.errors:
                ctx.errors.append(warn)

        ctx.research.arxiv_papers = papers


class CSAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("CSAgent", layer=3, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Starting General Research Protocol for CS literature...")
        topic = ctx.raw_topic
        skill_key = select_research_skill(topic)
        # Prefer mapped Claude-plugin research skill; fall back to general_research flat/plugin
        system_prompt = load_skill_prompt(skill_key if skill_key != "research" else "general_research")
        self.log(ctx, f"CSAgent using skill map key: {skill_key}")
        slug = topic.replace(" ", "_")[:20].lower()
        work_dir = os.path.join(ctx.work_dir, "general_research", slug)
        os.makedirs(os.path.join(work_dir, "sources"), exist_ok=True)
        
        # Phase 1: Decompose
        self.log(ctx, "Phase 1: Decomposing into sub-questions...")
        decomp_prompt = f"Decompose this CS topic into 3 specific technical sub-questions: {topic}. Output JSON: {{\"sub_questions\": [\"q1\", \"q2\", \"q3\"]}}"
        decomp_res = self.llm.generate(prompt=decomp_prompt, system_prompt=system_prompt)
        
        try:
            decomp_res = strip_code_fence(decomp_res)
            sub_qs = json.loads(decomp_res).get("sub_questions", [topic])
        except Exception:
            sub_qs = [f"{topic} algorithms", f"{topic} system architecture", f"{topic} performance"]
            
        with open(os.path.join(work_dir, "plan.md"), "w") as f:
            f.write(f"# Sub-Questions\n" + "\n".join(f"- {q}" for q in sub_qs))
            
        # Phase 2 & 3: Search and Extract
        self.log(ctx, "Phase 2 & 3: Searching for CS literature...")
        collected_context = []
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                for i, q in enumerate(sub_qs):
                    self.log(ctx, f"CSAgent searching: {q}")
                    results = list(ddgs.text(q, max_results=2))
                    for j, r in enumerate(results):
                        source_id = f"cs_source_{i}_{j}"
                        content = f"Title: {r.get('title')}\nURL: {r.get('href')}\nContent: {r.get('body')}"
                        with open(os.path.join(work_dir, "sources", f"{source_id}.md"), "w") as sf:
                            sf.write(content)
                        collected_context.append(content)
        except Exception as e:
            self.log(ctx, f"CS search failed: {e}", level="WARN")

        # Phase 4 & 5: Synthesize
        self.log(ctx, "Phase 4 & 5: Synthesizing CS findings...")
        synthesis_prompt = f"Based on these sources:\n{collected_context}\n\nProvide 3 key CS technical findings. Output strict JSON: {{\"findings\": [\"finding1\", \"finding2\", \"finding3\"]}}"
        res = self.llm.generate(prompt=synthesis_prompt, system_prompt=system_prompt + "\n\nYou MUST return ONLY valid JSON.")
        
        try:
            res = strip_code_fence(res)
            data = ResearchFindings.model_validate_json(res)
            ctx.research.cs_context = data.findings
            with open(os.path.join(work_dir, "briefing.md"), "w") as f:
                f.write(json.dumps(data.findings, indent=2))
        except Exception:
            ctx.research.cs_context = ["Fallback CS context generated due to parsing error."]
            
        self.log(ctx, f"CS General Research Protocol complete. Saved to {work_dir}")


class ElectronicsAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("ElectronicsAgent", layer=3, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Evaluating hardware interface abstractions via LLM + skill prompt...")
        system_prompt = load_skill_prompt("system_architecture", fallback="generic")
        hw = ctx.code_analysis.hardware_mappings
        prompt = (
            f"Topic: {ctx.raw_topic}\nHardware mappings: {hw}\n"
            "Provide 3 concise electronics/hardware findings relevant to this system. "
            'Output JSON: {"findings": ["...", "...", "..."]}'
        )
        res = self.llm.generate(prompt=prompt, system_prompt=system_prompt + "\nReturn ONLY valid JSON.")
        try:
            res = strip_code_fence(res)
            data = ResearchFindings.model_validate_json(res)
            ctx.research.electronics_context = data.findings
        except Exception:
            ctx.research.electronics_context = []
            self.log(ctx, "ElectronicsAgent LLM parse failed; leaving electronics_context empty.", level="WARN")
        self.log(ctx, f"ElectronicsAgent findings: {len(ctx.research.electronics_context)}")


class LiteratureAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("LiteratureAgent", layer=3, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Starting Literature Review Protocol...")
        topic = ctx.raw_topic
        slug = topic.replace(" ", "_")[:20].lower()
        work_dir = os.path.join(ctx.work_dir, "litreview", slug)
        os.makedirs(os.path.join(work_dir, "papers"), exist_ok=True)
        
        system_prompt = load_skill_prompt("litreview") + faculty_skill_addendum(
            ctx.research.faculty_context or []
        )
        
        # Phase 1: Framework Selection
        self.log(ctx, "Phase 1: Selecting review framework (PICO/Decomposition)...")
        framework_prompt = f"Select a review framework for: {topic}. Output JSON: {{\"framework\": \"Decomposition\", \"sub_areas\": [\"Problem\", \"Solution\"]}}"
        fw_res = self.llm.generate(prompt=framework_prompt, system_prompt=system_prompt)
        try:
            fw_res = strip_code_fence(fw_res)
            fw_data = json.loads(fw_res)
            sub_areas = fw_data.get("sub_areas", ["Overview"])
        except Exception:
            sub_areas = ["Background", "Methodology"]
            
        with open(os.path.join(work_dir, "framework.md"), "w") as f:
            f.write(f"# Literature Framework\n" + "\n".join(f"- {sa}" for sa in sub_areas))

        # Phase 2: Targeted Searches
        self.log(ctx, "Phase 2 & 3: Targeted literature searches...")
        collected_papers = []
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                for i, sa in enumerate(sub_areas):
                    self.log(ctx, f"LitReview querying: {topic} {sa} research paper")
                    results = list(ddgs.text(f"{topic} {sa} research paper", max_results=2))
                    for j, r in enumerate(results):
                        paper_id = f"paper_{i}_{j}"
                        content = f"Title: {r.get('title')}\nURL: {r.get('href')}\nAbstract: {r.get('body')}"
                        with open(os.path.join(work_dir, "papers", f"{paper_id}.md"), "w") as sf:
                            sf.write(content)
                        collected_papers.append(content)
        except Exception as e:
            self.log(ctx, f"LitReview search failed: {e}", level="WARN")

        # Phase 3: Research Guide Synthesis
        self.log(ctx, "Phase 4: Synthesizing Academic Literature Guide...")
        synth_prompt = f"Synthesize these papers across the framework areas: {sub_areas}\n\nPapers:\n{collected_papers}\n\nOutput strict JSON: {{\"findings\": [\"Synthesis 1\", \"Synthesis 2\"]}}"
        res = self.llm.generate(prompt=synth_prompt, system_prompt=system_prompt + "\n\nYou MUST return ONLY valid JSON.")
        
        try:
            res = strip_code_fence(res)
            data = ResearchFindings.model_validate_json(res)
            ctx.research.literature_context = data.findings
            ctx.research.literature_summary = "\n".join(data.findings)
            with open(os.path.join(work_dir, "research_guide.md"), "w") as f:
                f.write(json.dumps(data.findings, indent=2))
        except Exception:
            self.log(ctx, "LitReview synthesis parsing failed.", level="WARN")
            ctx.research.literature_context = []

        self.log(ctx, f"LitReview Protocol complete. Artifacts saved in {work_dir}")


class GapFinder(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("GapFinder", layer=3, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Starting Deep Research Protocol (Multi-Phase Loop)...")
        topic = ctx.raw_topic
        slug = topic.replace(" ", "_")[:20].lower()
        
        # Phase 1: Setup working directory
        work_dir = os.path.join(ctx.work_dir, "deep_research", slug)
        os.makedirs(os.path.join(work_dir, "sources"), exist_ok=True)
        os.makedirs(os.path.join(work_dir, "findings"), exist_ok=True)
        
        system_prompt = load_skill_prompt("deep_research") + faculty_skill_addendum(
            ctx.research.faculty_context or []
        )
        
        # Phase 2: Plan
        self.log(ctx, "Phase 1 & 2: Reframing and Planning...")
        plan_prompt = f"Create a research plan for topic: {topic}. Output ONLY valid JSON: {{\"scope\": \"...\", \"hypotheses\": [\"H1\", \"H2\"], \"search_queries\": [\"q1\", \"q2\"]}}"
        plan_res = self.llm.generate(prompt=plan_prompt, system_prompt=system_prompt)
        
        search_queries = [f"{topic} missing research gaps"]
        try:
            plan_res = strip_code_fence(plan_res)
            plan_data = json.loads(plan_res)
            with open(os.path.join(work_dir, "plan.md"), "w") as f:
                f.write(f"# Plan\nScope: {plan_data.get('scope')}\nHypotheses: {plan_data.get('hypotheses')}")
            search_queries = plan_data.get('search_queries', search_queries)[:2]
        except Exception as e:
            self.log(ctx, f"Plan JSON parsing error: {e}. Using fallback queries.")
            
        # Phase 3 & 4: Search and Sources
        self.log(ctx, "Phase 3 & 4: Sourcing and Triangulation...")
        sources_csv_path = os.path.join(work_dir, "sources.csv")
        collected_context = []
        
        with open(sources_csv_path, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["ID", "Query", "Source_File"])
            
            try:
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    for i, q in enumerate(search_queries):
                        self.log(ctx, f"DeepResearch searching for: {q}")
                        results = list(ddgs.text(q, max_results=2))
                        for j, r in enumerate(results):
                            source_id = f"source_{i}_{j}"
                            source_file = os.path.join(work_dir, "sources", f"{source_id}.md")
                            content = f"Title: {r.get('title')}\nURL: {r.get('href')}\nContent: {r.get('body')}"
                            
                            with open(source_file, "w") as sf:
                                sf.write(content)
                            
                            writer.writerow([source_id, q, source_file])
                            collected_context.append(content)
            except Exception as e:
                self.log(ctx, f"DeepResearch sub-search failed: {e}", level="WARN")

        # Phase 5 & 6: Synthesis and Findings (JSON Output)
        self.log(ctx, "Phase 5 & 6: Synthesizing novelty gaps...")
        synthesis_prompt = f"Based on the planned hypotheses and these collected sources:\n{collected_context}\n\nIdentify 3 novel research gaps. Output strict JSON: {{\"findings\": [\"gap1\", \"gap2\"]}}"
        res = self.llm.generate(prompt=synthesis_prompt, system_prompt=system_prompt + "\n\nYou MUST return ONLY valid JSON.")
        
        try:
            res = strip_code_fence(res)
            data = ResearchFindings.model_validate_json(res)
            ctx.research.novelty_gaps = data.findings
            
            with open(os.path.join(work_dir, "findings", "gaps.md"), "w") as f:
                f.write(json.dumps(data.findings, indent=2))
                
        except Exception as e:
            self.log(ctx, f"GapFinder Synthesis JSON error: {e}")
            ctx.research.novelty_gaps = ["Gap 1: Missing formal verification.", "Gap 2: Unresolved edge cases."]
            
        self.log(ctx, f"Deep Research Protocol complete. All artifacts logically saved in {work_dir}")

class WebSearchAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("WebSearchAgent", layer=3, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Performing live web search for contextual grounding via DuckDuckGo...")
        try:
            from duckduckgo_search import DDGS
            
            results = []
            with DDGS() as ddgs:
                query = ctx.raw_topic
                self.log(ctx, f"Searching DuckDuckGo for: '{query}'...")
                
                for r in ddgs.text(query, max_results=5):
                    results.append(f"Source: {r.get('title')} ({r.get('href')})\nSnippet: {r.get('body')}")
            
            ctx.research.web_context.extend(results)
            self.log(ctx, f"Successfully retrieved {len(results)} live web search results.")
            
        except Exception as e:
            self.log(ctx, f"Live Web search failed: {e}.", level="WARN")

class FacultyProfileAgent(BaseAgent):
    """Loads institutional faculty JSON into ctx.research.faculty_context (LangGraph node).

    Does not invent profiles. Pre-build JSON via process_faculty / fetch_faculty (OpenAlex).
    """

    def __init__(self, bus: SupervisorBus):
        super().__init__("FacultyProfileAgent", layer=3, bus=bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Loading faculty profiles for institutional grounding...")
        profiles_dir = os.path.join(
            ctx.work_dir, "faculty_profiles"
        )
        if not os.path.exists(profiles_dir):
            self.log(
                ctx,
                "No faculty_profiles/ found. Optional pre-step: python src/utils/fetch_faculty.py",
                level="INFO",
            )
            return

        loaded = 0
        for filename in os.listdir(profiles_dir):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(profiles_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                summary = f"Profile: {data.get('faculty_name', '')} ({data.get('department', '')})\n"
                summary += f"Domains: {', '.join(data.get('primary_domains', []))}\n"
                summary += f"Interdisciplinary Overlap: {data.get('interdisciplinary_summary', '')}\n"
                if "collaboration_matrix" in data:
                    summary += (
                        f"Synergy: {data['collaboration_matrix'].get('synergy_description', '')}\n"
                    )
                if summary not in ctx.research.faculty_context:
                    ctx.research.faculty_context.append(summary)
                    loaded += 1
            except Exception as e:
                self.log(ctx, f"Failed to load faculty profile {filename}: {e}", level="WARN")

        self.log(ctx, f"FacultyProfileAgent loaded {loaded} profile(s).")


class ResearchOrchestrator(BaseAgent):
    """Executes Layer 3 research agents sequentially (thread-safe ctx writes)."""
    def __init__(self, bus: SupervisorBus):
        super().__init__("ResearchOrchestrator", layer=3, bus=bus)
        self.arxiv_agent = ArXivAgent(bus)
        self.web_agent = WebSearchAgent(bus)
        self.cs_agent = CSAgent(bus)
        self.electronics_agent = ElectronicsAgent(bus)
        self.lit_agent = LiteratureAgent(bus)
        self.gap_finder = GapFinder(bus)

    def run(self, ctx: PipelineContext) -> None:
        self.log(ctx, "Initializing Layer 3 Research Execution (sequential, merge-safe)...")

        for agent in (
            self.arxiv_agent,
            self.web_agent,
            self.cs_agent,
            self.electronics_agent,
            self.lit_agent,
            self.gap_finder,
        ):
            try:
                agent.run(ctx)
            except Exception as e:
                self.log(ctx, f"{agent.name} failed: {e}", level="WARN")
                ctx.errors.append(f"L3 {agent.name}: {e}")

        self.log(ctx, "Layer 3 Research Execution Complete.")
