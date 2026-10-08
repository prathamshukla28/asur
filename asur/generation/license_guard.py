"""License guard - the fail-closed trap list (G9, ADR-0005).

Every media asset carries a license block (ASUR-PROV-01). Before any asset is
used for a monetized project, the guard checks it against a hard-coded list of
known license traps and the asset's own declared license facts. If the asset is
not safe for commercial use under the project's terms, the guard FAILS CLOSED
and names the offending asset + license (ASUR-GATE-01). It never silently
downgrades or ignores a trap.

A trap fires when, for a monetized project, ANY of:
  * the asset's model/source is on the hard-coded TRAP_LIST with a reason that
    forbids this use (non-commercial, territory, MAU, or traffic cap), or
  * the asset's own license block says commercial_ok is false, or
  * the project's expected revenue exceeds the asset's revenue_cap_usd, or
  * the project's target territory is in the asset's territory_exclusions.

The result maps to gate disposition BLOCK, substate LICENSE_VIOLATION.

No network, stdlib only. The trap facts are frozen here from
docs/GENERATION_STACK.md; new facts require an ADR + SPEC-GAP, never a guess.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "TRAP_LIST",
    "LicenseViolation",
    "check_asset_license",
    "check_assets",
]


class LicenseViolation(ValueError):
    """Raised (fail-closed) when an asset is not license-safe for the project.

    Maps to gate disposition BLOCK, substate LICENSE_VIOLATION. The message
    always names the offending asset and the license reason (ASUR-EXPLAIN-01).
    """


# Hard-coded trap facts, frozen from docs/GENERATION_STACK.md (ADR-0005).
# Keyed by a model/source identifier (casefolded match). Each entry states why
# it is a trap and, where relevant, the structured limits the guard enforces.
#   kind: "non_commercial" | "territory" | "mau_cap" | "traffic_cap" | "avoid"
TRAP_LIST: dict[str, dict[str, Any]] = {
    "flux.1 dev": {"kind": "non_commercial", "note": "FLUX.1 dev is non-commercial without a paid BFL license."},
    "flux.2 dev": {"kind": "non_commercial", "note": "FLUX.2 dev is non-commercial without a paid BFL license."},
    "xtts v2": {"kind": "non_commercial", "note": "XTTS v2 / Coqui is CPML non-commercial."},
    "coqui": {"kind": "non_commercial", "note": "Coqui XTTS is CPML non-commercial."},
    "musicgen": {"kind": "non_commercial", "note": "MusicGen / AudioCraft is CC-BY-NC-4.0 non-commercial."},
    "audiocraft": {"kind": "non_commercial", "note": "AudioCraft is CC-BY-NC-4.0 non-commercial."},
    "hunyuanvideo": {
        "kind": "territory",
        "territories": ("EU", "UK", "KR"),
        "mau_cap": 100_000_000,
        "note": "HunyuanVideo is not licensed in EU/UK/South Korea and has a 100M MAU cap.",
    },
    "cogvideox-5b": {
        "kind": "traffic_cap",
        "traffic_cap_visits_month": 1_000_000,
        "note": "CogVideoX-5B is capped at <1M visits/month.",
    },
    "suno": {"kind": "avoid", "note": "Suno is avoided entirely (download disabled / litigation)."},
    "udio": {"kind": "avoid", "note": "Udio is avoided entirely (download disabled / litigation)."},
    "sora": {"kind": "avoid", "note": "Sora is removed (sunset 2026-09-24) and must never be used."},
}


def _model_key(asset: dict) -> str:
    provenance = asset.get("provenance") or {}
    model = provenance.get("model") or ""
    return str(model).strip().casefold()


def check_asset_license(
    asset: dict,
    *,
    monetized: bool,
    expected_revenue_usd: float = 0.0,
    target_territory: str | None = None,
    expected_mau: int = 0,
    expected_visits_month: int = 0,
) -> None:
    """Raise :class:`LicenseViolation` if *asset* is not license-safe.

    Returns ``None`` when the asset passes. ``asset`` is a provenance+license
    block dict (see docs/DATA_MODELS.md). A project that is not monetized still
    gets the hard "avoid" traps enforced (e.g. Sora, Suno/Udio) because those
    are unusable regardless of money, but commercial-only limits are skipped.
    """
    asset_id = asset.get("asset_id") or asset.get("asset_ref") or "<unnamed-asset>"
    model_key = _model_key(asset)
    trap = TRAP_LIST.get(model_key)

    # "avoid" traps are absolute - they fire even for non-monetized projects.
    if trap is not None and trap["kind"] == "avoid":
        raise LicenseViolation(f"asset '{asset_id}' uses forbidden source '{model_key}': {trap['note']}")

    if not monetized:
        return

    license_block = asset.get("license") or {}

    # The asset's own declared license facts come first (fail closed on absence
    # is not required here because a missing commercial_ok is treated as unsafe).
    commercial_ok = license_block.get("commercial_ok")
    if commercial_ok is False or commercial_ok is None:
        name = license_block.get("name", "unknown")
        raise LicenseViolation(
            f"asset '{asset_id}' license '{name}' is not commercial-ok "
            "(commercial_ok is false or undeclared) for a monetized project."
        )

    cap = license_block.get("revenue_cap_usd")
    if cap is not None and expected_revenue_usd > cap:
        raise LicenseViolation(
            f"asset '{asset_id}' license '{license_block.get('name', 'unknown')}' has a "
            f"revenue cap of ${cap} but the project expects ${expected_revenue_usd}."
        )

    territory_exclusions = license_block.get("territory_exclusions") or []
    if target_territory and target_territory in territory_exclusions:
        raise LicenseViolation(
            f"asset '{asset_id}' is excluded in territory '{target_territory}' "
            f"({license_block.get('name', 'unknown')})."
        )

    # Hard-coded structured traps (model-level), on top of declared facts.
    if trap is not None:
        if trap["kind"] == "non_commercial":
            raise LicenseViolation(f"asset '{asset_id}' uses non-commercial source '{model_key}': {trap['note']}")
        if trap["kind"] == "territory":
            excluded = trap.get("territories", ())
            if target_territory and target_territory in excluded:
                raise LicenseViolation(
                    f"asset '{asset_id}' source '{model_key}' is not licensed in "
                    f"'{target_territory}': {trap['note']}"
                )
            mau_cap = trap.get("mau_cap")
            if mau_cap is not None and expected_mau > mau_cap:
                raise LicenseViolation(
                    f"asset '{asset_id}' source '{model_key}' exceeds its MAU cap "
                    f"({expected_mau} > {mau_cap}): {trap['note']}"
                )
        if trap["kind"] == "traffic_cap":
            visits_cap = trap.get("traffic_cap_visits_month")
            if visits_cap is not None and expected_visits_month > visits_cap:
                raise LicenseViolation(
                    f"asset '{asset_id}' source '{model_key}' exceeds its monthly traffic cap "
                    f"({expected_visits_month} > {visits_cap}): {trap['note']}"
                )


def check_assets(assets: list[dict], **kwargs: Any) -> None:
    """Run :func:`check_asset_license` over *assets*, failing on the first trap.

    Named-asset failure is deliberate: the guard stops at the first offending
    asset and reports it, rather than silently continuing (ASUR-GATE-01).
    """
    for asset in assets:
        check_asset_license(asset, **kwargs)
