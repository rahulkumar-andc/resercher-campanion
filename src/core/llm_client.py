"""
Local LLM & Ollama Connector Engine

Policy (ARC):
- Default: ALL agents use LocalLLMClient (Ollama, llama3.1:latest).
- Writing only (Layer 5 section draft): optional Mistral cloud when CLOUD_LLM_API_KEY is set
  (see src/agents/layer5_output.py). Everything else stays local — no cloud calls here.
"""

import requests
import json
import os
from typing import Dict, Any, Optional, List


class LocalLLMClient:
    """Local-only LLM client via Ollama. Never calls cloud APIs."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        fallback_model: str = "qwen2.5-coder:7b",
        timeout: int = 300,
    ):
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.default_model = default_model or os.environ.get("ARC_LOCAL_MODEL", "llama3.1:latest")
        self.fallback_model = fallback_model
        self.timeout = timeout
        self.is_connected = self.check_connection()

    def check_connection(self) -> bool:
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
        max_tokens: int = 2048,
    ) -> str:
        selected_model = model or self.default_model

        if not self.is_connected and not self.check_connection():
            return f"[LocalLLM Offline Fallback Mode] Generated response for prompt: {prompt[:100]}..."

        payload = {
            "model": selected_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return resp.json().get("response", "")
            # One retry with fallback model
            if selected_model != self.fallback_model:
                return self.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model=self.fallback_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            return f"[LLM Error {resp.status_code}] Failed response from model {selected_model}"
        except Exception as e:
            return f"[LLM Exception] {str(e)}"

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        selected_model = model or self.default_model

        if not self.is_connected and not self.check_connection():
            return "[LocalLLM Offline Fallback] Multi-turn agent dialogue completed."

        payload = {
            "model": selected_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload),
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                return resp.json().get("message", {}).get("content", "")
            return f"[LLM Chat Error {resp.status_code}]"
        except Exception as e:
            return f"[LLM Chat Exception] {str(e)}"


def writing_cloud_enabled() -> bool:
    """True when Layer-5 section writing may use Mistral (CLOUD_LLM_API_KEY)."""
    flag = os.environ.get("ARC_WRITING_USE_CLOUD", "1").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    return bool(_resolve_cloud_api_key())


def _resolve_cloud_api_key() -> Optional[str]:
    key = os.environ.get("CLOUD_LLM_API_KEY")
    if key:
        return key
    try:
        from dotenv import dotenv_values
        return dotenv_values(".env").get("CLOUD_LLM_API_KEY")
    except ImportError:
        return None


def cloud_write_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 4000,
) -> Optional[str]:
    """
    Writing-only cloud call (Mistral). Returns None if disabled/unavailable.
    Must NOT be used by research/QA/code agents — those stay on LocalLLMClient.
    """
    if not writing_cloud_enabled():
        return None
    api_key = _resolve_cloud_api_key()
    if not api_key:
        return None
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": os.environ.get("ARC_WRITING_MODEL", "mistral-large-latest"),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        resp = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=180,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception:
        return None
    return None
