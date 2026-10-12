"""V1b — human-gated collector for the viral-check correlation study (SPEC-GAP G30).

> HUMAN-GATED TOOL. This script lives OUTSIDE the `asur/` package on purpose:
> the ASUR constitution keeps the core 100% local and key-free (ASUR-LOCAL-01) and
> forbids any test from touching the network (§4). Gathering real public clips and
> their public view counts IS a network action with your own browser/credentials, so
> that step stays in *your* hands. This tool never logs in, never calls a platform
> API, and is never imported by the core or run by pytest.

What it does
------------
Turns a human-prepared input list into the exact on-disk dataset schema the blind
scorer (`asur.viral_check.validation.score_blind`) and the offline correlator
(`asur.viral_check.validation.correlate`) already expect:

    validation/<study_id>/
        clip_meta.json          observable metadata only, NO view counts
        views.sealed.json       public view counts, SEALED (scorer never opens this)
        ratings/<clip_id>.json   empty blind-rating stubs for a human to fill
        clips/                   (you drop the downloaded <clip_id>.mp4 files here)

It does NOT score, does NOT derive facts, and does NOT reveal the sealed views. The
sealed file is written last and is the only place view counts live, so a blind rater
or the scorer can work without ever seeing an outcome (ASUR-HONEST-01).

The input list (JSON)
---------------------
A single JSON file you build by hand while browsing public creators' clips:

    {
      "study_id": "study-2026-02",
      "platform": "public-reels",
      "clips": [
        {"clip_id": "clip-001", "source_url": "https://.../reel/abc",
         "public_views": 50000,
         "pre_derived": {"aspect_ratio": "9:16", "low_resolution": false,
                         "muted": false}}
      ]
    }

`public_views` is REQUIRED per clip (public view count only — no private
watch-time/retention for public-creator clips). `pre_derived` is optional; if you omit
it you can let the scorer's `derive.probe_clip` read the real .mp4 via ffprobe later.
Nothing here is invented: every field is something you observed (§7).

Usage
-----
    python3 studio/validation/collect.py --input my_list.json --out validation

Then: drop each clip's .mp4 into validation/<study_id>/clips/<clip_id>.mp4, have a
rater fill validation/<study_id>/ratings/<clip_id>.json WITHOUT looking at the sealed
views, run the blind scorer, then the correlator.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

_BANNER = """\
================================================================================
ASUR VALIDATION COLLECTOR  (V1b, human-gated)
--------------------------------------------------------------------------------
This tool writes a correlation-study dataset from a list YOU prepared by browsing
public clips. It does NOT log in, call any platform API, or download anything.
It does NOT score and NEVER reveals the sealed view counts.

Per ASUR-LOCAL-01 / ASUR-HONEST-01:
  * View counts are written ONLY into views.sealed.json (the blind scorer never
    reads that file).
  * Blind ratings stubs are left EMPTY for a human who has not seen the views.
  * Every field must be something you actually observed - nothing is invented.
