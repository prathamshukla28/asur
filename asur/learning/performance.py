"""Performance capture - the real numbers a human records after publishing (Stage 26).

A performance artifact holds the measured results of a published video: views,
watch time, retention, shares, saves, comments, likes, follows. These numbers are
HUMAN-PROVIDED (pasted or typed in from the platform's own analytics). ASUR never
fetches them over the network (ASUR-LOCAL-01) - there is no network call here.

It carries lineage back to the publish_package it measures, so every number is
traceable to exactly what was posted (ASUR-PROV-01, ASUR-VERSION-01).
"""

from __future__ import annotations

from ..core.envelope import Artifact, make_artifact, utc_now_iso
from ..core.identity import Identity
from . import source_ref

# The metric keys ASUR understands. Unknown keys from the human are kept verbatim
# too (we never silently drop what a creator recorded), but these are the ones the
# learning fold reads when comparing prediction vs reality.
METRIC_KEYS = (
    "views",
    "watch_time_s",
    "avg_watch_time_s",
    "retention_pct",
    "completion_pct",
    "shares",
    "saves",
    "comments",
    "likes",
    "follows",
)


def build_performance(
    publish_package_artifact: Artifact,
    metrics: dict,
    project_id: str,
    *,
    identity: Identity | None = None,
) -> Artifact:
    """Record human-provided performance metrics for a published video.

    `metrics` is whatever the creator read off the platform. We normalise the
    known keys (defaulting missing ones to 0) and keep any extra keys the creator
    supplied, so nothing they measured is lost. No network, no fetching.
    """
    metrics = dict(metrics or {})
    normalised = {key: metrics.get(key, 0) for key in METRIC_KEYS}
    # Preserve any extra keys the creator recorded beyond the known set.
    for key, value in metrics.items():
        if key not in normalised:
            normalised[key] = value

    body = {
        "stage": "performance",
        "metrics": normalised,
        "source": "human-provided (read from platform analytics; no network fetch)",
        "captured_at": utc_now_iso(),
        "method": (
            "local capture of human-entered metrics; ASUR makes no network call to "
            "any platform (ASUR-LOCAL-01)"
        ),
    }

    return make_artifact(
        kind="performance",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[source_ref(publish_package_artifact)],
        agent="learning",
        identity=identity,
    )
