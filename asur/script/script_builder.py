"""Stage 6 - structured script (local, explainable).

Takes the ``strategy`` and ``hooks`` artifacts and produces a ``script``
artifact: a full structured script with ten sections, each carrying the nine
production fields the GENERATION layer later needs. No network
(ASUR-LOCAL-01). The selected hook from the ``hooks`` artifact becomes the
opening spoken line, so the script is anchored to the best-scored hook.

A script is more than dialogue: every section records how it should look,
sound, move, and what reaction it should create. That is what makes a later
visual screenplay possible without the author re-deciding everything.

Section order follows the locked narrative structure:
    hook -> opening -> problem -> context -> story -> value -> proof ->
    pattern_interrupts[] -> payoff -> cta
"""

from __future__ import annotations

from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from . import source_ref

# The nine fields every section must carry (DATA_MODELS.md script schema).
SECTION_FIELDS = (
    "spoken_words",
    "timing",
    "emotion",
    "intended_reaction",
    "visual_direction",
    "onscreen_text",
    "broll_requirements",
    "transition_requirements",
    "audio_direction",
)

# Linear section names (pattern_interrupts is a list, handled separately).
SECTION_ORDER = (
    "hook",
    "opening",
    "problem",
    "context",
    "story",
    "value",
    "proof",
    "payoff",
    "cta",
)


def _selected_hook(hooks_artifact: Artifact) -> dict[str, Any]:
    body = hooks_artifact.body or {}
    selected_id = body.get("selected_hook_id")
    for hook in body.get("hooks", []):
        if hook.get("hook_id") == selected_id:
            return hook
    # Fail soft: fall back to first hook if the selection is missing.
    hooks = body.get("hooks", [])
    return hooks[0] if hooks else {}


def _strategy_val(strategy_artifact: Artifact, name: str, default: str) -> str:
    field = (strategy_artifact.body or {}).get(name) or {}
    if isinstance(field, dict):
        return field.get("value") or default
    if isinstance(field, str):
        return field or default
    return default


def _section(
    *,
    spoken: str,
    timing: str,
    emotion: str,
    reaction: str,
    visual: str,
    onscreen: str,
    broll: str,
    transition: str,
    audio: str,
) -> dict[str, str]:
    return {
        "spoken_words": spoken,
        "timing": timing,
        "emotion": emotion,
        "intended_reaction": reaction,
        "visual_direction": visual,
        "onscreen_text": onscreen,
        "broll_requirements": broll,
        "transition_requirements": transition,
        "audio_direction": audio,
    }


