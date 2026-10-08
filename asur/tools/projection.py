"""Firewall projections - the pure function that bridges GENERATION and VIRAL CHECK.

ASUR-FIREWALL-01: GENERATION and VIRAL CHECK never see each other's workbench.
SCRIPT (which holds full memory) computes two *views* from the shared material:

  GENERATION_VIEW  - what the generator is allowed to see: the creative brief,
                     audience, platform, promise, hook direction + strategic
                     angles, quality/hardness FLOORS (the minimum bar), and the
                     cost/budget + asset-license policy. It must NEVER carry the
                     viral-checker's pass criteria, gate thresholds, or finding /
                     weakness / exploit reasoning.

  VIRAL_VIEW       - what the evaluator is allowed to see: the rendered-bundle
                     content hashes, claimed scope, provenance manifests +
                     per-asset license facts, platform/brand facts, and checker
                     rubric metadata (which lane, binding identity). It must
                     NEVER carry the quality/hardness TARGETS - no per-dimension
                     target, no "what good was defined as". An evaluator holding
                     the author's playbook grades the intent instead of the bytes.

Three enforcement mechanisms (all local, key-free):
  1. Pure projection: these functions recompute each view deterministically from
     their inputs. Same inputs -> same view. No hidden state, no network.
  2. Named-forbidden strip + grep conformance: `conformance_scan` recursively
     greps a produced view (keys AND string values) for forbidden names and
     FAILS CLOSED (raises FirewallLeak) if any appears. Each builder runs this
     on its own output before returning, so a leak can never escape.
  3. (Local layout check lives at the gate / queue layer - see queue.py and the
     static cross-import check in tests/test_boundary.py.)
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "GENERATION_FORBIDDEN",
    "VIRAL_FORBIDDEN",
    "FirewallLeak",
    "build_generation_view",
    "build_viral_view",
    "conformance_scan",
]


class FirewallLeak(ValueError):
    """Raised (fail-closed) when a forbidden field name leaks into a view.

    Carrying this to a gate maps to disposition BLOCK, substate FIREWALL_LEAK.
    """


# Names the GENERATION side must never receive. The evaluator's playbook.
GENERATION_FORBIDDEN = frozenset(
    {
        "pass_criteria",
        "gate_thresholds",
        "finding_text",
        "weakness",
        "exploit",
        "verdict",
        "viral_check",
    }
)

# Names the VIRAL CHECK side must never receive. The author's playbook.
VIRAL_FORBIDDEN = frozenset(
    {
        "quality_targets",
        "hardness_targets",
        "target_score",
        "per_dimension_target",
        "what_good_is",
        "quality_floors",
    }
)


def _walk_strings(obj: Any):
    """Yield every dict key and every string value anywhere inside *obj*."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(key, str):
                yield key
            yield from _walk_strings(value)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _walk_strings(item)
    elif isinstance(obj, str):
        yield obj


def conformance_scan(view: dict, forbidden: frozenset) -> None:
    """Fail closed if any *forbidden* name appears as a key or inside a string.

    This is the greppable firewall conformance check (ASUR-FIREWALL-01). It is
    deliberately a substring match on a casefolded token so that a forbidden
    name cannot hide inside a larger key/value either.
    """
    for token in _walk_strings(view):
        low = token.casefold()
        for bad in forbidden:
            if bad in low:
                raise FirewallLeak(
                    f"forbidden field '{bad}' leaked into projection "
                    f"(found in '{token}'); ASUR-FIREWALL-01 fails closed"
                )


def build_generation_view(
    *,
    brief: dict,
    hooks: dict,
    quality_floors: dict,
    cost_policy: dict,
) -> dict:
    """Compute the GENERATION_VIEW the generator is allowed to see.

    Carries the creative brief, hook direction + strategic angles, quality
    FLOORS (minimum bar), and the cost/budget + asset-license policy. Runs the
    conformance scan against GENERATION_FORBIDDEN before returning - so if any
    viral-checker pass criterion / gate threshold / finding leaked in through
    the inputs, this fails closed.
    """
    view = {
        "view": "GENERATION_VIEW",
        "brief": brief,
        "hooks": hooks,
        "quality_floors": quality_floors,
        "cost_policy": cost_policy,
    }
    conformance_scan(view, GENERATION_FORBIDDEN)
    return view


def build_viral_view(
    *,
    bundle_hashes: dict,
    provenance: dict,
    platform_facts: dict,
    rubric_metadata: dict,
) -> dict:
    """Compute the VIRAL_VIEW the evaluator is allowed to see.

    Carries rendered-bundle content hashes + claimed scope, provenance +
    per-asset license facts, platform/brand facts, and checker rubric metadata
    (lane + binding identity, NOT fixtures). Runs the conformance scan against
    VIRAL_FORBIDDEN before returning - so if any quality/hardness TARGET leaked
    in through the inputs, this fails closed.
    """
    view = {
        "view": "VIRAL_VIEW",
        "bundle_hashes": bundle_hashes,
        "provenance": provenance,
        "platform_facts": platform_facts,
        "rubric_metadata": rubric_metadata,
    }
    conformance_scan(view, VIRAL_FORBIDDEN)
    return view
