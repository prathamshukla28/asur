"""V1a viral-check empirical-validation spine (blind correlation study).

Covers the three pure-stdlib pieces that let us PROVE (not predict) whether
the viral-check input-quality score tracks real public-view performance:

  derive.derive_platform_facts  - observable facts + blind human judgments,
                                  never invented (missing judgment -> omitted).
  score_blind.score_study       - scores every clip through the REAL evaluator
                                  while the view counts stay sealed on disk.
  correlate.correlate           - unseals views and computes a per-dimension
                                  Spearman rank correlation + an honest report
                                  that NEVER contains a single %viral number.

All fixture-driven: no ffprobe, no model, no network, no GPU (ASUR-LOCAL-01,
AGENTS section 4). The fixture lives under tests/fixtures/viral_validation/.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from asur.tools.projection import FirewallLeak
from asur.viral_check.dimensions import DIMENSIONS
from asur.viral_check.evaluate import PASS, PASS_WITH_CHANGES, REJECT
from asur.viral_check.validation import correlate, derive, score_blind

_FIXTURE = Path(__file__).parent / "fixtures" / "viral_validation" / "demo-study"

_VERDICTS = {PASS, PASS_WITH_CHANGES, REJECT}

# ASUR-HONEST-01: a validation report must never roll the twelve dimensions
# up into a single "how viral" number.
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


@pytest.fixture
def study_dir(tmp_path: Path) -> Path:
    """A writable copy of the fixture study (scores/ and report are produced)."""
    dest = tmp_path / "demo-study"
    shutil.copytree(_FIXTURE, dest)
    return dest


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# derive_platform_facts
# --------------------------------------------------------------------------- #

def test_derive_uses_blind_judgments_and_observable_facts() -> None:
    ratings = {
        "strong_first_three_seconds": True,
        "delivers_promise": True,
        "captions_present": True,
    }
    probe = {"aspect_ratio": "9:16", "low_resolution": False, "muted": False}
    facts = derive.derive_platform_facts("clip-01.mp4", ratings=ratings, probe=probe)
    assert facts["strong_first_three_seconds"] is True
    assert facts["delivers_promise"] is True
    assert facts["captions_present"] is True
    assert facts["aspect_ratio"] == "9:16"
    assert facts["low_resolution"] is False


def test_derive_omits_missing_judgment_never_invents() -> None:
    # clip-04 fixture omits delivers_promise on purpose.
    ratings = {"strong_first_three_seconds": False, "captions_present": False}
    probe = {"aspect_ratio": "9:16", "low_resolution": False, "muted": False}
    facts = derive.derive_platform_facts("clip-04.mp4", ratings=ratings, probe=probe)
    # Missing judgment -> fact omitted so the dimension stays at baseline.
    assert "delivers_promise" not in facts
    assert facts["strong_first_three_seconds"] is False


def test_derive_captions_unknown_when_extra_absent() -> None:
    # No captions judgment and no caption model available => 'unknown',
    # never a guessed True/False.
    ratings = {"strong_first_three_seconds": True, "delivers_promise": True}
    probe = {"aspect_ratio": "9:16", "low_resolution": False, "muted": False}
    facts = derive.derive_platform_facts(
        "clip.mp4", ratings=ratings, probe=probe, captions_probe=None
    )
    assert facts.get("captions_present") == "unknown"


def test_derive_output_passes_the_firewall_but_a_target_name_fails_closed() -> None:
    ratings = {"strong_first_three_seconds": True}
    probe = {"aspect_ratio": "9:16", "low_resolution": False, "muted": False}
    # A clean observable fact set must survive the VIRAL_VIEW firewall scan.
    facts = derive.derive_platform_facts("clip.mp4", ratings=ratings, probe=probe)
    assert isinstance(facts, dict)
    # Injecting a quality-target name must fail closed when scored.
    poisoned = dict(facts)
    poisoned["target_score"] = 90
    with pytest.raises(FirewallLeak):
        score_blind.score_one("poison", poisoned)


# --------------------------------------------------------------------------- #
# score_study  (blind: must never read the sealed views)
# --------------------------------------------------------------------------- #

def test_score_study_scores_every_clip_with_twelve_dimensions(study_dir: Path) -> None:
    score_blind.score_study(study_dir)
    scores_dir = study_dir / "scores"
    produced = sorted(p.stem for p in scores_dir.glob("*.json"))
    assert produced == ["clip-01", "clip-02", "clip-03", "clip-04", "clip-05"]
    body = _load(scores_dir / "clip-01.json")
    assert [d["dimension"] for d in body["dimensions"]] == list(DIMENSIONS)
    assert body["verdict"] in _VERDICTS
    # No rolled-up aggregate anywhere.
    for key in _FORBIDDEN_AGGREGATE_KEYS:
        assert key not in body


def test_weakest_clip_is_rejected(study_dir: Path) -> None:
    score_blind.score_study(study_dir)
    body = _load(study_dir / "scores" / "clip-05.json")
    # clip-05: low_resolution + 1:1 aspect => hard flag => REJECT.
    assert body["verdict"] == REJECT


def test_score_study_never_opens_the_sealed_views(
    study_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sealed = (study_dir / "views.sealed.json").resolve()
    real_open = Path.open

    def guarded_open(self: Path, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        if self.resolve() == sealed:
            raise AssertionError("blind scorer opened the sealed view counts")
        return real_open(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "open", guarded_open)

    real_builtin_open = open

    def guarded_builtin_open(file, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        try:
            resolved = Path(file).resolve()
        except TypeError:
            resolved = None
        if resolved == sealed:
            raise AssertionError("blind scorer opened the sealed view counts")
        return real_builtin_open(file, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("builtins.open", guarded_builtin_open)

    score_blind.score_study(study_dir)  # must not touch views.sealed.json


# --------------------------------------------------------------------------- #
# correlate  (offline: unseals views, Spearman per dimension, honest report)
# --------------------------------------------------------------------------- #

def test_correlate_produces_report_with_per_dimension_spearman(study_dir: Path) -> None:
    score_blind.score_study(study_dir)
    report = correlate.correlate(study_dir)
    assert (study_dir / "report.json").is_file()
    assert (study_dir / "report.md").is_file()
    dims = {row["dimension"]: row for row in report["dimensions"]}
    assert set(dims) == set(DIMENSIONS)
    for row in report["dimensions"]:
        assert row["spearman"] is None or -1.0 <= row["spearman"] <= 1.0  # unmeasured -> None
    assert report["sample_size"] == 5
    assert report["metric"] == "public_views"


def test_attention_dimension_tracks_views_in_fixture(study_dir: Path) -> None:
    # Fixture is built so Attention descends with views (clip-01..clip-05),
    # giving a strong positive rank correlation.
    score_blind.score_study(study_dir)
    report = correlate.correlate(study_dir)
    attention = next(r for r in report["dimensions"] if r["dimension"] == "Attention")
    assert attention["spearman"] > 0.5


def test_spearman_is_deterministic_on_known_ranks() -> None:
    # Perfect monotone increase => rho == 1.0.
    assert correlate.spearman([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]) == pytest.approx(1.0)
    # Perfect monotone decrease => rho == -1.0.
    assert correlate.spearman([1, 2, 3, 4, 5], [50, 40, 30, 20, 10]) == pytest.approx(-1.0)
    # Tie handling (average ranks): known value.
    assert correlate.spearman([1, 1, 2, 3], [1, 2, 3, 4]) == pytest.approx(0.9486833, abs=1e-6)


def test_report_has_no_viral_percentage_or_aggregate(study_dir: Path) -> None:
    score_blind.score_study(study_dir)
    correlate.correlate(study_dir)
    report_text = (study_dir / "report.json").read_text(encoding="utf-8")
    md_text = (study_dir / "report.md").read_text(encoding="utf-8")
    assert "%" not in report_text
    assert "%" not in md_text
    body = _load(study_dir / "report.json")

    def walk(obj: object):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from walk(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                yield from walk(item)

    keys = {str(k).casefold() for k in walk(body)}
    for forbidden in _FORBIDDEN_AGGREGATE_KEYS:
        assert forbidden not in keys


def test_report_carries_honest_caveats(study_dir: Path) -> None:
    score_blind.score_study(study_dir)
    report = correlate.correlate(study_dir)
    caveats = " ".join(report["caveats"]).casefold()
    assert "correlation" in caveats
    assert "serendipit" in caveats or "probabilistic" in caveats
