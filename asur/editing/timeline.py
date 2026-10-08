"""Timeline model (EDITING environment, DATA_MODELS.md section 5).

A Timeline is a first-class, versioned entity. Every clip carries a stable
identity and a ``version_history`` so no edit is ever silently overwritten
(ASUR-VERSION-01). The model is pure stdlib dicts/dataclasses: it serializes to
plain JSON-safe structures and can round-trip losslessly through its own
``to_dict`` / ``from_dict`` without any third-party library. Hand-off to OTIO
(a media dependency) lives in ``asur.editing.adapters.otio`` only.

Shape (9:16 Instagram Reel): resolution 1080x1920, fps 30. Track/clip types:
video, audio, text (captions), graphics, effects, transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.canonical import canonical_sha256
from ..core.envelope import Artifact, make_artifact
from ..core.identity import Identity
from . import source_ref

REEL_WIDTH = 1080
REEL_HEIGHT = 1920
REEL_FPS = 30

TRACK_TYPES = ("video", "audio", "text", "graphics", "effects", "transitions")


def _short_id(prefix: str, seed: str) -> str:
    """Deterministic stable id ``<prefix>-<12 hex>`` derived from *seed*."""
    return f"{prefix}-{canonical_sha256(seed)[:12]}"


@dataclass
class Clip:
    """One editable clip on a track. Every field a human can change is here, and
    every change appends the prior state to ``version_history`` (never mutated in
    place destructively)."""

    clip_id: str
    asset_ref: str
    in_point: float = 0.0
    out_point: float = 0.0
    timeline_start: float = 0.0
    speed: float = 1.0
    keyframes: dict = field(default_factory=lambda: {"scale": [], "position": [], "opacity": []})
    crop: dict = field(default_factory=dict)
    masks: list = field(default_factory=list)
    overlays: list = field(default_factory=list)
    primitive: str | None = None
    locked: bool = False
    review: str | None = None
    version_history: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "clip_id": self.clip_id,
            "asset_ref": self.asset_ref,
            "in": self.in_point,
            "out": self.out_point,
            "timeline_start": self.timeline_start,
            "speed": self.speed,
            "keyframes": self.keyframes,
            "crop": self.crop,
            "masks": self.masks,
            "overlays": self.overlays,
            "primitive": self.primitive,
            "locked": self.locked,
            "review": self.review,
            "version_history": self.version_history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Clip:
        return cls(
            clip_id=data["clip_id"],
            asset_ref=data["asset_ref"],
            in_point=float(data.get("in", 0.0)),
            out_point=float(data.get("out", 0.0)),
            timeline_start=float(data.get("timeline_start", 0.0)),
            speed=float(data.get("speed", 1.0)),
            keyframes=data.get("keyframes", {"scale": [], "position": [], "opacity": []}),
            crop=data.get("crop", {}),
            masks=data.get("masks", []),
            overlays=data.get("overlays", []),
            primitive=data.get("primitive"),
            locked=bool(data.get("locked", False)),
            review=data.get("review"),
            version_history=data.get("version_history", []),
        )

    def _snapshot(self) -> dict:
        """A copy of the current editable state (excluding version_history) to
        push onto version_history before a change."""
        snap = self.to_dict()
        snap.pop("version_history", None)
        return snap


@dataclass
class Track:
    track_id: str
    type: str
    clips: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "type": self.type,
            "clips": [c.to_dict() for c in self.clips],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Track:
        return cls(
            track_id=data["track_id"],
            type=data["type"],
            clips=[Clip.from_dict(c) for c in data.get("clips", [])],
        )


@dataclass
class Timeline:
    """Versioned 9:16 Reel timeline. ``version`` increments each time an edit is
    committed; the whole prior document is retained by the workspace envelope
    (append-only) and per-clip history by ``Clip.version_history``."""

    timeline_id: str
    project_id: str
    version: int = 1
    fps: int = REEL_FPS
    width: int = REEL_WIDTH
    height: int = REEL_HEIGHT
    duration_s: float = 0.0
    tracks: list = field(default_factory=list)
    markers: list = field(default_factory=list)
    scenes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timeline_id": self.timeline_id,
            "project_id": self.project_id,
            "version": self.version,
            "fps": self.fps,
            "resolution": {"w": self.width, "h": self.height},
            "duration_s": self.duration_s,
            "tracks": [t.to_dict() for t in self.tracks],
            "markers": self.markers,
            "scenes": self.scenes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Timeline:
        res = data.get("resolution", {"w": REEL_WIDTH, "h": REEL_HEIGHT})
        return cls(
            timeline_id=data["timeline_id"],
            project_id=data["project_id"],
            version=int(data.get("version", 1)),
            fps=int(data.get("fps", REEL_FPS)),
            width=int(res.get("w", REEL_WIDTH)),
            height=int(res.get("h", REEL_HEIGHT)),
            duration_s=float(data.get("duration_s", 0.0)),
            tracks=[Track.from_dict(t) for t in data.get("tracks", [])],
            markers=data.get("markers", []),
            scenes=data.get("scenes", []),
        )

    def find_clip(self, clip_id: str) -> Clip | None:
        for track in self.tracks:
            for clip in track.clips:
                if clip.clip_id == clip_id:
                    return clip
        return None


def build_timeline_from_generation_plan(
    generation_plan_artifact: Artifact,
    visual_screenplay_artifact: Artifact,
    project_id: str,
) -> Timeline:
    """Assemble an initial 9:16 timeline from a generation plan + screenplay.

    One video/graphics clip per planned asset, scenes carried from the
    screenplay, plus the shared voice and music tracks. Deterministic ids so the
    same inputs always yield the same timeline (reproducibility, ASUR-EXPLAIN-01).
    """
    gp = generation_plan_artifact.body or {}
    sp = visual_screenplay_artifact.body or {}
    subject = gp.get("subject", "")
    timeline_id = _short_id("tl", f"{project_id}|{subject}")

    video_track = Track(track_id="trk-video-1", type="video")
    text_track = Track(track_id="trk-captions", type="text")
    voice_track = Track(track_id="trk-audio-voice", type="audio")
    music_track = Track(track_id="trk-audio-music", type="audio")

    scenes = sp.get("scenes", [])
    scene_spans: dict[str, tuple[float, float]] = {}
    tl_scenes: list[dict] = []
    for scene in scenes:
        sid = scene.get("scene_id", "")
        start = float(scene.get("start", 0.0))
        end = float(scene.get("end", 0.0))
        scene_spans[sid] = (start, end)
        tl_scenes.append({"scene_id": sid, "start": start, "end": end})

    duration = max((end for (_, end) in scene_spans.values()), default=0.0)

    for job in gp.get("jobs", []):
        asset_ref = job.get("target_asset", "")
        media_type = job.get("params", {}).get("media_type", "")
        start = 0.0
        end = 0.0
        for sid, (s, e) in scene_spans.items():
            if asset_ref.startswith(sid):
                start, end = s, e
                break
        clip = Clip(
            clip_id=_short_id("clip", f"{timeline_id}|{asset_ref}"),
            asset_ref=asset_ref,
            in_point=0.0,
            out_point=max(end - start, 0.0),
            timeline_start=start,
        )
        if asset_ref == "voice-track":
            clip.out_point = duration
            voice_track.clips.append(clip)
        elif asset_ref == "music-bed":
            clip.out_point = duration
            music_track.clips.append(clip)
        elif media_type == "graphic" or asset_ref.endswith("-onscreen-text"):
            text_track.clips.append(clip)
        else:
            video_track.clips.append(clip)

    tracks = [t for t in (video_track, text_track, voice_track, music_track) if t.clips]
    return Timeline(
        timeline_id=timeline_id,
        project_id=project_id,
        version=1,
        duration_s=duration,
        tracks=tracks,
        markers=[],
        scenes=tl_scenes,
    )


def build_edit_plan(
    timeline: Timeline,
    generation_plan_artifact: Artifact,
    project_id: str,
    *,
    note: str = "initial assembly",
    identity: Identity | None = None,
) -> Artifact:
    """Wrap a Timeline as a versioned ``edit_plan`` artifact (ASUR-VERSION-01).

    The timeline dict lives in the artifact body; the workspace keeps every
    saved version append-only, and the body round-trips losslessly.
    """
    body: dict[str, Any] = {
        "subject": (generation_plan_artifact.body or {}).get("subject", ""),
        "note": note,
        "timeline": timeline.to_dict(),
        "clip_count": sum(len(t.clips) for t in timeline.tracks),
        "method": "local deterministic assembly from generation_plan; no network",
    }
    return make_artifact(
        kind="edit_plan",
        project_id=project_id,
        body=body,
        status="ready",
        sources=[source_ref(generation_plan_artifact)],
        agent="editing",
        identity=identity,
    )
