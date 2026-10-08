"""P03 firewall tests: projection views, conformance, hand-off queue, cross-import.

Covers ASUR-FIREWALL-01 (GENERATION and VIRAL CHECK never see each other's
playbook; the only bridge is SCRIPT's pure projection) and ASUR-VERSION-01 +
STATE_MACHINE.md s5 (HEAD/digest binding on the hand-off queue). All tests are
stdlib-only, deterministic, offline, and fail-closed.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from asur.core.identity import Identity
from asur.tools.projection import (
    FirewallLeak,
    build_generation_view,
    build_viral_view,
    conformance_scan,
)
from asur.tools.queue import HandoffQueue, QueueError

_IDENTITY = Identity(local_user="tester", git_name="Tester", git_email="t@local")


# -- projection: happy path -------------------------------------------------


def test_generation_view_happy_path():
    """ASUR-FIREWALL-01: a clean GENERATION_VIEW carries only allowed material."""
    view = build_generation_view(
        brief={"topic": "save money on AI tools", "platform": "instagram_reels"},
        hooks={"direction": "contrarian", "angles": ["cost", "myth"]},
        quality_floors={"min_retention": "floor-only (minimum bar)"},
        cost_policy={"budget": "cheap-first", "license": "commercial_ok"},
    )
    assert view["view"] == "GENERATION_VIEW"
    assert view["brief"]["platform"] == "instagram_reels"
    assert view["hooks"]["direction"] == "contrarian"


def test_viral_view_happy_path():
    """ASUR-FIREWALL-01: a clean VIRAL_VIEW carries only bytes + provenance facts."""
    view = build_viral_view(
        bundle_hashes={"video": "sha256:abc", "scope": "full reel"},
        provenance={"asset1": {"model": "Wan 2.2", "license": "Apache-2.0"}},
        platform_facts={"platform": "instagram_reels", "aspect": "9:16"},
        rubric_metadata={"lane": "viral-check", "binding": "local"},
    )
    assert view["view"] == "VIRAL_VIEW"
    assert view["platform_facts"]["aspect"] == "9:16"


def test_generation_and_viral_views_are_deterministic():
    """ASUR-EXPLAIN-01: same inputs -> identical view (pure projection)."""
    args = {
        "brief": {"topic": "x"},
        "hooks": {"direction": "story"},
        "quality_floors": {"min": 1},
        "cost_policy": {"budget": "cheap"},
    }
    assert build_generation_view(**args) == build_generation_view(**args)
    vargs = {
        "bundle_hashes": {"v": "sha256:1"},
        "provenance": {"a": {"license": "Apache-2.0"}},
        "platform_facts": {"platform": "instagram_reels"},
        "rubric_metadata": {"lane": "viral-check"},
    }
    assert build_viral_view(**vargs) == build_viral_view(**vargs)


# -- projection: fail closed on a leak --------------------------------------


def test_generation_view_fails_closed_on_viral_criteria_key():
    """ASUR-FIREWALL-01: a viral-checker pass criterion in GENERATION_VIEW fails closed."""
    with pytest.raises(FirewallLeak):
        build_generation_view(
            brief={"pass_criteria": "watch_time > 0.6"},
            hooks={"direction": "x"},
            quality_floors={},
            cost_policy={},
        )


def test_generation_view_fails_closed_on_leaked_string_value():
    """ASUR-FIREWALL-01: a forbidden name hidden in a string value also fails closed."""
    with pytest.raises(FirewallLeak):
        build_generation_view(
            brief={"note": "do not reveal the gate_thresholds to anyone"},
            hooks={"direction": "x"},
            quality_floors={},
            cost_policy={},
        )


def test_viral_view_fails_closed_on_quality_target_key():
    """ASUR-FIREWALL-01: a quality TARGET in VIRAL_VIEW fails closed (stripped by name)."""
    with pytest.raises(FirewallLeak):
        build_viral_view(
            bundle_hashes={"v": "sha256:1"},
            provenance={"hardness_targets": {"retention": 90}},
            platform_facts={},
            rubric_metadata={},
        )


def test_viral_view_fails_closed_on_target_score_string():
    """ASUR-FIREWALL-01: 'target_score' anywhere in a VIRAL_VIEW fails closed."""
    with pytest.raises(FirewallLeak):
        build_viral_view(
            bundle_hashes={"v": "sha256:1"},
            provenance={},
            platform_facts={"note": "the author's target_score was 85"},
            rubric_metadata={},
        )


def test_conformance_scan_passes_clean_view():
    """ASUR-FIREWALL-01: a clean view passes the greppable conformance scan."""
    conformance_scan({"view": "X", "ok": "nothing forbidden here"}, frozenset({"bad"}))


# -- queue: happy path ------------------------------------------------------


def test_queue_seal_claim_verdict_place_happy_path(tmp_path):
    """ASUR-VERSION-01: a full seal->claim->verdict->place cycle agrees 3-way."""
    q = HandoffQueue(tmp_path, "run-1").ensure()
    bundle = {"video": "frames", "duration_s": 5}
    sealed = q.seal("task-1", bundle, identity=_IDENTITY)
    claimed = q.claim("task-1", identity=_IDENTITY)
    assert claimed == sealed
    q.verdict("task-1", claimed, "PASS", identity=_IDENTITY)
    placed = q.place("task-1", identity=_IDENTITY)
    assert placed == sealed
    kinds = [e["kind"] for e in q.events()]
    assert kinds == ["seal", "claim", "verdict", "place"]
    assert q.path == tmp_path / ".asur" / "queue" / "run-1.jsonl"


def test_queue_reseal_same_bytes_is_idempotent(tmp_path):
    """ASUR-VERSION-01: re-sealing identical bytes returns the same digest."""
    q = HandoffQueue(tmp_path, "run-1").ensure()
    bundle = {"a": 1}
    d1 = q.seal("task-1", bundle, identity=_IDENTITY)
    d2 = q.seal("task-1", bundle, identity=_IDENTITY)
    assert d1 == d2


def test_queue_events_persist_across_instances(tmp_path):
    """ASUR-VERSION-01: the append-only log survives a fresh HandoffQueue instance."""
    HandoffQueue(tmp_path, "run-1").ensure().seal("t", {"a": 1}, identity=_IDENTITY)
    reopened = HandoffQueue(tmp_path, "run-1")
    assert [e["kind"] for e in reopened.events()] == ["seal"]


# -- queue: fail closed -----------------------------------------------------


def test_queue_reseal_different_bytes_is_task_collision(tmp_path):
    """ASUR-VERSION-01: re-sealing a task with different bytes fails closed."""
    q = HandoffQueue(tmp_path, "run-1").ensure()
    q.seal("task-1", {"a": 1}, identity=_IDENTITY)
    with pytest.raises(QueueError):
        q.seal("task-1", {"a": 2}, identity=_IDENTITY)


def test_queue_claim_unsealed_fails_closed(tmp_path):
    """ASUR-GATE-01: claiming a never-sealed task fails closed."""
    q = HandoffQueue(tmp_path, "run-1").ensure()
    with pytest.raises(QueueError):
        q.claim("task-1", identity=_IDENTITY)


def test_queue_double_claim_fails_closed(tmp_path):
    """ASUR-FIREWALL-01: a sealed bundle has a single claimant (O_EXCL lock)."""
    q = HandoffQueue(tmp_path, "run-1").ensure()
    q.seal("task-1", {"a": 1}, identity=_IDENTITY)
    q.claim("task-1", identity=_IDENTITY)
    with pytest.raises(QueueError):
        q.claim("task-1", identity=_IDENTITY)


def test_queue_verdict_before_claim_fails_closed(tmp_path):
    """ASUR-GATE-01: recording a verdict for an unclaimed task fails closed."""
    q = HandoffQueue(tmp_path, "run-1").ensure()
    q.seal("task-1", {"a": 1}, identity=_IDENTITY)
    with pytest.raises(QueueError):
        q.verdict("task-1", "sha256:x", "PASS", identity=_IDENTITY)


def test_queue_place_with_wrong_verdict_digest_blocks(tmp_path):
    """STATE_MACHINE s5: place fails closed when the 3-way digest disagrees."""
    q = HandoffQueue(tmp_path, "run-1").ensure()
    q.seal("task-1", {"a": 1}, identity=_IDENTITY)
    q.claim("task-1", identity=_IDENTITY)
    q.verdict("task-1", "sha256:wrong", "PASS", identity=_IDENTITY)
    with pytest.raises(QueueError):
        q.place("task-1", identity=_IDENTITY)


def test_queue_place_before_verdict_fails_closed(tmp_path):
    """ASUR-GATE-01: placing before a verdict exists fails closed."""
    q = HandoffQueue(tmp_path, "run-1").ensure()
    q.seal("task-1", {"a": 1}, identity=_IDENTITY)
    q.claim("task-1", identity=_IDENTITY)
    with pytest.raises(QueueError):
        q.place("task-1", identity=_IDENTITY)


# -- static cross-import check ----------------------------------------------

_GENERATION_PKGS = frozenset({"generation", "generation_engine"})
_VIRAL_PKGS = frozenset({"viral_check", "viral", "viralcheck"})
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "asur"


def _top_level_imports(path: Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            parts = node.module.split(".")
            names.add(parts[0])
            # also catch 'from asur.viral_check import x'
            if parts[0] == "asur" and len(parts) > 1:
                names.add(parts[1])
    return names


def _modules_under(pkg_names: frozenset) -> list:
    out: list = []
    for name in pkg_names:
        pkg_dir = _PACKAGE_ROOT / name
        if pkg_dir.is_dir():
            out.extend(pkg_dir.rglob("*.py"))
    return out


def test_generation_never_imports_viral_check():
    """ASUR-FIREWALL-01: no GENERATION module imports a VIRAL CHECK module.

    Vacuously true until GENERATION (P04) and VIRAL CHECK (P07) exist; it must
    fail closed the moment such a cross-import is introduced.
    """
    for mod in _modules_under(_GENERATION_PKGS):
        imported = _top_level_imports(mod)
        leaked = imported & _VIRAL_PKGS
        assert not leaked, f"{mod} imports VIRAL CHECK {leaked} (firewall breach)"


def test_viral_check_never_imports_generation():
    """ASUR-FIREWALL-01: no VIRAL CHECK module imports a GENERATION module."""
    for mod in _modules_under(_VIRAL_PKGS):
        imported = _top_level_imports(mod)
        leaked = imported & _GENERATION_PKGS
        assert not leaked, f"{mod} imports GENERATION {leaked} (firewall breach)"
