"""Network-backed LLM providers. Imported lazily by ``asur.llm.provider_from_spec``.

These modules may use ``urllib`` (Ollama) or the optional ``anthropic`` package,
so they sit outside the stdlib-only boundary lint, like the media adapters.
"""
