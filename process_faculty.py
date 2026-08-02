import os
import json
import asyncio
from pathlib import Path

# Adjust path if necessary depending on the project structure
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agents.base_agent import BaseAgent
from src.core.models import PipelineContext, AgentMessage, PipelineStage
from src.core.llm_client import LocalLLMClient

from src.core.event_bus import SupervisorBus

class FacultyProfileAgent(BaseAgent):
    def __init__(self, bus: SupervisorBus):
        super().__init__("FacultyProfileAgent", 3, bus)
        self.skill_file = "interdisciplinary_faculty.md"

    def run(self, context: PipelineContext):
        self.context = context
        self.context.logs.append(
            AgentMessage(self.name, 3, "Starting Faculty Profile parsing sequence.")
        )
        
        skill_path = Path("src/skills") / self.skill_file
        if skill_path.exists():
            with open(skill_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()
        else:
            system_prompt = "You are an interdisciplinary researcher."
        raw_cv_text = self.context.raw_topic  # We pass the CV text in raw_topic for this standalone run

        prompt = f"""
You are the FacultyProfileAgent. Using your skill protocol, parse the following academic CVs and publication records into a structured JSON format.

RAW CV DATA:
{raw_cv_text}

Ensure the output is ONLY valid JSON as per your schema. Do not include markdown formatting like ```json.
"""
        
        self.context.logs.append(
            AgentMessage(self.name, 3, "Sending CV text to LLM for structured parsing.")
        )
        
        response = self.llm.generate(prompt=prompt, system_prompt=system_prompt)
        
        # Clean up JSON if it has markdown formatting or conversational text
        start_idx = response.find("{")
        end_idx = response.rfind("}")
        
        if start_idx != -1 and end_idx != -1:
            clean_json = response[start_idx:end_idx + 1]
        else:
            clean_json = response
            
        try:
            parsed_data = json.loads(clean_json)
            
            # Save the parsed data to the research artifacts directory
            output_dir = Path("output/faculty_profiles")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            faculty_name = parsed_data.get("faculty_name", "Unknown_Faculty").replace(" ", "_")
            file_path = output_dir / f"{faculty_name}_profile.json"
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(parsed_data, f, indent=4)
                
            self.context.logs.append(
                AgentMessage(self.name, 3, f"Successfully saved faculty profile to {file_path}")
            )
            print(f"✅ Successfully parsed and saved profile for {faculty_name} at {file_path}")
            
            return parsed_data
            
        except json.JSONDecodeError as e:
            self.context.errors.append(f"FacultyProfileAgent failed to parse JSON: {e}")
            print(f"❌ Failed to parse JSON from LLM response:\n{response}")
            return None


if __name__ == "__main__":
    # Test text based on user's truncated CV dump
    cv_text = """
    Professor First Name Arijit Last Name Chowdhuri
    Designation Professor in Physics
    Address Department of Physics, Acharya Narendra Dev College (University of Delhi), Govindpuri, Kalkaji, New Delhi – 110 019 INDIA
    Email arijitchowdhuri@andc.du.ac.in
    
    Educational Qualifications:
    Ph.D. Material Sciences (Experimental) Department of Physics & Astrophysics, University of Delhi, 2003
    
    Dr. Arijit Chowdhuri is a Professor in the Department of Physics. He has worked on Gas Sensors, Electronic Nose, and Air Pollution monitoring.
    
    Prof. Sunita Narang
    Department of Computer Science
    Ph.D. Financial Derivatives, Recommender Systems, Cybersecurity, E-nose.
    
    Joint Publications:
    "Low cost ‘Smart’ switch for designing Electronic Nose (E-Nose) for gas sensing applications" - Chowdhuri A., Narang S., 2021
    "Using mobile phones with android OS for measuring hazardous gas concentrations detected using Electronic Nose (E-Nose)" - Prayas Tiwari, Ashish Pokhriyal, Pankaj Rawat, Charu K. Gupta, Sunita Narang and Arijit Chowdhuri, 2022
    
    Administrative Roles (Arijit Chowdhuri):
    Convener, Admissions Committee, 2020-2022
    """
    
    from src.core.event_bus import SupervisorBus
    
    ctx = PipelineContext(
        job_id="faculty-test-1",
        raw_topic=cv_text,
        stage=PipelineStage.RESEARCH_GROUNDING
    )
    
    bus = SupervisorBus()
    agent = FacultyProfileAgent(bus)
    result = agent.run(ctx)
    
    if result:
        print(json.dumps(result, indent=2))
