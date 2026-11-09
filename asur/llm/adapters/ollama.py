"""Local Ollama provider (stdlib ``urllib`` only, no third-party package).

Talks to a locally running Ollama server (https://ollama.com) via its HTTP API
``POST /api/generate`` with ``stream: false``. Nothing leaves the machine unless
``ASUR_OLLAMA_URL`` is pointed elsewhere.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .. import LLMError


class OllamaProvider:
    """``LLMProvider`` backed by a local Ollama server."""

    def __init__(self, model: str, *, base_url: str = "http://localhost:11434",
                 timeout_s: float = 120.0) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    @property
    def label(self) -> str:
        return f"llm:ollama/{self.model}"

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 1500) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "format": "json",
            "options": {"num_predict": max_tokens, "temperature": 0.7},
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise LLMError(f"ollama request to {self.base_url} failed: {exc}") from exc
        text = body.get("response") if isinstance(body, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise LLMError("ollama returned an empty response")
        return text
