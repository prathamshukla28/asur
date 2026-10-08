"""Integration tests for the ASUR Phase 1 SCRIPT pipeline.

Runs the full chain idea -> research -> audience -> strategy -> hooks ->
script -> quality gate end to end, and asserts the founding invariants hold:

  ASUR-LOCAL-01   pure local, no network (nothing here reaches out)
  ASUR-VERSION-01 every saved artifact is versioned, nothing overwritten
  ASUR-PROV-01    every stage records its source lineage
  ASUR-EXPLAIN-01 hooks score on 15 named dimensions
  ASUR-GATE-01    quality gate fails closed on a degenerate script
  ASUR-FIREWALL-01 script-side artifacts never carry viral-checker criteria
"""

import json

from asur.core.envelope import verify_checksum
from asur.core.gate import SHIP
from asur.core.workspace import Workspace
from asur.script import source_ref
from asur.script.idea import build_idea
from asur.script.research import build_research
from asur.script.audience import build_audience
from asur.script.strategy import build_strategy
from asur.script.hooks import build_hooks, SCORE_DIMS, MIN_HOOKS
from asur.script.script_builder import build_script, SECTION_ORDER, SECTION_FIELDS
from asur.script.quality_gate import build_qa_report, run_quality_gate


SAMPLE_IDEA = "why most people waste money on AI tools"
PROJECT_ID = "test-project"


def _build_chain(project_id=PROJECT_ID):
    """Build the full Phase 1 artifact chain and return it as a dict."""
    idea = build_idea(SAMPLE_IDEA, project_id)
    research = build_research(idea, project_id)
    audience = build_audience(idea, research, project_id)
    strategy = build_strategy(idea, audience, project_id)
    hooks = build_hooks(strategy, project_id)
    script = build_script(strategy, hooks, project_id)
    qa, result = build_qa_report(
        script, project_id, hooks_artifact=hooks, strategy_artifact=strategy
    )
    return {
        "idea": idea,
        "research": research,
        "audience": audience,
        "strategy": strategy,
        "hooks": hooks,
        "script": script,
        "qa_report": qa,
        "result": result,
    }


def test_full_pipeline_produces_all_seven_artifacts():
    chain = _build_chain()
    for kind in ("idea", "research", "audience", "strategy", "hooks", "script", "qa_report"):
        artifact = chain[kind]
        assert artifact is not None, f"{kind} artifact was not produced"
        assert artifact.kind == kind, f"{kind} artifact has wrong kind {artifact.kind!r}"


def test_every_artifact_checksum_verifies():
    chain = _build_chain()
    for kind in ("idea", "research", "audience", "strategy", "hooks", "script", "qa_report"):
        assert verify_checksum(chain[kind]), f"{kind} checksum does not verify"


def test_lineage_sources_are_correct():
    """ASUR-PROV-01: each stage records exactly the upstream artifacts it used."""
    chain = _build_chain()

    def source_ids(artifact):
        return {s["artifact_id"] for s in artifact.sources}

    def source_checksums(artifact):
        return {s["checksum"] for s in artifact.sources}

    # research <- idea
    assert source_ids(chain["research"]) == {chain["idea"].artifact_id}
    # audience <- idea + research
    assert source_ids(chain["audience"]) == {
        chain["idea"].artifact_id,
        chain["research"].artifact_id,
    }
    # strategy <- idea + audience
    assert source_ids(chain["strategy"]) == {
        chain["idea"].artifact_id,
        chain["audience"].artifact_id,
    }
    # hooks <- strategy
    assert source_ids(chain["hooks"]) == {chain["strategy"].artifact_id}
    # script <- strategy + hooks
    assert source_ids(chain["script"]) == {
        chain["strategy"].artifact_id,
        chain["hooks"].artifact_id,
    }
    # qa_report <- script (and hooks)
    assert chain["script"].artifact_id in source_ids(chain["qa_report"])

    # recorded source checksums must match the real upstream checksums
    assert chain["research"].checksum in source_checksums(chain["audience"])
    assert chain["idea"].checksum in source_checksums(chain["research"])
    assert chain["hooks"].checksum in source_checksums(chain["script"])


def test_source_ref_shape():
    chain = _build_chain()
    ref = source_ref(chain["idea"])
    assert set(ref.keys()) == {"artifact_id", "version", "checksum"}
    assert ref["artifact_id"] == chain["idea"].artifact_id
    assert ref["checksum"] == chain["idea"].checksum


def test_hooks_count_meets_minimum():
    chain = _build_chain()
    hooks = chain["hooks"].body["hooks"]
    assert len(hooks) >= MIN_HOOKS, f"expected >= {MIN_HOOKS} hooks, got {len(hooks)}"


