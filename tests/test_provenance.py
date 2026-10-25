"""Tests for the provenance+license schema guard (ASUR-PROV-01 made real).

Proves every produced asset must carry the complete block the pipeline relies
on, that the guard fails closed (and names the gap) on any missing/invalid
field, and that it is wired into ``produce_assets`` so a black-box asset can
never reach the render.
"""

import pytest

from asur.generation.provenance import (
    ProvenanceError,
    validate_asset_provenance,
    validate_produced_assets,
)


def _good_asset(**overrides):
    asset = {
        "media_type": "image",
        "file_path": "/tmp/scene-1.png",
        "provenance": {"model": "SDXL", "model_version": "1.0"},
        "license": {"name": "OpenRAIL++-M", "commercial_ok": True},
    }
    asset.update(overrides)
    return asset


def test_complete_asset_passes():
    """A fully-formed provenance+license block validates cleanly."""
    validate_asset_provenance(_good_asset())  # must not raise


def test_renderer_block_shape_passes():
    """The FFmpeg renderer's own block shape is accepted (no false positive)."""
    render_block = {
        "media_type": "video",
        "origin": "procedural",
        "file_path": "/tmp/final.mp4",
        "provenance": {"model": "FFmpeg", "model_version": "ffmpeg-binary"},
        "license": {"name": "FFmpeg-tool-output", "commercial_ok": True},
    }
    validate_asset_provenance(render_block)


@pytest.mark.parametrize(
    "mutation",
    [
        {"media_type": ""},
        {"file_path": ""},
        {"provenance": {}},                      # no model
        {"provenance": {"model": "  "}},          # blank model
        {"license": {"name": "X"}},               # no commercial_ok
        {"license": {"name": "", "commercial_ok": True}},  # blank name
        {"license": {"name": "X", "commercial_ok": "yes"}},  # not a bool
    ],
)
def test_incomplete_asset_fails_closed(mutation):
    """ASUR-GATE-01: any missing/invalid field fails closed with a named gap."""
    with pytest.raises(ProvenanceError):
        validate_asset_provenance(_good_asset(**mutation))


def test_non_dict_asset_fails_closed():
    """A produced 'asset' that is not even a block is refused."""
    with pytest.raises(ProvenanceError):
        validate_asset_provenance("not-an-asset")


def test_error_names_the_offending_asset():
    """ASUR-EXPLAIN-01: the failure message names the asset and the field."""
    with pytest.raises(ProvenanceError) as exc:
        validate_asset_provenance(_good_asset(file_path="/tmp/bad.png", provenance={}))
    assert "/tmp/bad.png" in str(exc.value)
    assert "provenance" in str(exc.value)


def test_validate_produced_assets_walks_the_list():
    """A produce_assets result validates each asset; the second gap is caught."""
    produced = {
        "backgrounds": {},
        "voice": None,
        "music": None,
        "assets": [_good_asset(), _good_asset(provenance={})],
        "skipped": [],
    }
    with pytest.raises(ProvenanceError):
        validate_produced_assets(produced)


def test_validate_produced_assets_requires_an_assets_list():
    """A result with no assets list fails closed rather than passing vacuously."""
    with pytest.raises(ProvenanceError):
        validate_produced_assets({"backgrounds": {}})


def test_produce_assets_enforces_provenance(monkeypatch, tmp_path):
    """produce_assets runs the guard: a black-box asset never reaches the render.

    We stub the dispatcher so no media extra is needed, returning one asset with
    a complete block and one missing its license. produce_assets must fail closed
    on the incomplete one (ASUR-PROV-01, ASUR-GATE-01).
    """
    from asur.core.envelope import make_artifact
    from asur.generation import dispatch, produce

    f1 = tmp_path / "a.png"
    f1.write_bytes(b"x")
    f2 = tmp_path / "b.wav"
    f2.write_bytes(b"y")

    calls = iter(
        [
            {
                "media_type": "image",
                "file_path": str(f1),
                "provenance": {"model": "SDXL"},
                "license": {"name": "OpenRAIL++-M", "commercial_ok": True},
            },
            {  # incomplete: no license block
                "media_type": "audio_voice",
                "file_path": str(f2),
                "provenance": {"model": "Kokoro"},
            },
        ]
    )
    monkeypatch.setattr(dispatch, "run_job", lambda job, out_dir: next(calls))

    plan = make_artifact(
        kind="generation_plan",
        project_id="p",
        body={
            "jobs": [
                {"job_id": "j1", "model": "SDXL", "target_asset": "s1-background",
                 "params": {"media_type": "image"}},
                {"job_id": "j2", "model": "Kokoro", "target_asset": "voice",
                 "params": {"media_type": "audio_voice"}},
            ]
        },
    )

    with pytest.raises(ProvenanceError):
        produce.produce_assets(plan, out_dir=str(tmp_path / "out"))
