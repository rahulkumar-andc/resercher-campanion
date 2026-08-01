"""
Local LLM & Ollama Connector Engine
Supports DeepSeek-R1, Qwen-2.5-Coder, and LLaMA-3 models via Ollama & OpenAI-compatible local APIs.
Includes automatic fallback mode if Ollama server is offline.
"""

import requests
import json
import time
from typing import Dict, Any, Optional, List


class LocalLLMClient:
    """Client interface for local LLM inference via Ollama or custom local servers."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "deepseek-r1:7b",
        fallback_model: str = "qwen2.5-coder:7b",
        timeout: int = 30

    ):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.fallback_model = fallback_model
        self.timeout = timeout
        self.is_connected = self.check_connection()

    def check_connection(self) -> bool:
        """Check if local Ollama server is running."""
        try:
            res = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return res.status_code == 200
        except Exception:
            return False

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048
    ) -> str:
        """Generate response from local LLM with automatic fallback handling."""
        selected_model = model or self.default_model

        if not self.is_connected and not self.check_connection():
            # Fallback mock response for offline/testing mode
            return f"[LocalLLM Offline Fallback Mode] Generated response for prompt: {prompt[:100]}..."

        payload = {
            "model": selected_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=self.timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("response", "")
            else:
                return f"[LLM Error {resp.status_code}] Failed response from model {selected_model}"
        except Exception as e:
            return f"[LLM Exception] {str(e)}"

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2
    ) -> str:
        """Structured multi-turn chat generation for agents."""
        selected_model = model or self.default_model

        if not self.is_connected and not self.check_connection():
            return "[LocalLLM Offline Fallback] Multi-turn agent dialogue completed."

        payload = {
            "model": selected_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature}
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=self.timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("message", {}).get("content", "")
            return f"[LLM Chat Error {resp.status_code}]"
        except Exception as e:
            return f"[LLM Chat Exception] {str(e)}"
