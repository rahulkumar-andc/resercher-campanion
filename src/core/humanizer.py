import json
import re
import random
from typing import List

# These are imported locally so they don't break if not installed immediately
try:
    import nltk
    from nltk.tokenize import sent_tokenize
    import torch
    from transformers import GPT2LMHeadModel, GPT2Tokenizer
    import chromadb
except ImportError:
    nltk = None
    torch = None
    chromadb = None

from src.core.llm_client import LocalLLMClient

class RegexFilter:
    def __init__(self):
        # Common AI filler words to eliminate
        self.banned_phrases = {
            r"\b(delve|delving)\b": "explore",
            r"\b(crucial|vital)\b": "important",
            r"\b(testament to)\b": "evidence of",
            r"\b(in today's fast-paced world)\b": "",
            r"\b(moreover|furthermore)\b": "additionally",
            r"\b(groundbreaking)\b": "significant",
            r"\b(in conclusion)\b": "to summarize",
        }

    def filter(self, text: str) -> str:
        result = text
        for pattern, replacement in self.banned_phrases.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        # Clean up double spaces left by empty replacements
        return re.sub(r" +", " ", result).strip()

class BurstinessEngine:
    def _smart_split(self, sentence: str) -> List[str]:
        # A simple fallback for smart split
        parts = sentence.split(" and ", 1)
        if len(parts) == 2:
            return [parts[0] + ".", parts[1].capitalize()]
        return [sentence]

    def _smart_merge(self, s1: str, s2: str) -> str:
        s1 = s1.rstrip(".")
        s2 = s2[0].lower() + s2[1:]
        return f"{s1} and {s2}"
        
    def _extract_key_phrase(self, s: str) -> str:
        words = s.split()
        if len(words) > 3:
            return " ".join(words[:3]) + "."
        return "This is essential."

    def inject_burstiness(self, text: str) -> str:
        if nltk is None:
            return text
            
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)

        sentences = sent_tokenize(text)
        result = []
        i = 0
        
        while i < len(sentences):
            action = random.choices(
                ['keep', 'split', 'merge', 'fragment'],
                weights=[0.5, 0.2, 0.2, 0.1]
            )[0]
            
            if action == 'split' and len(sentences[i]) > 80:
                parts = self._smart_split(sentences[i])
                result.extend(parts)
            elif action == 'merge' and i+1 < len(sentences):
                merged = self._smart_merge(sentences[i], sentences[i+1])
                result.append(merged)
                i += 1
            elif action == 'fragment':
                result.append(self._extract_key_phrase(sentences[i]))
                result.append(sentences[i])
            else:
                result.append(sentences[i])
            i += 1
        return ' '.join(result)
    
    def measure_burstiness(self, text: str) -> float:
        if nltk is None: return 0.0
        sentences = sent_tokenize(text)
        lengths = [len(s.split()) for s in sentences]
        if not lengths: return 0.0
        
        mean = sum(lengths) / len(lengths)
        variance = sum((l-mean)**2 for l in lengths) / len(lengths)
        std_dev = variance ** 0.5
        burstiness = std_dev / mean if mean > 0 else 0
        return burstiness

class AdversarialHumanizer:
    def __init__(self, llm_client: LocalLLMClient):
        self.llm = llm_client
        self.DETECTOR_PROMPT = """You are an AI content detector.
Analyze this text and return ONLY a valid JSON object matching exactly this schema:
{
  "ai_phrases": ["list of AI-like phrases found"],
  "robotic_sections": ["list of robotic sentences"],
  "confidence_ai": 0-100,
  "specific_fixes": ["fix1", "fix2"]
}
Do not return any markdown wrapping or conversational text."""

        self.REWRITER_PROMPT = """You are a human writing expert.
Rewrite the provided text to resolve these AI-like patterns: {issues}
Make it sound natural, vary sentence structure, and use an empirical PhD-level tone.
Return ONLY the rewritten text."""

    def adversarial_loop(self, text: str, max_rounds: int = 2) -> str:
        current = text
        for round_num in range(max_rounds):
            detection_str = self.llm.generate(prompt=current, system_prompt=self.DETECTOR_PROMPT, temperature=0.1)
            try:
                # Strip backticks if LLM returns markdown json
                clean_json = detection_str.strip().strip("`").lstrip("json\n")
                detection = json.loads(clean_json)
                score = detection.get('confidence_ai', 100)
            except Exception:
                score = 50
                detection = {"specific_fixes": ["Vary sentence length", "Remove filler words"]}

            if score < 30:
                break
            
            prompt = self.REWRITER_PROMPT.format(issues='\\n'.join(detection.get('specific_fixes', [])))
            current = self.llm.generate(prompt=current, system_prompt=prompt, temperature=0.6)
        
        return current

