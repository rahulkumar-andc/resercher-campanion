"""
Skill prompt loader for ARC.

Resolution order for load_skill_prompt(name):
1. Claude-plugin SKILL.md (mapped path under src/skills/research* or research-ops)
2. Flat src/skills/{name}.md
3. fallback skill / generic string

Claude plugin skills as local LLM prompts
---------------------------------------
YES — the SKILL.md *text* can be used as a system prompt for Ollama/local models.
NO  — Claude Code–only pieces do not auto-run on local LLM:
      - MCP tools, bash_tool, interactive grill-me, Node docx packaging,
        Consensus MCP, CLI agents under .claude-plugin/
Those need Claude Code (or separate script invocation). ARC maps prompts only;
search/synthesis is implemented in Python agents (DDG/ArXiv/OpenAlex).
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

_SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")

# Local models have limited context — keep plugin bodies bounded.
_DEFAULT_MAX_CHARS = 12000

# Claude-plugin SKILL.md relative to src/skills/
PLUGIN_SKILL_MAP: Dict[str, str] = {
    # Core research pack
    "litreview": "research/litreview/skills/litreview/SKILL.md",
    "deep_research": "research/deep-research/skills/deep-research/SKILL.md",
    "dossier": "research/dossier/skills/dossier/SKILL.md",
    "patent": "research/patent/skills/patent/SKILL.md",
    "pulse": "research/pulse/skills/pulse/SKILL.md",
    "grants": "research/grants/skills/grants/SKILL.md",
    "notebooklm": "research/notebooklm/skills/notebooklm/SKILL.md",
    "syllabus": "research/syllabus/skills/syllabus/SKILL.md",
    "research": "research/research/skills/research/SKILL.md",
    "general_research": "research/research/skills/research/SKILL.md",
    # Research-ops pack
    "clinical_research": "research-ops/skills/clinical-research/SKILL.md",
    "market_research": "research-ops/skills/market-research/SKILL.md",
    "product_research": "research-ops/skills/product-research/SKILL.md",
    "research_finance": "research-ops/skills/research-finance/SKILL.md",
    "research_ops": "research-ops/skills/research-ops-skills/SKILL.md",
}

# Aliases → canonical map keys / flat names
_ALIASES: Dict[str, str] = {
    "literature_review": "litreview",
    "lit_review": "litreview",
    "deep-research": "deep_research",
    "autoresearch": "deep_research",
    "clinical-research": "clinical_research",
    "market-research": "market_research",
    "product-research": "product_research",
    "research-finance": "research_finance",
    "research-ops": "research_ops",
}

_LOCAL_LLM_PREAMBLE = (
    "\n\n--- ARC RUNTIME ADAPTER (local / autonomous) ---\n"
    "You are running inside the Autonomous Research Companion pipeline, not Claude Code.\n"
    "Ignore interactive grill-me pauses, MCP/Consensus checks, bash_tool, and .docx packaging.\n"
    "Produce concise structured findings the calling agent can parse (prefer JSON when asked).\n"
    "Do not invent citations; only use facts provided in the user prompt / search results.\n"
)


def list_mapped_plugin_skills() -> List[Tuple[str, str, bool]]:
    """Return (name, relative_path, file_exists) for all mapped plugins."""
    out = []
    for name, rel in sorted(PLUGIN_SKILL_MAP.items()):
        path = os.path.join(_SKILLS_DIR, rel)
        out.append((name, rel, os.path.exists(path)))
    return out


def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return (
        text[:max_chars]
        + "\n\n[... skill truncated for local LLM context; full text in plugin SKILL.md ...]\n"
    )


def _normalize(skill_name: str) -> str:
    key = (skill_name or "").strip().lower().replace(" ", "_")
    return _ALIASES.get(key, key)


def load_plugin_skill(skill_name: str, max_chars: int = _DEFAULT_MAX_CHARS) -> Optional[str]:
    """Load mapped Claude-plugin SKILL.md if present."""
    key = _normalize(skill_name)
    rel = PLUGIN_SKILL_MAP.get(key)
    if not rel:
        return None
    path = os.path.join(_SKILLS_DIR, rel)
    if not os.path.exists(path):
        return None
    body = _truncate(_read_file(path), max_chars)
    return body + _LOCAL_LLM_PREAMBLE


def load_flat_skill(skill_name: str) -> Optional[str]:
    key = _normalize(skill_name)
    path = os.path.join(_SKILLS_DIR, f"{key}.md")
    if os.path.exists(path):
        return _read_file(path)
    # original casing filename
    path2 = os.path.join(_SKILLS_DIR, f"{skill_name}.md")
    if os.path.exists(path2):
        return _read_file(path2)
    return None


def load_skill_prompt(
    skill_name: str,
    fallback: Optional[str] = None,
    prefer_plugin: bool = True,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> str:
    """
    Load skill text for an agent.

    prefer_plugin=True (default): Claude plugin SKILL.md first, then flat .md.
    """
    key = _normalize(skill_name)

    if prefer_plugin:
        plugin = load_plugin_skill(key, max_chars=max_chars)
        if plugin:
            return plugin

    flat = load_flat_skill(key) or load_flat_skill(skill_name)
    if flat:
        return flat

    if fallback:
        return load_skill_prompt(fallback, fallback=None, prefer_plugin=prefer_plugin, max_chars=max_chars)

    return f"You are a specialized agent for {skill_name}."


def faculty_skill_addendum(faculty_context: list) -> str:
    """Append interdisciplinary faculty guidance when institutional profiles exist."""
    if not faculty_context:
        return ""
    base = load_skill_prompt("interdisciplinary_faculty", prefer_plugin=False)
    profiles = "\n".join(faculty_context)
    return (
        f"\n\n--- FACULTY GROUNDING ADDENDUM ---\n{base}\n\n"
        f"INSTITUTIONAL PROFILES:\n{profiles}\n"
    )


def select_research_skill(topic: str) -> str:
    """Heuristic: pick a plugin skill key from topic keywords."""
    t = (topic or "").lower()
    rules = [
        (("patent", "ip ", "prior art", "cpc"), "patent"),
        (("grant", "nih", "funding", "r01"), "grants"),
        (("clinical", "trial", "patient", "protocol"), "clinical_research"),
        (("market", "tam", "sam", "competitor"), "market_research"),
        (("product research", "user interview", "ux research"), "product_research"),
        (("budget", "burn rate", "runway", "finance"), "research_finance"),
        (("dossier", "company profile", "due diligence"), "dossier"),
        (("syllabus", "course", "curriculum"), "syllabus"),
        (("pulse", "news", "trend watch"), "pulse"),
        (("literature", "lit review", "related work"), "litreview"),
        (("deep research", "novelty", "research gap"), "deep_research"),
    ]
    for keywords, skill in rules:
        if any(k in t for k in keywords):
            return skill
    return "research"
