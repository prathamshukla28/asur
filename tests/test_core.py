"""Unit tests for the ASUR key-free core.

Covers the invariants that everything else leans on:
  - canonical: determinism + checksum stability (same content -> same hash,
    key order irrelevant, unicode preserved).
  - identity: always resolves, never raises, never hits the network.
  - envelope: well-formed artifacts, checksum over body only, tamper detection.
  - workspace: monotonic versioning, NO silent overwrite, atomic create,
    load round-trips, corruption guard.
  - gate: fail-closed (empty -> HOLD, raising check -> BLOCK, unknown -> BLOCK),
    producer != approver (self-approval capped at HOLD:SELF_APPROVED).
"""

from __future__ import annotations

import pytest

from asur.core import canonical, identity
from asur.core.envelope import make_artifact, verify_checksum
from asur.core.workspace import Workspace, WorkspaceError
from asur.core.identity import Identity
from asur.core import gate
from asur.core.gate import Check, run_gate, approval_gate, SHIP, HOLD, BLOCK


# -- canonical -----------------------------------------------------------
def test_canonical_is_key_order_independent():
    a = {"b": 1, "a": 2, "c": {"y": 1, "x": 2}}
    b = {"a": 2, "c": {"x": 2, "y": 1}, "b": 1}
    assert canonical.canonicalize(a) == canonical.canonicalize(b)
    assert canonical.canonical_sha256(a) == canonical.canonical_sha256(b)


def test_canonical_has_single_trailing_newline():
    text = canonical.canonicalize({"x": 1})
    assert text.endswith("\n")
    assert not text.endswith("\n\n")


def test_canonical_preserves_unicode():
    # Hindi/Hinglish content must survive as real UTF-8, not \uXXXX escapes.
    text = canonical.canonicalize({"hook": "Ye baat koi nahi batata"})
    assert "Ye baat koi nahi batata" in text


def test_canonical_rejects_nan():
    with pytest.raises(ValueError):
        canonical.canonicalize({"x": float("nan")})


# -- identity ------------------------------------------------------------
def test_identity_always_resolves():
    ident = identity.get_identity()
    assert ident.local_user  # never empty
    assert isinstance(ident.git_name, str)
    assert isinstance(ident.git_email, str)


def test_identity_principal_prefers_email():
    i = Identity(local_user="u", git_name="N", git_email="e@x")
    assert i.principal() == "e@x"
    assert Identity("u", "N", "").principal() == "N"
    assert Identity("u", "", "").principal() == "u"


# -- envelope ------------------------------------------------------------
def test_make_artifact_is_well_formed():
    art = make_artifact(kind="idea", project_id="p1", body={"one_line": "x"})
    assert art.kind == "idea"
    assert art.version == 1
    assert art.schema_version == "asur.artifact/v1"
    assert art.artifact_id.startswith("idea-")
    assert verify_checksum(art)


def test_checksum_is_over_body_only():
    art = make_artifact(kind="idea", project_id="p1", body={"one_line": "x"})
    before = art.checksum
    # Mutating envelope metadata (status/review) must NOT change the checksum.
    art.status = "approved"
    art.review = {"reviewer": "r", "decision": "approved"}
    assert verify_checksum(art)
    assert art.checksum == before


def test_tamper_detection():
    art = make_artifact(kind="idea", project_id="p1", body={"one_line": "x"})
    art.body = {"one_line": "tampered"}
    assert not verify_checksum(art)


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        make_artifact(kind="not_a_kind", project_id="p1", body={})


# -- workspace -----------------------------------------------------------
def test_workspace_monotonic_versioning(tmp_path):
    ws = Workspace(tmp_path, project_id="p1").ensure()
    assert ws.latest_version("idea") == 0
    a1 = make_artifact(kind="idea", project_id="p1", body={"n": 1})
    ws.save_artifact(a1)
    assert ws.latest_version("idea") == 1
    a2 = make_artifact(kind="idea", project_id="p1", body={"n": 2})
    ws.save_artifact(a2)
    assert ws.latest_version("idea") == 2


def test_workspace_load_roundtrip(tmp_path):
    ws = Workspace(tmp_path, project_id="p1").ensure()
    body = {"one_line": "why most AI tools waste money", "lang": "en"}
    art = make_artifact(kind="idea", project_id="p1", body=body)
    ws.save_artifact(art)
    loaded = ws.load_latest("idea")
    assert loaded is not None
    assert loaded.body == body
    assert verify_checksum(loaded)


def test_workspace_refuses_corrupt_save(tmp_path):
    ws = Workspace(tmp_path, project_id="p1").ensure()
    art = make_artifact(kind="idea", project_id="p1", body={"n": 1})
    art.body = {"n": 999}  # checksum now stale -> corruption
    with pytest.raises(WorkspaceError):
        ws.save_artifact(art)


def test_workspace_supersede_appends_history(tmp_path):
    ws = Workspace(tmp_path, project_id="p1").ensure()
    ws.save_artifact(make_artifact(kind="idea", project_id="p1", body={"n": 1}))
    ws.supersede("idea")
    latest = ws.load_latest("idea")
    assert latest is not None
    assert latest.status == "superseded"
    assert ws.latest_version("idea") == 2  # history is append-only


# -- gate ----------------------------------------------------------------
def test_gate_empty_holds():
    assert run_gate("g", []).disposition == HOLD


def test_gate_takes_worst_disposition():
    checks = [
        Check("ok", lambda: (SHIP, "fine")),
        Check("warn", lambda: (HOLD, "needs change")),
    ]
    assert run_gate("g", checks).disposition == HOLD


def test_gate_raising_check_blocks():
    def boom():
        raise RuntimeError("kaboom")

    assert run_gate("g", [Check("boom", boom)]).disposition == BLOCK


def test_gate_unknown_disposition_blocks():
    assert run_gate("g", [Check("weird", lambda: ("MAYBE", "?"))]).disposition == BLOCK


def test_approval_gate_requires_approver():
    prod = Identity("u", "N", "e@x")
    r = approval_gate("g", producer=prod, approver=None)
    assert r.disposition == HOLD
    assert r.substate == "HUMAN_APPROVAL_REQUIRED"


def test_approval_gate_self_approval_capped():
    prod = Identity("u", "N", "e@x")
    r = approval_gate("g", producer=prod, approver=prod)
    assert r.disposition == HOLD
    assert r.substate == "SELF_APPROVED"
    assert r.self_approved is True


def test_approval_gate_self_approval_allowed_when_permitted():
    prod = Identity("u", "N", "e@x")
    r = approval_gate("g", producer=prod, approver=prod, allow_self_approval=True)
    assert r.disposition == SHIP
    assert r.self_approved is True


def test_approval_gate_distinct_approver_ships():
    prod = Identity("u", "N", "e@x")
    appr = Identity("v", "M", "m@y")
    r = approval_gate("g", producer=prod, approver=appr)
    assert r.disposition == SHIP
    assert r.self_approved is False


def test_approval_gate_content_block_dominates_approval():
    prod = Identity("u", "N", "e@x")
    appr = Identity("v", "M", "m@y")
    checks = [Check("bad", lambda: (BLOCK, "license violation"))]
    r = approval_gate("g", producer=prod, approver=appr, checks=checks)
    assert r.disposition == BLOCK