class StyleEmbeddingMatcher:
    def __init__(self, llm_client: LocalLLMClient, your_documents: List[str] = None):
        self.llm = llm_client
        self.your_documents = your_documents or []
        self.collection = None
        if chromadb is not None:
            self.db = chromadb.Client()
            self.collection = self.db.create_collection("your_style")
            
            for i, doc in enumerate(self.your_documents):
                chunks = [doc[i:i+200] for i in range(0, len(doc), 200)]
                if chunks:
                    self.collection.add(
                        documents=chunks,
                        ids=[f"doc_{i}_{j}" for j in range(len(chunks))]
                    )

    def style_score(self, generated_text: str) -> float:
        if not self.collection or not self.your_documents:
            return 1.0 # Skip if no reference docs
        try:
            results = self.collection.query(query_texts=[generated_text], n_results=5)
            distances = results['distances'][0]
            if not distances: return 1.0
            similarity = max(0, 1 - (sum(distances) / len(distances)))
            return similarity
        except Exception:
            return 1.0

    def rewrite_to_match_style(self, text: str, threshold: float = 0.75) -> str:
        score = self.style_score(text)
        if score >= threshold or not self.collection:
            return text
            
        try:
            examples = self.collection.query(query_texts=[text], n_results=3)['documents'][0]
            rewrite_prompt = f"""Here are 3 examples of the target writing style:
EXAMPLE 1: {examples[0]}
EXAMPLE 2: {examples[1]}
EXAMPLE 3: {examples[2]}

Rewrite the following text EXACTLY in this style:
TEXT: {text}"""
            
            return self.llm.generate(prompt=rewrite_prompt, temperature=0.3)
        except Exception:
            return text

class PerplexityScorer:
    def __init__(self, llm_client: LocalLLMClient):
        self.llm = llm_client
        self.model = None
        self.tokenizer = None
        if torch is not None:
            try:
                # Load small gpt2 for quick local inference
                self.model = GPT2LMHeadModel.from_pretrained('gpt2')
                self.tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
                self.model.eval()
            except Exception:
                pass

    def score(self, text: str) -> float:
        if self.model is None or self.tokenizer is None:
            return 100.0 # Safe default
            
        try:
            tokens = self.tokenizer(text, return_tensors='pt', truncation=True, max_length=512)
            with torch.no_grad():
                loss = self.model(**tokens, labels=tokens['input_ids']).loss
            return torch.exp(loss).item()
        except Exception:
            return 100.0

    def boost_perplexity(self, text: str) -> str:
        if self.model is None or nltk is None:
            return text
            
        sentences = sent_tokenize(text)
        result = []
        for sent in sentences:
            p = self.score(sent)
            if p < 40:
                varied = self.llm.generate(
                    prompt=f"Rewrite this with a more natural, unpredictable structure, keeping the exact meaning: {sent}",
                    temperature=0.7
                )
                result.append(varied)
            else:
                result.append(sent)
        return ' '.join(result)

class HumanizerPipeline:
    """The master pipeline orchestration for human-level text anti-detection."""
    def __init__(self, llm_client: LocalLLMClient, user_style_docs: List[str] = None):
        self.regex = RegexFilter()
        self.burstiness = BurstinessEngine()
        self.adversarial = AdversarialHumanizer(llm_client)
        self.style = StyleEmbeddingMatcher(llm_client, user_style_docs)
        self.perplexity = PerplexityScorer(llm_client)

    def humanize(self, text: str) -> str:
        # Pass 1 - RegEx
        text = self.regex.filter(text)
        # Pass 2 - Burstiness
        text = self.burstiness.inject_burstiness(text)
        # Pass 3 - Perplexity Boost
        p_score = self.perplexity.score(text)
        if p_score < 50:
            text = self.perplexity.boost_perplexity(text)
        # Pass 4 - Style Match
        style_score = self.style.style_score(text)
        if style_score < 0.75:
            text = self.style.rewrite_to_match_style(text)
        # Pass 5 - Adversarial Polish
        text = self.adversarial.adversarial_loop(text, max_rounds=1)
        
        return text