================================================================================"""

_UTC = datetime.timezone.utc


def _now_iso() -> str:
    return datetime.datetime.now(tz=_UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, payload: dict) -> None:
    """Refuse to overwrite: append-only, nothing silently clobbered (ASUR-VERSION-01)."""
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing file: {path}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_input(input_path: Path) -> dict:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("input list must be a JSON object")
    study_id = data.get("study_id")
    if not isinstance(study_id, str) or not study_id.strip():
        raise ValueError("input list is missing a non-empty 'study_id'")
    clips = data.get("clips")
    if not isinstance(clips, list) or not clips:
        raise ValueError("input list 'clips' must be a non-empty array")
    seen: set[str] = set()
    for i, clip in enumerate(clips):
        if not isinstance(clip, dict):
            raise TypeError(f"clips[{i}] must be an object")
        clip_id = clip.get("clip_id")
        if not isinstance(clip_id, str) or not clip_id.strip():
            raise ValueError(f"clips[{i}] is missing a non-empty 'clip_id'")
        if clip_id in seen:
            raise ValueError(f"duplicate clip_id: {clip_id}")
        seen.add(clip_id)
        views = clip.get("public_views")
        # Fail closed: a clip with no observed view count cannot enter the study.
        if not isinstance(views, int) or isinstance(views, bool) or views < 0:
            raise ValueError(
                f"clips[{i}] ({clip_id}) needs an integer 'public_views' >= 0 "
                "(public view count you observed)"
            )
    return data


def collect(input_path: Path, out_root: Path) -> Path:
    """Build the sealed dataset from a human-prepared input list; return the study dir."""
    data = _load_input(input_path)
    study_id = data["study_id"]
    platform = data.get("platform", "public")
    clips = data["clips"]

    study_dir = out_root / study_id
    if study_dir.exists():
        raise FileExistsError(
            f"study directory already exists: {study_dir} "
            "(studies are append-only; pick a new study_id)"
        )
    (study_dir / "ratings").mkdir(parents=True)
    (study_dir / "clips").mkdir()

    collected_at = _now_iso()
    meta_clips: list[dict] = []
    sealed_views: dict[str, int] = {}
    for clip in clips:
        clip_id = clip["clip_id"]
        entry: dict = {"clip_id": clip_id, "collected_at": collected_at}
        if "source_url" in clip:
            entry["source_url"] = clip["source_url"]
        if isinstance(clip.get("pre_derived"), dict):
            entry["pre_derived"] = clip["pre_derived"]
        meta_clips.append(entry)
        sealed_views[clip_id] = clip["public_views"]
        # Empty blind-rating stub: a human fills the judgment booleans WITHOUT
        # ever seeing views. Missing keys stay missing (derive omits, never invents).
        _write_json(
            study_dir / "ratings" / f"{clip_id}.json",
            {
                "clip_id": clip_id,
                "rater_id": None,
                "rated_at": None,
                "blind": True,
                "judgments": {},
            },
        )

    # Observable metadata only - NO view counts live here.
    _write_json(
        study_dir / "clip_meta.json",
        {
            "study_id": study_id,
            "platform": platform,
            "collected_at": collected_at,
            "note": (
                "Observable metadata only; view counts are sealed in "
                "views.sealed.json and must not be read while scoring."
            ),
            "clips": meta_clips,
        },
    )

    # Written LAST and on its own: the sealed outcome the scorer never opens.
    _write_json(
        study_dir / "views.sealed.json",
        {
            "note": (
                "SEALED OUTCOME. The blind scorer MUST NEVER read this file. "
                "Public view counts only. Unsealed only by the offline "
                "correlation step."
            ),
            "sealed_at": collected_at,
            "metric": "public_views",
            "views": sealed_views,
        },
    )
    return study_dir


def main(argv: list[str] | None = None) -> int:
    print(_BANNER, file=sys.stderr)
    ap = argparse.ArgumentParser(
        prog="studio/validation/collect.py",
        description="Build a sealed viral-check correlation-study dataset (human-gated).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--input", required=True, help="human-prepared JSON clip list")
    ap.add_argument("--out", default="validation",
                    help="output root for validation/<study_id>/ (default: validation)")
    args = ap.parse_args(argv)

    try:
        study_dir = collect(Path(args.input).expanduser(), Path(args.out).expanduser())
    except (FileExistsError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"collect failed (fail closed): {exc}", file=sys.stderr)
        return 1

    clip_count = len(json.loads((study_dir / "clip_meta.json").read_text(encoding="utf-8"))["clips"])
    print(f"wrote study dataset: {study_dir}")
    print(f"  clip_meta.json      ({clip_count} clips, observable metadata only)")
    print("  views.sealed.json   (public view counts, SEALED)")
    print(f"  ratings/            ({clip_count} empty blind-rating stubs to fill)")
    print("  clips/              (drop each <clip_id>.mp4 here)")
    print("\nnext (all human-driven):")
    print("  1. download each clip's .mp4 into clips/ as <clip_id>.mp4")
    print("  2. a rater fills ratings/<clip_id>.json WITHOUT opening views.sealed.json")
    print("  3. python3 -c \"from asur.viral_check.validation import score_blind; "
          f"score_blind.score_study(__import__('pathlib').Path('{study_dir}'))\"")
    print("  4. python3 -c \"from asur.viral_check.validation import correlate; "
          f"print(correlate.correlate(__import__('pathlib').Path('{study_dir}'))['dimensions'])\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
