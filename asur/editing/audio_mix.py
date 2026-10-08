"""Audio mix model (EDITING environment).

A Reel's audio is a mix of a voice track (narration), a music bed, and optional
SFX. The mix must keep the voice intelligible: the music ducks under the voice.
This module is pure data — it records levels and ducking intent; actual mixing
happens in a render adapter behind ``asur[generation]``. No audio is processed
here.
"""

from __future__ import annotations

from typing import Optional

# Reference levels in dBFS (0 = full scale, negative = quieter). Voice sits near
# the top; music sits well under it so narration stays intelligible. These are
# the structural defaults the checker enforces (ASUR-EXPLAIN-01).
DEFAULT_VOICE_DB = -3.0
DEFAULT_MUSIC_DB = -18.0
DEFAULT_SFX_DB = -12.0

# How far the music ducks (drops) while the voice is speaking.
DEFAULT_DUCK_DB = -8.0


def build_audio_mix(
    *,
    voice_db: float = DEFAULT_VOICE_DB,
    music_db: float = DEFAULT_MUSIC_DB,
    sfx_db: float = DEFAULT_SFX_DB,
    duck_db: float = DEFAULT_DUCK_DB,
    has_voice: bool = True,
    has_music: bool = True,
    has_sfx: bool = False,
) -> dict:
    """Build an audio-mix record (pure data; no processing)."""
    return {
        "voice": {"level_db": float(voice_db), "present": bool(has_voice)},
        "music": {"level_db": float(music_db), "present": bool(has_music)},
        "sfx": {"level_db": float(sfx_db), "present": bool(has_sfx)},
        "ducking": {
            "enabled": bool(has_voice and has_music),
            "duck_db": float(duck_db),
            "trigger": "voice",
        },
        "method": "local structural mix spec; render happens in a media adapter",
    }


def check_audio_mix(mix: dict) -> dict:
    """Structurally verify a mix: voice louder than ducked music (fail closed).

    Returns ``{ok, reasons}``. If a voice and a music bed are both present, the
    music's ducked level must stay below the voice level, or the narration gets
    buried (ASUR-GATE-01).
    """
    reasons: list[str] = []
    voice = mix.get("voice", {})
    music = mix.get("music", {})
    ducking = mix.get("ducking", {})

    if voice.get("present") and music.get("present"):
        voice_db = float(voice.get("level_db", 0.0))
        music_db = float(music.get("level_db", 0.0))
        duck_db = float(ducking.get("duck_db", 0.0))
        ducked_music = music_db + duck_db
        if ducked_music >= voice_db:
            reasons.append(
                f"ducked music {ducked_music}dB not below voice {voice_db}dB"
            )
        if not ducking.get("enabled"):
            reasons.append("voice+music present but ducking disabled")

    return {"ok": not reasons, "reasons": reasons}
