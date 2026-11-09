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
from ..llm import LLMProvider, draft_or_fallback
from . import source_ref
from .llm_schema import clean_text

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


# Narration pace used to turn spoken words into section timings. ~150 words per
# minute is a common conversational narration rate; the render's system voice
# speaks slightly faster, so every line fits inside its scene.
WORDS_PER_SECOND = 2.5
_MIN_SECTION_S = 2.0

_LLM_SYSTEM = (
    "You write tight scripts for short vertical videos. Reply with ONE JSON object "
    "only. Do not invent statistics, studies, quotes, or personal anecdotes; speak "
    "in second person to the viewer. Each spoken line is at most 2 sentences."
)


def _speech_seconds(text: str) -> float:
    """Estimated narration time for *text* at WORDS_PER_SECOND (min 2.0s)."""
    words = len([w for w in text.split() if w.strip("-")])
    return round(max(_MIN_SECTION_S, words / WORDS_PER_SECOND), 1)


def _template_lines(
    subject: str, hook_text: str, value_line: str, core_promise: str, has_takeaway: bool
) -> dict[str, tuple[str, str]]:
    """Deterministic offline (spoken_words, onscreen_text) per section.

    The subject is named in the hook, problem, and payoff only - not mechanically
    in every line - and the story beat describes a common pattern instead of
    claiming a first-person experience the template cannot have had.
    """
    return {
        "hook": (hook_text, hook_text),
        "opening": (
            "If this sounds familiar, the next thirty seconds are for you.",
            subject.capitalize(),
        ),
        "problem": (
            f"Most people struggle with {subject} because they fix the wrong thing first.",
            "Here's the real problem",
        ),
        "context": (
            "The usual advice skips the part that actually matters.",
            "The part everyone skips",
        ),
        "story": (
            "Here's how it usually goes: you follow the popular tips, see little "
            "change, and assume the problem is you.",
            "Sound familiar?",
        ),
        "value": (value_line, "The one thing that works"),
        "proof": (
            (
                "Don't take my word for it - try it this week and check the result yourself."
                if has_takeaway
                else "Test it on your own situation before you trust it."
            ),
            "Test it yourself",
        ),
        "payoff": (
            f"Do that, and {subject} stops being the thing that holds you back.",
            core_promise,
        ),
        "cta": ("Save this so you have it the next time it comes up.", "Save this for later"),
    }


def _validate_llm_script(data: Any, hook_text: str) -> dict[str, tuple[str, str]]:
    sections = data.get("sections") if isinstance(data, dict) else None
    if not isinstance(sections, dict):
        raise ValueError("expected a 'sections' object")
    out: dict[str, tuple[str, str]] = {"hook": (hook_text, hook_text)}
    for name in SECTION_ORDER[1:]:
        sec = sections.get(name)
        if not isinstance(sec, dict):
            raise ValueError(f"missing section {name!r}")
        spoken = clean_text(sec.get("spoken_words"), max_chars=300)
        onscreen = clean_text(sec.get("onscreen_text") or spoken.split(".")[0], max_chars=80)
        out[name] = (spoken, onscreen)
    return out


