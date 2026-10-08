"""Stage 12/13 - asset strategy (local, explainable, stdlib-only).

Takes the ``visual_screenplay`` artifact and produces an ``asset_plan``
artifact: for every asset the screenplay asks for, decide the source strategy
(user_original / ai_video / ai_image / procedural / licensed_stock /
screen_recording / existing / hybrid), the default locked-stack model, the
estimated cost, and a license precheck. No network, no media imports.

Defaults come from the LOCKED generation stack (GENERATION_STACK.md / ADR-0004),
all of which are license-clean for commercial use with render_cost_usd:0 when
run locally:
    video -> Wan 2.2 TI2V-5B (Apache-2.0)
    images -> SDXL (OpenRAIL++-M, no revenue cap)
    voice -> Kokoro-82M (Apache-2.0)
    music/sfx -> Stable Audio 3.0 (Community free < $1M revenue)
    captions -> faster-whisper (MIT)
    render -> FFmpeg/MoviePy (MIT)

Each chosen asset gets a license_precheck via the fail-closed license guard so a
trapped model (e.g. FLUX dev, XTTS v2, MusicGen, Suno/Udio, Sora) can never slip
into a monetized plan unnoticed (G9, ADR-0005, ASUR-GATE-01).
"""

from __future__ import annotations

from typing import Any

from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from . import source_ref
from .license_guard import LicenseViolation, check_asset_license

# Locked-stack default model per source strategy (GENERATION_STACK.md).
_DEFAULT_MODEL = {
    "ai_image": ("SDXL", "image", "OpenRAIL++-M"),
    "ai_video": ("Wan 2.2 TI2V-5B", "video", "Apache-2.0"),
    "audio_voice": ("Kokoro-82M", "audio_voice", "Apache-2.0"),
    "audio_music": ("Stable Audio 3.0", "audio_music", "Stable Audio Community"),
    "procedural": ("FFmpeg", "graphic", "LGPL/GPL (tool)"),
}


def _license_block(license_name: str) -> dict[str, Any]:
    """A clean, commercial-OK license block for a locked-stack default asset."""
    return {
        "name": license_name,
        "commercial_ok": True,
        "revenue_cap_usd": None,
        "territory_exclusions": [],
        "training_data_provenance": "disclosed",
        "source_url": "",
        "notes": "locked-stack default; license-clean for commercial use",
    }


def _asset_for_scene(scene: dict[str, Any]) -> list[dict[str, Any]]:
    """Decide the concrete assets + source strategy for one screenplay scene."""
    method = scene.get("generation_method", "ai_image")
    scene_id = scene.get("scene_id", "scene")
    assets: list[dict[str, Any]] = []

    if method == "user_original":
        # Authentic footage preserved - no AI model, no render cost, creator-owned.
        model, media_type, license_name = ("user-camera", "footage", "creator-owned")
        source_strategy = "user_original"
        rationale = "authentic footage adds trust; AI must not replace it here"
    else:
        model, media_type, license_name = _DEFAULT_MODEL["ai_image"]
        source_strategy = "ai_image"
        rationale = "semantic background image illustrates the scene meaning"

    assets.append(
        {
            "asset_ref": f"{scene_id}-background",
            "source_strategy": source_strategy,
            "rationale": rationale,
            "model_choice": model,
            "media_type": media_type,
            "estimated_cost_usd": 0.0,
            "provenance": {"model": model},
            "license": _license_block(license_name),
        }
    )

    # On-screen hero text = procedural (rendered by FFmpeg/MoviePy), zero cost.
    assets.append(
        {
            "asset_ref": f"{scene_id}-onscreen-text",
            "source_strategy": "procedural",
            "rationale": "hero words rendered as typography; no model needed",
            "model_choice": "FFmpeg",
            "media_type": "graphic",
            "estimated_cost_usd": 0.0,
            "provenance": {"model": "FFmpeg"},
            "license": _license_block("LGPL/GPL (tool)"),
        }
    )
    return assets


def build_asset_plan(
    visual_screenplay_artifact: Artifact,
    project_id: str,
    *,
    monetized: bool = True,
    expected_revenue_usd: float = 0.0,
    target_territory: str | None = None,
    identity: Identity | None = None,
) -> Artifact:
    """Produce an ``asset_plan`` artifact from the visual screenplay.

    Runs a fail-closed license precheck on every chosen asset. If any trapped or
    non-commercial asset would be used in a monetized plan the guard raises
    ``LicenseViolation`` naming the asset (ASUR-GATE-01) and no plan is produced.
    """
    sp_body = visual_screenplay_artifact.body or {}
    subject = sp_body.get("subject", "the topic")
    scenes = sp_body.get("scenes") or []

    assets: list[dict[str, Any]] = []
    for scene in scenes:
        assets.extend(_asset_for_scene(scene))

    # One shared voice track + one shared music bed for the whole proof.
    v_model, v_type, v_lic = _DEFAULT_MODEL["audio_voice"]
    assets.append(
        {
            "asset_ref": "voice-track",
            "source_strategy": "ai_video",  # audio generated locally
            "rationale": "narration voice; local, license-clean, no cloning",
            "model_choice": v_model,
            "media_type": v_type,
            "estimated_cost_usd": 0.0,
            "provenance": {"model": v_model},
            "license": _license_block(v_lic),
        }
    )
    m_model, m_type, m_lic = _DEFAULT_MODEL["audio_music"]
    assets.append(
        {
            "asset_ref": "music-bed",
            "source_strategy": "ai_video",
            "rationale": "low instrumental bed; local, free below revenue threshold",
            "model_choice": m_model,
            "media_type": m_type,
            "estimated_cost_usd": 0.0,
            "provenance": {"model": m_model},
            "license": _license_block(m_lic),
        }
    )

    # Fail-closed license precheck over every asset. Guard names the offender.
    precheck_errors: list[str] = []
    for asset in assets:
        try:
            check_asset_license(
                asset,
                monetized=monetized,
                expected_revenue_usd=expected_revenue_usd,
                target_territory=target_territory,
            )
            asset["license_precheck"] = "pass"
        except LicenseViolation as exc:  # pragma: no cover - defaults never trap
            asset["license_precheck"] = f"BLOCK:LICENSE_VIOLATION - {exc}"
            precheck_errors.append(str(exc))

    if precheck_errors:
        # Fail closed naming the offending asset(s) (ASUR-GATE-01, G9).
        raise LicenseViolation("; ".join(precheck_errors))

    total_cost = sum(a.get("estimated_cost_usd", 0.0) for a in assets)

    body: dict[str, Any] = {
        "subject": subject,
        "asset_count": len(assets),
        "assets": assets,
        "total_estimated_cost_usd": total_cost,
        "monetized": monetized,
        "method": (
            "local heuristic: locked-stack defaults (Wan2.2/SDXL/Kokoro/Stable "
            "Audio/FFmpeg), fail-closed license precheck; no network, no model"
        ),
    }

    return make_artifact(
        kind="asset_plan",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[source_ref(visual_screenplay_artifact)],
        agent="generation",
        identity=identity,
    )
