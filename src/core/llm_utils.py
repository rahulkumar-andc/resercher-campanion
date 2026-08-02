"""Small normalization helpers for LLM responses."""


def strip_code_fence(text: str) -> str:
    """Return response text without one leading Markdown code fence."""
    text = text or ""
    if text.startswith("```json"):
        return text[7:].rsplit("```", 1)[0].strip()
    if text.startswith("```"):
        return text[3:].rsplit("```", 1)[0].strip()
    return text.strip()
