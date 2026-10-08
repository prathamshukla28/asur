"""Read human-recorded performance metrics from a file on disk (Stage 26 front door).

The creator reads their real numbers off the platform's own analytics screen and
saves them to a small file - JSON like {"views": 48000, "completion_pct": 28} or a
two-column CSV `key,value`. This module opens that local file and hands the numbers
to build_performance(). It never reaches the network (ASUR-LOCAL-01) and uses no
third-party parser (stdlib json/csv only - no pandas). It fails closed on a missing
or unreadable file rather than inventing numbers (ASUR-GATE-01, ASUR-HONEST-01).

This closes the PERFORMANCE -> LEARNING loop on disk: a saved metrics file turns
into a performance artifact, which the learning fold compares against the viral-check
prediction and folds back into SCRIPT memory to inform the next idea.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

from ..core.envelope import Artifact
from ..core.identity import Identity
from .performance import build_performance


class MetricsFileError(RuntimeError):
    """A metrics file could not be read or parsed - fail closed, do not invent."""


def _coerce(value: object) -> object:
    """Turn a CSV string into an int/float when it clearly is one; else keep as-is."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def read_metrics_file(path: str) -> dict:
    """Load a local metrics file (.json or .csv) into a plain dict. No network.

    JSON: a single object of metric_name -> number.
    CSV : rows of `key,value` (an optional header row named key,value is skipped).
    """
    p = Path(path)
    if not p.is_file():
        raise MetricsFileError(f"metrics file not found: {path}")

    suffix = p.suffix.lower()
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - unreadable file
        raise MetricsFileError(f"could not read metrics file {path}: {exc}") from exc

    if suffix == ".json":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MetricsFileError(f"invalid JSON in {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise MetricsFileError(f"metrics JSON must be an object, got {type(data).__name__}")
        return dict(data)

    if suffix == ".csv":
        metrics: dict = {}
        for row in csv.reader(raw.splitlines()):
            if not row or len(row) < 2:
                continue
            key = row[0].strip()
            if not key or (key.lower() == "key" and row[1].strip().lower() == "value"):
                continue  # skip blanks and a header row
            metrics[key] = _coerce(row[1])
        if not metrics:
            raise MetricsFileError(f"no key,value rows found in {path}")
        return metrics

    raise MetricsFileError(f"unsupported metrics file type {suffix!r} (use .json or .csv)")


def build_performance_from_file(
    publish_package_artifact: Artifact,
    metrics_path: str,
    project_id: str,
    *,
    identity: Optional[Identity] = None,
) -> Artifact:
    """Disk front door: read a metrics file, then build the performance artifact.

    Thin wrapper over build_performance - the only new thing is the local file read.
    """
    metrics = read_metrics_file(metrics_path)
    return build_performance(
        publish_package_artifact,
        metrics,
        project_id,
        identity=identity,
    )