def test_every_hook_has_all_fifteen_score_dims():
    """ASUR-EXPLAIN-01: each hook is scored on every named dimension, 0-100."""
    chain = _build_chain()
    for hook in chain["hooks"].body["hooks"]:
        scores = hook["scores"]
        assert set(scores.keys()) == set(SCORE_DIMS), (
            f"hook {hook['hook_id']} missing score dims: "
            f"{set(SCORE_DIMS) - set(scores.keys())}"
        )
        for dim, value in scores.items():
            assert isinstance(value, int), f"{dim} score is not an int: {value!r}"
            assert 0 <= value <= 100, f"{dim} score out of range: {value}"


def test_selected_hook_is_rank_one():
    chain = _build_chain()
    body = chain["hooks"].body
    selected_id = body["selected_hook_id"]
    rank_one = min(body["hooks"], key=lambda h: h["rank"])
    assert rank_one["hook_id"] == selected_id
    assert rank_one["rank"] == 1


def test_script_has_nine_sections_each_with_nine_fields():
    chain = _build_chain()
    sections = chain["script"].body["sections"]
    assert set(sections.keys()) == set(SECTION_ORDER), (
        f"section mismatch: {set(SECTION_ORDER) ^ set(sections.keys())}"
    )
    for name in SECTION_ORDER:
        section = sections[name]
        assert set(section.keys()) == set(SECTION_FIELDS), (
            f"section {name!r} field mismatch: "
            f"{set(SECTION_FIELDS) ^ set(section.keys())}"
        )


def test_gate_ships_on_good_script():
    """ASUR-GATE-01 (happy path): a well-formed script passes the 13-check gate."""
    chain = _build_chain()
    result = chain["result"]
    assert result.disposition == SHIP, f"expected SHIP, got {result.disposition}"
    assert result.passed is True
    assert chain["qa_report"].body["checks_total"] == 13


def test_gate_fails_closed_on_degenerate_script():
    """ASUR-GATE-01 (fail-closed): an empty script must NOT pass."""
    chain = _build_chain()
    good_script = chain["script"]

    # Degenerate copy: strip every section down to empty fields.
    import copy

    broken = copy.deepcopy(good_script)
    empty_section = {field: "" for field in SECTION_FIELDS}
    broken.body["sections"] = {name: dict(empty_section) for name in SECTION_ORDER}
    broken.body["pattern_interrupts"] = []
    broken.recompute_checksum()
    broken.checksum = broken.recompute_checksum()

    result = run_quality_gate(
        broken, hooks_artifact=chain["hooks"], strategy_artifact=chain["strategy"]
    )
    assert result.disposition != SHIP, "degenerate script must not SHIP"
    assert result.passed is False


def test_firewall_no_viral_checker_criteria_leak():
    """ASUR-FIREWALL-01: script-side artifacts carry quality floors only.

    They must never contain viral-checker pass criteria / target thresholds.
    """
    chain = _build_chain()
    forbidden = (
        "pass_criteria",
        "pass_threshold",
        "viral_threshold",
        "target_score",
        "viral_pass",
        "checker_criteria",
    )
    for kind in ("strategy", "hooks", "script"):
        blob = json.dumps(chain[kind].body).lower()
        for token in forbidden:
            assert token not in blob, (
                f"ASUR-FIREWALL-01 violation: {kind} body contains forbidden "
                f"viral-checker token {token!r}"
            )


def test_workspace_versioning_is_append_only(tmp_path):
    """ASUR-VERSION-01: saving the same chain twice bumps versions, never overwrites."""
    ws = Workspace(tmp_path, PROJECT_ID).ensure()

    chain1 = _build_chain()
    for kind in ("idea", "research", "audience", "strategy", "hooks", "script", "qa_report"):
        ws.save_artifact(chain1[kind])
        assert chain1[kind].version == 1, f"{kind} first save should be v1"

    chain2 = _build_chain()
    for kind in ("idea", "research", "audience", "strategy", "hooks", "script", "qa_report"):
        ws.save_artifact(chain2[kind])
        assert chain2[kind].version == 2, f"{kind} second save should be v2"

    # Both versions must still exist on disk (nothing overwritten).
    for kind in ("idea", "strategy", "script"):
        assert ws.load_artifact(kind, 1) is not None, f"{kind} v1 lost"
        assert ws.load_artifact(kind, 2) is not None, f"{kind} v2 lost"


def test_determinism_same_idea_same_checksums():
    """Same idea -> identical bodies -> identical artifact ids and checksums."""
    a = _build_chain("determinism-a")
    b = _build_chain("determinism-a")
    for kind in ("idea", "research", "audience", "strategy", "hooks", "script"):
        assert a[kind].checksum == b[kind].checksum, f"{kind} is not deterministic"
        assert a[kind].artifact_id == b[kind].artifact_id