def build_script(
    strategy_artifact: Artifact,
    hooks_artifact: Artifact,
    project_id: str,
    *,
    identity: Identity | None = None,
) -> Artifact:
    """Produce a ``script`` artifact from ``strategy`` + ``hooks``."""
    hook = _selected_hook(hooks_artifact)
    hook_meta = hook.get("metadata", {})
    hook_text = hook_meta.get("hook", "")
    hook_emotion = hook_meta.get("emotion", "curiosity")

    subject = (hooks_artifact.body or {}).get("subject", "the topic")
    language = (strategy_artifact.body or {}).get("language", "en")
    emotion = _strategy_val(strategy_artifact, "emotion", "curiosity")
    core_promise = _strategy_val(
        strategy_artifact, "core_promise", f"the one thing about {subject} that matters"
    )
    value_prop = _strategy_val(
        strategy_artifact, "value_prop", f"a clear, honest take on {subject}"
    )

    sections: dict[str, Any] = {}

    sections["hook"] = _section(
        spoken=hook_text,
        timing="0.0-3.0s",
        emotion=hook_emotion,
        reaction="stop scrolling; feel the open loop",
        visual="pattern-interrupt first frame; tight on speaker or bold text",
        onscreen=hook_text,
        broll="none - keep attention on the hook",
        transition="hard cut into opening",
        audio="punchy, no intro music delay",
    )

    sections["opening"] = _section(
        spoken=f"If you care about {subject}, the next 30 seconds are for you.",
        timing="3.0-7.0s",
        emotion=emotion,
        reaction="recognize themselves; commit to watch",
        visual="speaker direct to camera; confident framing",
        onscreen=f"{subject}".capitalize(),
        broll="light b-roll establishing the subject",
        transition="smooth cut",
        audio="subtle bed music enters low",
    )

    sections["problem"] = _section(
        spoken=f"Most people struggle with {subject} because they fix the wrong thing first.",
        timing="7.0-13.0s",
        emotion="concern",
        reaction="feel the stakes",
        visual="visual metaphor for the problem",
        onscreen="Here's the real problem",
        broll="footage illustrating the pain point",
        transition="quick cut on emphasis",
        audio="music tension rises slightly",
    )

    sections["context"] = _section(
        spoken=f"The usual advice on {subject} skips the part that actually matters.",
        timing="13.0-20.0s",
        emotion="curiosity",
        reaction="lean in for the missing piece",
        visual="contrast old-way vs better-way",
        onscreen="The part everyone skips",
        broll="split-screen or comparison b-roll",
        transition="wipe or slide",
        audio="steady bed",
    )

    sections["story"] = _section(
        spoken=f"I learned this the hard way with {subject} - so you don't have to.",
        timing="20.0-30.0s",
        emotion="empathy",
        reaction="trust the speaker; relate",
        visual="personal footage or authentic recreation",
        onscreen="I learned this the hard way",
        broll="authentic, not stock-feeling footage",
        transition="soft cut",
        audio="music softens under the story",
    )

    sections["value"] = _section(
        spoken=f"Here's the one thing that actually fixes it: {value_prop}.",
        timing="30.0-40.0s",
        emotion="aspiration",
        reaction="feel they're getting real usefulness",
        visual="clear on-screen steps or key point",
        onscreen="The one thing that works",
        broll="diagram or demonstration",
        transition="cut on each point",
        audio="music lifts on the payoff build",
    )

    sections["proof"] = _section(
        spoken=f"This isn't just talk - it's exactly why it works for {subject}.",
        timing="40.0-47.0s",
        emotion="credibility",
        reaction="believe the claim",
        visual="evidence, example, or before/after",
        onscreen="Why it actually works",
        broll="proof footage or result shot",
        transition="clean cut",
        audio="steady, confident bed",
    )

    pattern_interrupts = [
        _section(
            spoken="(none - visual beat)",
            timing="~17.0s",
            emotion="surprise",
            reaction="reset attention mid-video",
            visual="sudden zoom or angle change",
            onscreen="",
            broll="",
            transition="snap cut",
            audio="beat-synced whoosh",
        ),
        _section(
            spoken="(none - visual beat)",
            timing="~33.0s",
            emotion="surprise",
            reaction="re-hook before the payoff",
            visual="text punch-in on the key word",
            onscreen="Remember this",
            broll="",
            transition="speed ramp",
            audio="accent hit",
        ),
    ]

    sections["payoff"] = _section(
        spoken=f"Do that, and {subject} stops being the thing that holds you back.",
        timing="47.0-54.0s",
        emotion=emotion,
        reaction="feel the loop close; satisfied",
        visual="confident resolution shot",
        onscreen=core_promise,
        broll="summary visual",
        transition="settle",
        audio="music resolves",
    )

    sections["cta"] = _section(
        spoken=f"Save this so you remember it next time {subject} comes up.",
        timing="54.0-60.0s",
        emotion="warm",
        reaction="take the action (save / send / follow)",
        visual="speaker direct to camera; clear ask",
        onscreen="Save this for later",
        broll="none",
        transition="end card",
        audio="music outro",
    )

    body = {
        "language": language,
        "subject": subject,
        "selected_hook_id": hook.get("hook_id"),
        "narrative_structure": list(SECTION_ORDER[:7])
        + ["pattern_interrupts"]
        + list(SECTION_ORDER[7:]),
        "section_fields": list(SECTION_FIELDS),
        "sections": {name: sections[name] for name in SECTION_ORDER},
        "pattern_interrupts": pattern_interrupts,
        "estimated_duration_s": 60,
        "method": "local structured script builder; anchored to selected hook; no network",
    }

    return make_artifact(
        kind="script",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[source_ref(strategy_artifact), source_ref(hooks_artifact)],
        agent="script",
        identity=identity,
    )
