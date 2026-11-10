"""Time scenes from MEASURED narration instead of a words-per-second estimate.

The script planner sizes each section at ``WORDS_PER_SECOND`` (2.5 words/s,
``asur.script.script_builder``). Real speech engines talk faster than that, so a
scene planned from the estimate is longer than its spoken line, and padding the
narration to the planned span leaves dead air at the end of every scene. On the
README demo it added up to 16.9 s of silence, with a longest gap of 2.7 s.

This module is the fix, as pure data transforms (stdlib only, no I/O):

  * ``fit_scene_durations`` - each scene lasts as long as its measured speech
    plus a short, bounded pad (``NARRATION_PAD_S``). It never runs shorter than
    the time needed to read its on-screen caption at ``READING_WPS``, or than
    ``MIN_SCENE_S``. A beat with no narration is capped at ``UNNARRATED_MAX_S``,
    so it can never become a long silent gap.
  * ``timed_edit_plan`` - rebuilds the timeline from the screenplay with those
    durations (contiguous starts/ends, captions moved with their scenes) and
    records the measurements in the ``edit_plan`` body, so ``verify-repro`` can
    rebuild it deterministically from the same numbers.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from .timeline import build_edit_plan, build_timeline_from_generation_plan

__all__ = [
    "MIN_SCENE_S",
    "NARRATION_PAD_S",
    "READING_WPS",
    "TIMING_SOURCE",
    "UNNARRATED_MAX_S",
    "fit_scene_durations",
    "retimed_screenplay",
    "timed_edit_plan",
]

TIMING_SOURCE = "measured_narration"
# Air after the last word of a scene. Kept well under the viral check's 0.5 s
# silence-detection minimum, so it reads as a breath, not dead air.
NARRATION_PAD_S = 0.3
MIN_SCENE_S = 1.0
# A scene with no spoken line (a visual beat) never lasts longer than this.
UNNARRATED_MAX_S = 1.5
# On-screen text must stay readable: a scene is at least caption_words / this
# long. Set below the viral check's 3.5 words/s comfort limit, with margin.
READING_WPS = 3.3


def _ceil_tenth(x: float) -> float:
    """Round up to 0.1 s (a whole number of frames at 30 fps), avoiding float fuzz."""
    return math.ceil(round(x * 10, 6)) / 10


def fit_scene_durations(
    scenes: list[dict[str, Any]], speech_s: list[float | None]
) -> list[float]:
    """One duration per scene from its measured speech (see the module docstring)."""
    if len(scenes) != len(speech_s):
        raise ValueError("need one speech measurement per scene")
    durations: list[float] = []
    for scene, spoken in zip(scenes, speech_s):
        caption = str((scene.get("graphics") or {}).get("onscreen_text", "") or "")
        reading = len(caption.split()) / READING_WPS
        if spoken is None:
            planned = float(scene.get("end", 0.0)) - float(scene.get("start", 0.0))
            base = min(max(planned, MIN_SCENE_S), UNNARRATED_MAX_S)
        else:
            base = float(spoken) + NARRATION_PAD_S
        durations.append(_ceil_tenth(max(base, reading, MIN_SCENE_S)))
    return durations


def retimed_screenplay(screenplay: Artifact, durations: list[float]) -> Artifact:
    """An in-memory copy of *screenplay* whose scenes run back to back at *durations*.

    Only ``start``/``end`` change. The copy is not saved: the saved screenplay
    stays the planned one (its rebuild must stay reproducible), and the measured
    timing lives in the ``edit_plan`` that ``timed_edit_plan`` builds.
    """
    body = dict(screenplay.body or {})
    scenes = list(body.get("scenes") or [])
    if len(scenes) != len(durations):
        raise ValueError("need one duration per screenplay scene")
    retimed = []
    t = 0.0
    for scene, dur in zip(scenes, durations):
        start = round(t, 3)
        t += dur
        retimed.append({**scene, "start": start, "end": round(t, 3)})
    body["scenes"] = retimed
    return replace(screenplay, body=body)


def timed_edit_plan(
    generation_plan: Artifact,
    screenplay: Artifact,
    project_id: str,
    speech_s: list[float | None],
    *,
    engine: str = "",
    identity: Identity | None = None,
) -> Artifact:
    """An ``edit_plan`` whose scene timing comes from the measured narration."""
    scenes = list((screenplay.body or {}).get("scenes") or [])
    durations = fit_scene_durations(scenes, speech_s)
    planned_total = round(sum(float(s["end"]) - float(s["start"]) for s in scenes), 3)
    timeline = build_timeline_from_generation_plan(
        generation_plan, retimed_screenplay(screenplay, durations), project_id
    )
    plan = build_edit_plan(
        timeline, generation_plan, project_id,
        note="scenes timed from measured narration", identity=identity,
    )
    body = dict(plan.body or {})
    body["timing"] = {
        "source": TIMING_SOURCE,
        "engine": engine,
        "speech_s": list(speech_s),
        "durations_s": durations,
        "planned_total_s": planned_total,
        "total_s": round(sum(durations), 3),
        "pad_s": NARRATION_PAD_S,
        "reading_wps": READING_WPS,
        "unnarrated_max_s": UNNARRATED_MAX_S,
    }
    # Re-wrap so the checksum covers the timing block.
    return make_artifact(
        kind=plan.kind, project_id=project_id, body=body, status=plan.status,
        sources=list(plan.sources), agent="editing", identity=identity,
    )