def build_script(
    strategy_artifact: Artifact,
    hooks_artifact: Artifact,
    project_id: str,
    *,
    identity: Identity | None = None,
    generator: LLMProvider | None = None,
) -> Artifact:
    """Produce a ``script`` artifact from ``strategy`` + ``hooks``.

    The selected hook is always the opening line. Spoken words come from the
    deterministic template or, when ``generator`` is supplied and its output
    validates, from the LLM; production fields (visual/audio/transition
    direction) are template-authored either way. Section timings are derived
    from the spoken word counts at WORDS_PER_SECOND, so the estimated duration
    reflects the actual script length.
    """
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
    value_field = (strategy_artifact.body or {}).get("value_prop") or {}
    value_prop = _strategy_val(
        strategy_artifact, "value_prop", f"a clear, honest take on {subject}"
    )
    has_takeaway = isinstance(value_field, dict) and value_field.get("source") == "creator"
    value_line = (
        f"Here's the one thing that actually works: {value_prop.rstrip('.')}."
        if has_takeaway
        else f"Here's the one thing that actually fixes it: {value_prop.rstrip('.')}."
    )

    lines, provenance = draft_or_fallback(
        generator,
        prompt=(
            f"Topic: {subject!r}. Opening hook (keep verbatim): {hook_text!r}.\n"
            f"Core promise: {core_promise!r}. "
            + (f"The creator's key takeaway (must be the value section): {value_prop!r}.\n"
               if has_takeaway else "Propose one concrete, checkable takeaway.\n")
            + 'Return JSON {"sections": {NAME: {"spoken_words": str, "onscreen_text": '
            "str (max 6 words)}}} for NAME in: "
            + ", ".join(SECTION_ORDER[1:])
            + "."
        ),
        system=_LLM_SYSTEM,
        validate=lambda data: _validate_llm_script(data, hook_text),
        fallback=lambda: _template_lines(subject, hook_text, value_line, core_promise, has_takeaway),
    )
    if provenance["generator"] == "template":
        value_source = "creator" if has_takeaway else "template-generic"
    else:
        value_source = provenance["generator"]

    # Cumulative timings from spoken length.
    timings: dict[str, str] = {}
    cursor = 0.0
    for name in SECTION_ORDER:
        dur = _speech_seconds(lines[name][0])
        timings[name] = f"{cursor:.1f}-{cursor + dur:.1f}s"
        cursor = round(cursor + dur, 1)
    total_s = cursor

    production = {
        "hook": (hook_emotion, "stop scrolling; feel the open loop",
                 "pattern-interrupt first frame; tight on speaker or bold text",
                 "none - keep attention on the hook", "hard cut into opening",
                 "punchy, no intro music delay"),
        "opening": (emotion, "recognize themselves; commit to watch",
                    "speaker direct to camera; confident framing",
                    "light b-roll establishing the subject", "smooth cut",
                    "subtle bed music enters low"),
        "problem": ("concern", "feel the stakes", "visual metaphor for the problem",
                    "footage illustrating the pain point", "quick cut on emphasis",
                    "music tension rises slightly"),
        "context": ("curiosity", "lean in for the missing piece",
                    "contrast old-way vs better-way", "split-screen or comparison b-roll",
                    "wipe or slide", "steady bed"),
        "story": ("empathy", "recognize the pattern; relate",
                  "authentic recreation of the common mistake",
                  "authentic, not stock-feeling footage", "soft cut",
                  "music softens under the story"),
        "value": ("aspiration", "feel they're getting real usefulness",
                  "clear on-screen steps or key point", "diagram or demonstration",
                  "cut on each point", "music lifts on the payoff build"),
        "proof": ("credibility", "believe it is worth testing",
                  "evidence, example, or before/after", "proof footage or result shot",
                  "clean cut", "steady, confident bed"),
        "payoff": (emotion, "feel the loop close; satisfied", "confident resolution shot",
                   "summary visual", "settle", "music resolves"),
        "cta": ("warm", "take the action (save / send / follow)",
                "speaker direct to camera; clear ask", "none", "end card", "music outro"),
    }
    sections: dict[str, Any] = {}
    for name in SECTION_ORDER:
        spoken, onscreen = lines[name]
        emo, reaction, visual, broll, transition, audio = production[name]
        sections[name] = _section(
            spoken=spoken, timing=timings[name], emotion=emo, reaction=reaction,
            visual=visual, onscreen=onscreen, broll=broll, transition=transition,
            audio=audio,
        )

    pattern_interrupts = [
        _section(
            spoken="(none - visual beat)",
            timing=f"~{total_s / 3:.1f}s",
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
            timing=f"~{2 * total_s / 3:.1f}s",
            emotion="surprise",
            reaction="re-hook before the payoff",
            visual="text punch-in on the key word",
            onscreen="Remember this",
            broll="",
            transition="speed ramp",
            audio="accent hit",
        ),
    ]

    body = {
        "language": language,
        "subject": subject,
        "selected_hook_id": hook.get("hook_id"),
        "narrative_structure": list(SECTION_ORDER[:7])
        + ["pattern_interrupts"]
        + list(SECTION_ORDER[7:]),
        "section_fields": list(SECTION_FIELDS),
        "sections": sections,
        "pattern_interrupts": pattern_interrupts,
        "estimated_duration_s": total_s,
        "words_per_second": WORDS_PER_SECOND,
        "value_source": value_source,
        **provenance,
        "method": (
            "local structured script builder; anchored to selected hook; no network"
            if provenance["generator"] == "template"
            else f"spoken lines drafted by {provenance['generator']}; anchored to selected hook"
        ),
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
