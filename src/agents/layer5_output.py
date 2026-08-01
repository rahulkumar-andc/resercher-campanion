import os
from src.agents.base_agent import BaseAgent
from src.core.event_bus import SupervisorBus
from src.core.models import PipelineContext
from src.exporters.bibtex_exporter import BibTeXExporter
from src.exporters.pdf_exporter import PDFExporter
from src.exporters.pptx_exporter import PPTXExporter


def load_skill_prompt(skill_name: str) -> str:
    """Load the system prompt from the corresponding skill file."""
    skill_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills", f"{skill_name}.md")
    if not os.path.exists(skill_path):
        skill_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills", "generic.md")
    try:
        with open(skill_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

def _generate_section_content(agent: BaseAgent, ctx: PipelineContext, section_name: str, section_topics: str, skill_name: str, user_existing_text: str = None) -> str:
    system_prompt = load_skill_prompt(skill_name)
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

    if api_key:
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
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
                return resp.json()["choices"][0]["message"]["content"]
            else:
                agent.log(ctx, f"Cloud API Error on {section_name}: {resp.status_code}. Skipping.", level="WARN")
        except Exception as e:
            agent.log(ctx, f"Deep synthesis failed: {e}. Falling back to single-pass.", level="WARN")

    fallback_prompt = f"{system_prompt}\n\n{section_prompt}"
    return agent.llm.generate(prompt=fallback_prompt, system_prompt=system_prompt, temperature=0.3, max_tokens=3000)

# --- EXPLICIT 8-10 SECTION AGENTS ---

class AbstractAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("AbstractAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, "Drafting Abstract...")
        return _generate_section_content(self, ctx, "Abstract", section_topics, "abstract", user_existing_text)

class IntroductionAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("IntroductionAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, "Drafting Introduction...")
        return _generate_section_content(self, ctx, "Introduction", section_topics, "introduction", user_existing_text)

class LiteratureReviewAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("LiteratureReviewAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, "Drafting Literature Review...")
        return _generate_section_content(self, ctx, "Literature Review", section_topics, "literature_review", user_existing_text)

class MethodologyAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("MethodologyAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, "Drafting Proposed Method / Methodology...")
        return _generate_section_content(self, ctx, "Proposed Method / Methodology", section_topics, "methodology", user_existing_text)

class ResultsAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("ResultsAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, "Drafting Results...")
        return _generate_section_content(self, ctx, "Results", section_topics, "results", user_existing_text)

class DiscussionAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("DiscussionAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, "Drafting Discussion...")
        return _generate_section_content(self, ctx, "Discussion", section_topics, "discussion", user_existing_text)

class ConclusionAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("ConclusionAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, "Drafting Conclusion...")
        return _generate_section_content(self, ctx, "Conclusion", section_topics, "conclusion", user_existing_text)

class GenericSectionAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("GenericSectionAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_name: str, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, f"Drafting {section_name}...")
        return _generate_section_content(self, ctx, section_name, section_topics, "generic", user_existing_text)

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
            "Conclusion": ConclusionAgent(bus)
        }
        self.generic_agent = GenericSectionAgent(bus)

    def run(self, ctx: PipelineContext, output_dir: str = "./output") -> None:
        self.log(ctx, "Drafting full manuscript markdown using autonomous LLM synthesis...")
        topic = ctx.raw_topic
        outline = ctx.synthesis.outline
        
        target_section = getattr(ctx, 'target_section', None)
        user_existing_text = getattr(ctx, 'user_existing_text', None)
        
        if target_section:
            self.log(ctx, f"Targeted generation requested for section: {target_section}")
            
            section_topics = ""
            for s in outline:
                if s['section'] == target_section:
                    section_topics = ", ".join(s['topics'])
                    break
                    
            if target_section in self.agents:
                content = self.agents[target_section].run(ctx, section_topics, user_existing_text)
            else:
                content = self.generic_agent.run(ctx, target_section, section_topics, user_existing_text)
            
            if user_existing_text:
                final_content = user_existing_text + " " + content
            else:
                final_content = content
                
            ctx.output.markdown_manuscript = f"## {target_section}\n\n{final_content}"
            self.log(ctx, f"Targeted generation for {target_section} completed ({len(ctx.output.markdown_manuscript)} chars).")
            return
            
        self.log(ctx, "Initiating DEEP MULTI-PASS ACADEMIC SYNTHESIS with specialized agents...")
        
        full_manuscript = f"# {topic}\n\n"
        
        for section_dict in outline:
            section_title = section_dict['section']
            section_topics = ", ".join(section_dict['topics'])
            
            import re
            base_title = re.sub(r'^\d+\.\s*', '', section_title).strip()
            
            if base_title in self.agents:
                section_content = self.agents[base_title].run(ctx, section_topics, user_existing_text=None)
            else:
                section_content = self.generic_agent.run(ctx, section_title, section_topics, user_existing_text=None)
            
            full_manuscript += f"\n\n## {section_title}\n\n{section_content}"
            
        self.log(ctx, "Multi-agent synthesis completed successfully.")

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

