"""Anthropic API provider (lazy-imports the optional ``anthropic`` package).

Install with ``pip install 'asur[llm]'`` and set ``ANTHROPIC_API_KEY``. This is
the one opt-in path that sends the idea text to a hosted service; it is never
used unless ``ASUR_LLM=anthropic`` (or ``--llm anthropic``) is chosen explicitly.
"""

from __future__ import annotations

from typing import Any

from .. import DEFAULT_ANTHROPIC_MODEL, LLMError


class AnthropicProvider:
    """``LLMProvider`` backed by the Anthropic Messages API."""

    def __init__(self, model: str = DEFAULT_ANTHROPIC_MODEL, *, client: Any = None) -> None:
        self.model = model
        self._client = client

    @property
    def label(self) -> str:
        return f"llm:anthropic/{self.model}"

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise LLMError(
                    "the 'anthropic' package is not installed (pip install 'asur[llm]')"
                ) from exc
            try:
                self._client = anthropic.Anthropic()
            except Exception as exc:  # missing key, bad config
                raise LLMError(f"could not create Anthropic client: {exc}") from exc
        return self._client

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 1500) -> str:
        client = self._get_client()
        try:
            message = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # network, auth, rate limit: all fall back
            raise LLMError(f"anthropic request failed: {exc}") from exc
        parts = [getattr(block, "text", "") for block in getattr(message, "content", [])]
        text = "".join(p for p in parts if isinstance(p, str))
        if not text.strip():
            raise LLMError("anthropic returned no text content")
        return text
