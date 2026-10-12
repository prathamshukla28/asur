"""Offline correlation report for the validation study (SPEC-GAP G30).

Runs AFTER the blind scoring pass. It unseals the observed view counts, joins
them to the per-clip scores, and reports a per-dimension Spearman rank
correlation between each dimension's input-quality score and real public
views. It is a CORRELATION STUDY, never a predictor:

  - No single "%viral" number and no aggregate score is ever produced
    (ASUR-HONEST-01). The report carries twelve per-dimension correlations
    plus honest caveats, and contains no "%" character at all.
  - Correlation is not causation and per-video reach is partly serendipitous;
    those caveats are written into every report.

Stdlib-only, pure math (no numpy/scipy): Spearman = Pearson on average ranks.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..dimensions import DIMENSIONS

METRIC = "public_views"

# Aggregate keys that would smuggle a single "viral score" back in. The report
# is walked in tests to prove none of these ever appear (ASUR-HONEST-01).
_FORBIDDEN_AGGREGATE_KEYS = (
    "viral_score",
    "overall_score",
    "overall",
    "aggregate_score",
    "percent_viral",
    "viral_percent",
    "total_score",
    "final_score",
)

_CAVEATS = [
    (
        "This is a correlation study, not a predictor: it measures whether each "
        "dimension's input-quality score moves with observed views after the fact."
    ),
    "Correlation is not causation.",
    (
        "Per-video reach is probabilistic and partly serendipitous, so even a "
        "strong signal explains only part of the variance."
    ),
    (
        "Public view counts are the only outcome measured here; private "
        "watch-time and retention are not available for public clips."
    ),
    (
        "A per-dimension correlation is only as trustworthy as the sample size "
        "and the blind-rating discipline behind it."
    ),
]


def _average_ranks(values: list[float]) -> list[float]:
    """Rank values ascending; tied values share the mean of their ranks."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        # positions i..j are tied; average of 1-based ranks (i+1)..(j+1)
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0.0 or var_y == 0.0:
        return 0.0
    return cov / (var_x**0.5 * var_y**0.5)


def spearman(xs: list[float], ys: list[float]) -> float:
    """Spearman rank correlation = Pearson on average ranks.

    Returns 0.0 for fewer than two points or a constant series (no
    meaningful ordering), rather than raising, so the report degrades
    gracefully on a thin dimension.
    """
    if len(xs) != len(ys):
        raise ValueError("spearman: inputs must be the same length")
    if len(xs) < 2:
        return 0.0
    return _pearson(_average_ranks(list(xs)), _average_ranks(list(ys)))


def correlate(study_dir: str | Path) -> dict:
    """Unseal views, join to scores, report per-dimension Spearman + caveats.

    Writes ``report.json`` and ``report.md`` into ``study_dir`` and returns
    the report dict. No aggregate/%viral value is produced anywhere.
    """
    root = Path(study_dir)
    views = _load_sealed_views(root)
    scores = _load_scores(root)

    # Align clips present in BOTH views and scores, deterministic order.
    clip_ids = sorted(set(views) & set(scores))
    views_series = [float(views[c]) for c in clip_ids]

    dimension_rows: list[dict] = []
    for dim in DIMENSIONS:
        dim_scores = [float(_dim_score(scores[c], dim)) for c in clip_ids]
        rho = spearman(dim_scores, views_series)
        dimension_rows.append(
            {
                "dimension": dim,
                "spearman": round(rho, 6),
                "sample_size": len(clip_ids),
            }
        )

    report = {
        "study": root.name,
        "metric": METRIC,
        "sample_size": len(clip_ids),
        "dimensions": dimension_rows,
        "verdict_buckets": _verdict_buckets(scores, views, clip_ids),
        "caveats": list(_CAVEATS),
    }

    _assert_no_aggregate(report)
    (root / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (root / "report.md").write_text(_render_markdown(report), encoding="utf-8")
    return report


def _load_sealed_views(root: Path) -> dict:
    """Open the sealed outcome. ONLY the offline report may do this."""
    payload = json.loads((root / "views.sealed.json").read_text(encoding="utf-8"))
    views = payload.get("views")
    if not isinstance(views, dict):
        raise TypeError("views.sealed.json: missing 'views' mapping")
    return {str(k): v for k, v in views.items()}


def _load_scores(root: Path) -> dict:
    scores: dict = {}
    scores_dir = root / "scores"
    for path in sorted(scores_dir.glob("*.json")):
        scores[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return scores


def _dim_score(body: dict, dimension: str) -> int:
    for row in body.get("dimensions") or []:
        if row.get("dimension") == dimension:
            return int(row.get("score", 0))
    return 0


def _verdict_buckets(scores: dict, views: dict, clip_ids: list[str]) -> dict:
    """Group clips by verdict and report median views in each (honest, no %)."""
    buckets: dict = {}
    for clip_id in clip_ids:
        verdict = str(scores[clip_id].get("verdict", "UNKNOWN"))
        buckets.setdefault(verdict, []).append(float(views[clip_id]))
    out: dict = {}
    for verdict, series in buckets.items():
        out[verdict] = {
            "clips": len(series),
            "median_views": _median(series),
        }
    return out


def _median(series: list[float]) -> float:
    if not series:
        return 0.0
    ordered = sorted(series)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _assert_no_aggregate(report: dict) -> None:
    """Fail closed if any forbidden aggregate key leaked into the report."""
    for key in _walk_keys(report):
        if key.casefold() in _FORBIDDEN_AGGREGATE_KEYS:
            raise ValueError(
                f"correlation report leaked a forbidden aggregate key: {key}"
            )


def _walk_keys(obj) -> list[str]:
    keys: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.append(str(key))
            keys.extend(_walk_keys(value))
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            keys.extend(_walk_keys(item))
    return keys


def _render_markdown(report: dict) -> str:
    lines = [
        f"# Viral-check validation report - {report['study']}",
        "",
        (
            f"Outcome metric: **{report['metric']}** "
            f"(sample size {report['sample_size']})."
        ),
        "",
        (
            "Per-dimension Spearman rank correlation between the input-quality "
            "score and observed public views. This is a correlation study, not a "
            "predictor, and no single viral number is produced."
        ),
        "",
        "| Dimension | Spearman (score vs views) | Sample |",
        "| --- | --- | --- |",
    ]
    for row in report["dimensions"]:
        lines.append(
            f"| {row['dimension']} | {row['spearman']:+.3f} | {row['sample_size']} |"
        )
    lines += ["", "## Verdict buckets (median views)", ""]
    for verdict, info in sorted(report["verdict_buckets"].items()):
        lines.append(
            f"- **{verdict}**: {info['clips']} clip(s), "
            f"median views {info['median_views']:.0f}"
        )
    lines += ["", "## Honest caveats", ""]
    for caveat in report["caveats"]:
        lines.append(f"- {caveat}")
    lines.append("")
    return "\n".join(lines)
