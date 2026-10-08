"""Media adapters for GENERATION - behind the ``asur[generation]`` extra.

These modules are the ONLY place third-party media libraries (FFmpeg/MoviePy,
ComfyUI, Wan 2.2, SDXL, Kokoro, Stable Audio, faster-whisper) are touched. They
are declaration-only shells: each adapter imports its heavy dependency **lazily,
inside the call**, and raises a clear error if the extra is not installed.

HARD RULES (AGENTS.md §4, ADR-0002):
  * The stdlib-only control path (creative_direction, visual_screenplay,
    asset_strategy, generation_plan, hero_proof, license_guard) NEVER imports
    anything from this package. That is why `adapters` is intentionally NOT in
    `tests/test_boundary.py` STDLIB_ONLY_PACKAGES - but nothing stdlib may import
    it either.
  * These adapters are NEVER called in tests (no GPU, no network, no real model
    in CI - SPEC-GAP G10). They exist so a human, locally, with
    `pip install -e '.[generation]'`, can run the real render.
  * Sora is removed and appears in no adapter (ADR-0004).
"""
