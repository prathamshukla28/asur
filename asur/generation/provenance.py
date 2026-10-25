"""Provenance + license schema guard - makes ASUR-PROV-01 real for EVERY asset.

ASUR-PROV-01 says every media asset carries its origin, model, inputs, transforms,
and a license block. Until now only the renderer's own block was checked; the
``DEFERRED`` register flagged that nothing schema-validated the *other* produced
assets. This module closes that: it fails closed (``ProvenanceError``) unless
every produced asset carries the complete, structurally-valid block that the rest
of the pipeline - especially ``license_guard`` - depends on.

Stdlib only, no network. The required shape is deliberately the minimum the
system actually relies on, so it never false-positives on a legitimately
produced asset while still refusing a black box (ASUR-GATE-01, ASUR-EXPLAIN-01):

    {
      "media_type": <non-empty str>,          # what kind of asset
      "file_path":  <non-empty str>,           # where it is on disk
      "provenance": {"model": <non-empty str>, ...},   # how it was made
      "license":    {"name": <non-empty str>, "commercial_ok": <bool>, ...},
    }
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ProvenanceError",
    "validate_asset_provenance",
    "validate_produced_assets",
]


class ProvenanceError(ValueError):
    """Raised (fail-closed) when an asset's provenance/license block is incomplete.

    Maps to gate disposition BLOCK, substate PROVENANCE_INCOMPLETE. The message
    always names the asset and the missing/invalid field (ASUR-EXPLAIN-01).
    """


def _asset_name(asset: dict) -> str:
    for key in ("asset_id", "asset_ref", "file_path", "target_asset"):
        value = asset.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "<unnamed-asset>"


def _require_nonempty_str(value: Any, *, name: str, where: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ProvenanceError(
            f"asset '{where}' is missing a non-empty '{name}' "
            "(ASUR-PROV-01 fails closed)"
        )


def validate_asset_provenance(asset: Any) -> None:
    """Raise :class:`ProvenanceError` unless *asset* carries the full block.

    Returns ``None`` when the asset is complete. The checks mirror exactly what
    ``license_guard`` reads (``provenance.model``, ``license.name``,
    ``license.commercial_ok``), so a validated asset is a license-checkable one.
    """
    if not isinstance(asset, dict):
        raise ProvenanceError(
            f"produced asset is not a provenance block (got {type(asset).__name__}); "
            "ASUR-PROV-01 fails closed"
        )

    where = _asset_name(asset)
    _require_nonempty_str(asset.get("media_type"), name="media_type", where=where)
    _require_nonempty_str(asset.get("file_path"), name="file_path", where=where)

    provenance = asset.get("provenance")
    if not isinstance(provenance, dict):
        raise ProvenanceError(
            f"asset '{where}' has no 'provenance' block (ASUR-PROV-01 fails closed)"
        )
    _require_nonempty_str(
        provenance.get("model"), name="provenance.model", where=where
    )

    license_block = asset.get("license")
    if not isinstance(license_block, dict):
        raise ProvenanceError(
            f"asset '{where}' has no 'license' block (ASUR-PROV-01 fails closed)"
        )
    _require_nonempty_str(
        license_block.get("name"), name="license.name", where=where
    )
    if not isinstance(license_block.get("commercial_ok"), bool):
        raise ProvenanceError(
            f"asset '{where}' license must declare a boolean 'commercial_ok' "
            "(undeclared is unsafe; ASUR-PROV-01 fails closed)"
        )


def validate_produced_assets(produced: dict) -> None:
    """Validate every asset in a ``produce_assets`` result, failing on the first gap.

    ``produced`` is the grouped dict returned by
    :func:`asur.generation.produce.produce_assets`; its ``assets`` list holds the
    provenance+license block for each produced file. Stops at the first offending
    asset and names it rather than silently continuing (ASUR-GATE-01).
    """
    assets = produced.get("assets") if isinstance(produced, dict) else None
    if not isinstance(assets, list):
        raise ProvenanceError(
            "produced result has no 'assets' list to validate "
            "(ASUR-PROV-01 fails closed)"
        )
    for asset in assets:
        validate_asset_provenance(asset)
