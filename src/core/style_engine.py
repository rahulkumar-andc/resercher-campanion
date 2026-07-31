import re
from typing import Dict, Any


class StyleEngine:
    """Analyzes and extracts user writing style fingerprints and enforces style parameters."""

    @staticmethod
    def extract_fingerprint(sample_text: str) -> Dict[str, Any]:
        if not sample_text or len(sample_text.strip()) == 0:
            return {
                "academic_tone": "Formal/Technical",
                "sentence_length": "Medium",
                "vocabulary_density": "High",
                "citation_preference": "IEEE",
                "use_active_voice": True,
            }

        sentences = re.split(r'[.!?]+', sample_text)
        sentences = [s.strip() for s in sentences if s.strip()]
        avg_len = sum(len(s.split()) for s in sentences) / max(1, len(sentences))

        words = sample_text.lower().findall(r'\b[a-z]{4,}\b') if hasattr(sample_text.lower(), 'findall') else re.findall(r'\b[a-z]{4,}\b', sample_text.lower())
        vocab_density = len(set(words)) / max(1, len(words))

        tone = "Formal/Academic" if vocab_density > 0.4 else "Informal/Direct"
        length_style = "Long/Complex" if avg_len > 22 else ("Short/Direct" if avg_len < 12 else "Medium/Balanced")

        return {
            "academic_tone": tone,
            "sentence_length": length_style,
            "vocabulary_density": f"{vocab_density:.2f}",
            "avg_words_per_sentence": round(avg_len, 1),
            "citation_preference": "IEEE",
            "use_active_voice": True,
        }
