"""Strict validators for LLM-drafted SCRIPT content (stdlib-only).

Model output is untrusted input. These helpers coerce a parsed JSON value into
the exact shape a stage needs, or raise ValueError so the stage falls back to
its deterministic template (see ``asur.llm.draft_or_fallback``).
"""

from __future__ import annotations

from typing import Any

MAX_ITEM_CHARS = 400


def clean_text(value: Any, *, max_chars: int = MAX_ITEM_CHARS) -> str:
    """A single non-empty line of text, whitespace-collapsed and length-capped."""
    if not isinstance(value, str):
        raise ValueError(f"expected a string, got {type(value).__name__}")
    text = " ".join(value.split())
    if not text:
        raise ValueError("empty string")
    if len(text) > max_chars:
        raise ValueError(f"string longer than {max_chars} characters")
    return text


def as_str_list(value: Any, min_items: int, max_items: int) -> list[str]:
    """A list of ``min_items..max_items`` clean strings (extra items are dropped)."""
    if not isinstance(value, list):
        raise ValueError("expected a list")
    items = [clean_text(v) for v in value[:max_items]]
    if len(items) < min_items:
        raise ValueError(f"expected at least {min_items} items, got {len(items)}")
    return items


def as_object_list(
    value: Any, keys: tuple[str, ...], min_items: int, max_items: int
) -> list[dict[str, str]]:
    """A list of objects each carrying exactly *keys* as clean strings."""
    if not isinstance(value, list):
        raise ValueError("expected a list of objects")
    out: list[dict[str, str]] = []
    for item in value[:max_items]:
        if not isinstance(item, dict):
            raise ValueError("expected an object")
        out.append({k: clean_text(item.get(k)) for k in keys})
    if len(out) < min_items:
        raise ValueError(f"expected at least {min_items} objects, got {len(out)}")
    return out
