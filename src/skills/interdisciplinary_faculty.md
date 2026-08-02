---
name: interdisciplinary_faculty
description: "Specialized autonomous research skill protocol to process and synthesize academic faculty profile data for inclusion in the research literature pipeline. Parses CVs, publication profiles, and administrative records to structure papers, projects, talks, and admin roles into a unified JSON schema. Specially designed to bridge interdisciplinary skill sets (e.g., Physics/Electronics + Computer Science/ML) to ensure institutional and expertise-based grounding in research synthesis."
license: MIT
metadata:
  version: 1.0.0
  build_pattern: "Autonomous Faculty Parsing Loop"
---

# Interdisciplinary Faculty Profile Analyzer

This skill is designed for the `FacultyAgent` (or equivalent) in the Research Pipeline (Layer 3) to process raw academic CVs and publication texts, extracting highly structured artifacts.

## Core Objective
Convert unstructured academic faculty CVs and publication lists into structured, interdisciplinary research profiles.

## Parsing Protocol

When processing a faculty profile or CV, you MUST extract the following information into a strictly typed JSON structure.

1. **Identity & Core Competencies**:
   - Name, Designation, Department, Contact info.
   - Core research domains (e.g., "Physics", "Material Sciences", "Computer Science", "Machine Learning").
   - A unified summary of their interdisciplinary overlap (e.g., "Applying Machine Learning to Electronic Nose Gas Sensors").

2. **Academic & Administrative Roles**:
   - Committees, Convener roles, Coordinator positions.
   - Dates and descriptions of administrative impact.

3. **Projects & Grants**:
   - Title of project.
   - Funding agency and amount.
   - Duration / Year.
   - Principal Investigator (PI) or Co-PI status.

4. **Publications & Research Literature**:
   - Extract a list of all papers.
   - Title, Authors, Journal/Conference, Year, DOI/Link.
   - Explicitly tag interdisciplinary overlaps (e.g., bridging hardware/sensors with software/algorithms).

5. **Talks & Presentations**:
   - Title, Event, Date, Location.

## Interdisciplinary Synthesis Rule
When multiple faculty members (e.g., Prof. Arijit Chowdhuri and Prof. Sunita Narang) or multiple disparate fields are presented:
- Cross-reference their joint publications.
- Identify the exact intersection of their expertise (e.g., Hardware Sensors + ML Algorithms).
- Generate a `collaboration_matrix` highlighting how their distinct skill sets complement each other.

## Output Format
Always output the parsed data in the following JSON schema:
```json
{
  "faculty_name": "Full Name",
  "department": "Department",
  "primary_domains": ["Physics", "Material Science"],
  "interdisciplinary_summary": "Summary of cross-domain research...",
  "administrative_roles": [
    {"role": "Convener", "committee": "Admissions", "year": "2020-2022"}
  ],
  "projects": [
    {"title": "...", "funding_agency": "...", "amount": "...", "year": "..."}
  ],
  "publications": [
    {"title": "...", "authors": ["..."], "journal": "...", "year": 2021, "tags": ["E-Nose", "Sensors"]}
  ],
  "talks": [
    {"title": "...", "event": "...", "year": 2019}
  ],
  "collaboration_matrix": {
    "joint_papers": [...],
    "synergy_description": "..."
  }
}
```

## Execution Directives
- DO NOT hallucinate publications. Only extract what is present in the provided text.
- Normalize years and funding amounts where possible.
- If text is truncated, extract as much as possible and add a `"_metadata": {"truncated": true}` flag.
