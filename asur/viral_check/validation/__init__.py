"""Blind-correlation validation for the VIRAL CHECK instrument (SPEC-GAP G30).

This subpackage proves, empirically and honestly, whether the twelve
per-dimension input-quality scores *correlate* with real-world performance
on a dataset of real clips. It is a CORRELATION STUDY, never a predictor:

  - It never emits a single "%viral" number or any aggregate score
    (ASUR-HONEST-01). It reports a per-dimension Spearman rank correlation.
  - Clips are scored BLIND: the observed view counts stay sealed in
    ``views.sealed.json`` and the scorer never opens that file.
  - Judgment-call facts (delivers_promise, strong_first_three_seconds) come
    from a blind human rater who has not seen the views; a missing judgment
    is OMITTED, never invented (ASUR anti-hallucination rule).
  - All three modules are stdlib-only. Observable facts are injected (ffprobe
    and the faster-whisper adapter are called only in real runs, behind the
    injection parameters), so tests touch no binaries, network, or GPU.
"""

from __future__ import annotations

from . import correlate, derive, score_blind

__all__ = ["correlate", "derive", "score_blind"]
