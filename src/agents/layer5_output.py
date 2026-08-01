import os
from src.agents.base_agent import BaseAgent
from src.core.event_bus import SupervisorBus
from src.core.models import PipelineContext
from src.exporters.bibtex_exporter import BibTeXExporter
from src.exporters.pdf_exporter import PDFExporter
from src.exporters.pptx_exporter import PPTXExporter


SYSTEM_PROMPTS = {
    "Abstract": """You are an expert academic writer specializing in research paper abstracts.
A great abstract covers EXACTLY these 4 parts in order:
  1. The real-world problem and why it matters
  2. The limitation of existing approaches (gap)
  3. Your approach / method in concrete terms
  4. Key quantitative results + broader significance
Rules:
- Never start with "In this paper, we..." — that is a cliché
- Every sentence must contain new information — zero filler
- No citations in the abstract
- End with the practical impact or significance""",
    "Introduction": """You are an expert academic writer for research paper introductions.
Structure the Introduction as 5 clear moves:
  1. Hook — open with real-world impact or a striking statistic (2–3 sentences)
  2. Problem — define the precise technical challenge (3–4 sentences)
  3. Gap — explain what prior work does NOT solve, and why (3–4 sentences)
  4. Contribution — list this paper's specific contributions as bullet points
  5. Paper organization — one short paragraph outlining sections
Rules:
- Cite literature as (Author et al., Year) wherever relevant
- Be specific — no vague statements like "deep learning is widely used"
- The contribution list should be 3–5 concrete, measurable items""",
    "Literature Review": """You are an expert researcher writing a literature review for an academic paper.
DO NOT summarize papers one by one — that is a weak lit review.
Instead, organize THEMATICALLY:
  • Group related works into 3–5 thematic clusters
  • For each cluster: describe the shared approach, cite key papers, then state the shared limitation
  • Final paragraph: synthesize all limitations into the research gap THIS paper fills
Rules:
- Use transitional phrases: "Building on this...", "In contrast...", "While X achieves..., it fails to..."
- Every cluster must end with a critique / limitation
- The gap paragraph must connect directly to the paper's contribution
- Cite as (Author et al., Year)""",
    "Proposed Method / Methodology": """You are an expert technical writer describing research methodology.
Include ALL of these subsections:
  1. Overview — one paragraph high-level description of the approach
  2. Dataset / Experimental Setup — sources, size, splits, preprocessing
  3. Model / System Architecture — specific components, parameters, dimensions
  4. Training Procedure — optimizer, learning rate, epochs, hardware
  5. Evaluation Metrics — which metrics, why chosen, how computed
Rules:
- Be SPECIFIC — exact numbers, model sizes, hyperparameters
- A reader should be able to reproduce your experiment
- Avoid vague terms like "appropriate" or "suitable parameters" """,
    "Results": """You are an expert at presenting experimental results in academic papers.
Structure as:
  1. Main Results — compare against all baselines with specific numbers
  2. Ablation Study — what happens when components are removed
  3. Error Analysis — where does the model fail and why
  4. Qualitative Examples — 1–2 concrete case illustrations
Rules:
- Always give numbers: percentages, F1 scores, latency, etc.
- Explain WHY results are good/bad — not just what they are
- Reference tables/figures as "Table 1", "Figure 2" etc.
- Be honest about cases where your method underperforms""",
    "Discussion": """You are an expert academic writer for research paper discussion sections.
Cover these points:
  1. Interpretation — what do the results really mean?
  2. Connection to research questions — directly answer the questions from the intro
  3. Surprising findings — anything unexpected, with a hypothesis for why
  4. Limitations — be specific and honest (not vague disclaimers)
  5. Broader implications — what does this mean for the field?
Rules:
- Do not repeat results — interpret and contextualize them
- Connect back to the literature review: how does this advance the field?""",
    "Conclusion": """You are an expert at writing tight, effective research paper conclusions.
Structure:
  1. Restate problem + approach (2 sentences max — do not copy from abstract)
  2. Summarize key contributions (match what was claimed in Introduction)
  3. Honest limitations (1–2 sentences)
  4. Future work — SPECIFIC directions, not "we plan to extend to more domains"
Rules:
- Maximum 300 words — be crisp
- Do NOT introduce new results or claims
- Do NOT copy sentences from the Abstract"""
}

DEFAULT_SYSTEM_PROMPT = "You are an elite academic researcher and tenured professor. Write strictly in IEEE/ACM academic journal format. Be exhaustive, mathematically rigorous, and highly analytical."

def _generate_section_content(agent: BaseAgent, ctx: PipelineContext, section_name: str, section_topics: str, system_prompt: str, user_existing_text: str = None) -> str:
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
        return _generate_section_content(self, ctx, "Abstract", section_topics, SYSTEM_PROMPTS["Abstract"], user_existing_text)

class IntroductionAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("IntroductionAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, "Drafting Introduction...")
        return _generate_section_content(self, ctx, "Introduction", section_topics, SYSTEM_PROMPTS["Introduction"], user_existing_text)

class LiteratureReviewAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("LiteratureReviewAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, "Drafting Literature Review...")
        return _generate_section_content(self, ctx, "Literature Review", section_topics, SYSTEM_PROMPTS["Literature Review"], user_existing_text)

class MethodologyAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("MethodologyAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, "Drafting Proposed Method / Methodology...")
        return _generate_section_content(self, ctx, "Proposed Method / Methodology", section_topics, SYSTEM_PROMPTS["Proposed Method / Methodology"], user_existing_text)

class ResultsAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("ResultsAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, "Drafting Results...")
        return _generate_section_content(self, ctx, "Results", section_topics, SYSTEM_PROMPTS["Results"], user_existing_text)

class DiscussionAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("DiscussionAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, "Drafting Discussion...")
        return _generate_section_content(self, ctx, "Discussion", section_topics, SYSTEM_PROMPTS["Discussion"], user_existing_text)

class ConclusionAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("ConclusionAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, "Drafting Conclusion...")
        return _generate_section_content(self, ctx, "Conclusion", section_topics, SYSTEM_PROMPTS["Conclusion"], user_existing_text)

class GenericSectionAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("GenericSectionAgent", layer=5, bus=bus)
    def run(self, ctx: PipelineContext, section_name: str, section_topics: str, user_existing_text: str = None) -> str:
        self.log(ctx, f"Drafting {section_name}...")
        return _generate_section_content(self, ctx, section_name, section_topics, DEFAULT_SYSTEM_PROMPT, user_existing_text)

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

