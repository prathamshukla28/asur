"""Optional LLM drafting step for the SCRIPT stages (stdlib-only interface).

ASUR's SCRIPT stages (research, audience, hooks, script) have two generators:

  * ``template`` - the deterministic, offline f-string templates. Always
    available, byte-reproducible, and the fallback whenever an LLM is not
    configured or its output fails validation.
  * ``llm:<model>`` - a real language model behind the small :class:`LLMProvider`
    interface. Two providers ship: a local Ollama server (stdlib ``urllib``, no
    package needed) and the Anthropic API (lazy-imports the ``anthropic``
    package from the ``llm`` extra).

Every artifact records which generator produced it in ``body["generator"]``, so a
drafted line is never passed off as template output or vice versa. LLM output is
treated as untrusted: it is parsed as JSON, schema-validated by the calling
stage, and any world-claim it makes is tagged HYPOTHESIS (the model cannot
verify facts).

Selection is by explicit argument or the ``ASUR_LLM`` environment variable:

    ASUR_LLM=ollama:llama3.1          local Ollama (ASUR_OLLAMA_URL overrides
                                      the default http://localhost:11434)
    ASUR_LLM=anthropic                Anthropic API, model claude-sonnet-5-5
    ASUR_LLM=anthropic:<model>        Anthropic API, explicit model
    ASUR_LLM unset / none / template  templates only (default; fully offline)

This module imports only the standard library; the network adapters live in
``asur/llm/adapters/`` and are imported lazily, only when selected.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from typing import Any, Protocol, TypeVar, runtime_checkable

__all__ = [
    "DEFAULT_ANTHROPIC_MODEL",
    "DEFAULT_OLLAMA_MODEL",
    "TEMPLATE",
    "LLMError",
    "LLMProvider",
    "draft_or_fallback",
    "parse_json_payload",
    "provider_from_spec",
]

TEMPLATE = "template"
DEFAULT_OLLAMA_MODEL = "llama3.1"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"
DEFAULT_OLLAMA_URL = "http://localhost:11434"

T = TypeVar("T")


class LLMError(RuntimeError):
    """A provider could not produce a completion (network, auth, missing package)."""


@runtime_checkable
class LLMProvider(Protocol):
    """The whole provider contract: a label for provenance and one completion call."""

    @property
    def label(self) -> str:
        """Provenance label recorded on artifacts, e.g. ``llm:llama3.1``."""
        ...

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 1500) -> str:
        """Return the model's text completion for *prompt* or raise LLMError."""
        ...


def provider_from_spec(spec: str | None = None) -> LLMProvider | None:
    """Build the provider named by *spec* (or ``$ASUR_LLM``); None means templates.

    Raises ValueError on an unknown provider name (fail closed: a typo must not
    silently fall back to templates while the user believes an LLM ran).
    """
    raw = spec if spec is not None else os.environ.get("ASUR_LLM", "")
    raw = raw.strip()
    if not raw or raw.lower() in {"none", "off", TEMPLATE}:
        return None
    kind, _, model = raw.partition(":")
    kind = kind.strip().lower()
    model = model.strip()
    if kind == "ollama":
        from .adapters.ollama import OllamaProvider

        url = os.environ.get("ASUR_OLLAMA_URL", DEFAULT_OLLAMA_URL)
        return OllamaProvider(model or DEFAULT_OLLAMA_MODEL, base_url=url)
    if kind == "anthropic":
        from .adapters.anthropic import AnthropicProvider

        return AnthropicProvider(model or DEFAULT_ANTHROPIC_MODEL)
    raise ValueError(
        f"unknown LLM provider {kind!r} (expected 'ollama[:model]', "
        "'anthropic[:model]' or 'none')"
    )


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_json_payload(text: str) -> Any:
    """Extract and parse the JSON value in a model reply.

    Accepts a bare JSON document, a fenced ```json block, or prose surrounding
    one top-level object/array. Raises ValueError if nothing parses.
    """
    candidates = [text.strip()]
    candidates += [m.strip() for m in _FENCE.findall(text)]
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
    raise ValueError("model reply contained no parseable JSON")


def draft_or_fallback(
    provider: LLMProvider | None,
    *,
    prompt: str,
    system: str,
    validate: Callable[[Any], T],
    fallback: Callable[[], T],
    max_tokens: int = 1500,
) -> tuple[T, dict[str, Any]]:
    """Draft with the LLM when configured; otherwise (or on failure) use templates.

    Returns ``(value, provenance)`` where provenance is ``{"generator": ...}``
    and, after a failed LLM attempt, also ``{"llm_fallback": {provider, error}}``
    so the artifact says plainly that the LLM was tried and why it was not used.
    ``validate`` must raise ValueError (or TypeError/KeyError) on bad output.
    """
    if provider is None:
        return fallback(), {"generator": TEMPLATE}
    try:
        reply = provider.complete(prompt, system=system, max_tokens=max_tokens)
        value = validate(parse_json_payload(reply))
    except (LLMError, ValueError, TypeError, KeyError) as exc:
        return fallback(), {
            "generator": TEMPLATE,
            "llm_fallback": {"provider": provider.label, "error": str(exc)[:200]},
        }
    return value, {"generator": provider.label}