# ---------------------------------------------------------------------------
# P01 additions: hook A/B variant grouping (G2) + append-only hook memory (G3)
# ---------------------------------------------------------------------------

from asur.script.hook_memory import HookMemory, HOOK_EVENTS


def test_ab_variants_are_data_only():
    """SPEC-GAP G2 / ASUR-HONEST-01: A/B grouping is data-only, no live winner."""
    chain = _build_chain()
    ab = chain["hooks"].body["ab_variants"]

    # Marked explicitly as data-only, never a measured experiment.
    assert "data-only" in ab["status"], f"ab_variants status not data-only: {ab['status']!r}"

    # At least one variant, labels are a subset of A/B/C/D.
    assert ab["variants"], "expected at least one A/B variant"
    labels = [v["variant"] for v in ab["variants"]]
    assert set(labels) <= {"A", "B", "C", "D"}
    assert len(labels) == len(set(labels)), "variant labels must be unique"

    known_hook_ids = {h["hook_id"] for h in chain["hooks"].body["hooks"]}
    seen_directions = set()
    for v in ab["variants"]:
        # Each variant picks a real hook from a distinct strategic direction.
        assert v["direction"] not in seen_directions, "directions must be distinct per variant"
        seen_directions.add(v["direction"])
        assert v["chosen_hook_id"] in v["candidate_hook_ids"]
        assert v["chosen_hook_id"] in known_hook_ids


def test_ab_variants_declare_no_winner():
    """ASUR-HONEST-01: data-only grouping must not imply a measured winner."""
    chain = _build_chain()
    ab = chain["hooks"].body["ab_variants"]
    assert ab.get("status", "").startswith("data-only")
    for v in ab["variants"]:
        for token in ("winner", "percent_viral", "viral_score", "won", "beats", "score"):
            assert token not in v, f"variant must not carry a measured-outcome key ({token!r})"


def test_hook_memory_append_only_roundtrip(tmp_path):
    """SPEC-GAP G3 / ASUR-VERSION-01: hook memory only ever grows; survives reopen."""
    mem = HookMemory(tmp_path).ensure()
    assert mem.all_records() == [], "fresh memory should be empty"

    mem.record(hook_text="first hook", event="generated", project_id="p")
    mem.record(hook_text="second hook", event="used", project_id="p")
    assert len(mem.all_records()) == 2

    # Reopen a fresh instance on the same directory: records persist.
    mem2 = HookMemory(tmp_path)
    recs = mem2.all_records()
    assert len(recs) == 2, "records did not persist across reopen"

    # Appending grows, never shrinks or overwrites.
    mem2.record(hook_text="third hook", event="published", project_id="p")
    assert len(HookMemory(tmp_path).all_records()) == 3


def test_hook_memory_prior_texts_distinct_first_seen_order(tmp_path):
    mem = HookMemory(tmp_path).ensure()
    mem.record(hook_text="alpha", event="generated", project_id="p")
    mem.record(hook_text="beta", event="used", project_id="p")
    mem.record(hook_text="alpha", event="published", project_id="p")  # duplicate text

    all_texts = mem.prior_hook_texts()
    assert all_texts == ["alpha", "beta"], f"expected distinct first-seen order, got {all_texts}"

    # Event filter narrows the set.
    used_only = mem.prior_hook_texts(events=("used",))
    assert used_only == ["beta"]


def test_hook_memory_fails_closed_on_unknown_event(tmp_path):
    """ASUR-GATE-01: an unrecognised event is rejected, not silently recorded."""
    import pytest

    mem = HookMemory(tmp_path).ensure()
    with pytest.raises(ValueError):
        mem.record(hook_text="x", event="not-a-real-event", project_id="p")
    assert "not-a-real-event" not in HOOK_EVENTS


def test_hook_memory_record_many_counts_hooks(tmp_path):
    chain = _build_chain()
    mem = HookMemory(tmp_path).ensure()
    n = mem.record_many(chain["hooks"].body["hooks"], event="generated", project_id="p")
    assert n == len(chain["hooks"].body["hooks"])
    assert len(mem.all_records()) == n


def test_prior_hooks_feed_originality_across_runs(tmp_path):
    """G3 end-to-end: remembered hooks make a repeat generation look derivative."""
    chain = _build_chain()
    mem = HookMemory(tmp_path).ensure()
    mem.record_many(chain["hooks"].body["hooks"], event="generated", project_id="p")

    prior = mem.prior_hook_texts()
    assert prior, "expected remembered hook texts"

    strategy = chain["strategy"]
    again = build_hooks(strategy, "p", prior_hooks=prior)
    selected = next(
        h for h in again.body["hooks"] if h["hook_id"] == again.body["selected_hook_id"]
    )
    # The selected hook was generated before, so originality must not be 'original'.
    assert selected["originality"]["verdict"] != "original"
