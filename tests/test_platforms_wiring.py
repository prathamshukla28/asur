"""P09b wiring tests - the platform pack reaches the two hard-coded 9:16 seams.

These are the FAILING-FIRST tests (AGENTS.md section 6) that drive P09b: the
behaviour-neutral P09a registry must now actually reach the two places that
hard-code 1080x1920 / '9:16':

  * ``asur.generation.final_qa`` - the ``platform`` QA family's dimensions +
    duration-band checks.
  * ``asur.learning.publish_package`` - the publish package's
    ``metadata.aspect_ratio``.

The contract that P09b must satisfy:

  * A ``platform=`` argument (string id, resolved through the registry) threads
    the selected pack's FormatSpec into both seams.
  * ABSENT / ``None`` / ``"instagram_reels"`` => today's exact numbers
    (1080x1920, '9:16', no duration band). The 247 existing tests stay
    byte-identical because the Instagram pack reproduces them.
  * An unknown platform id FAILS CLOSED (ASUR-GATE-01) - never a silent default.

No network, no GPU, stdlib only.
"""

from __future__ import annotations

import pytest

from asur.core.envelope import make_artifact
from asur.generation import final_qa
from asur.learning.publish_package import build_publish_package
from asur.platforms import UnknownPlatform, get_platform

# --------------------------------------------------------------------------- #
# final_qa.platform_family - dimensions keyed off the selected pack            #
# --------------------------------------------------------------------------- #

def test_platform_family_defaults_to_instagram_1080x1920_pass():
    """No platform arg => today's Instagram behaviour: 1080x1920 PASSES."""
    fam = final_qa.platform_family(width=1080, height=1920, duration_s=30.0)
    dims = next(c for c in fam["checks"] if c["check"] == "dimensions")
    assert dims["status"] == "pass"
    assert fam["status"] == "pass"


def test_platform_family_instagram_rejects_landscape():
    """Under the IG default, a 16:9 landscape frame must still FAIL dimensions."""
    fam = final_qa.platform_family(width=1920, height=1080, duration_s=30.0)
    dims = next(c for c in fam["checks"] if c["check"] == "dimensions")
    assert dims["status"] == "fail"
    assert fam["status"] == "fail"


def test_platform_family_youtube_long_accepts_1920x1080():
    """With platform='youtube_long', a 1920x1080 landscape frame PASSES dims.

    This is the whole point of P09b: the dimensions check is keyed off the
    selected pack's FormatSpec, not a hard-coded 1080x1920.
    """
    fam = final_qa.platform_family(
        width=1920, height=1080, duration_s=480.0, platform="youtube_long"
    )
    dims = next(c for c in fam["checks"] if c["check"] == "dimensions")
    assert dims["status"] == "pass"


def test_platform_family_youtube_long_rejects_vertical():
    """A 9:16 vertical frame must FAIL under the 16:9 long-form pack."""
    fam = final_qa.platform_family(
        width=1080, height=1920, duration_s=480.0, platform="youtube_long"
    )
    dims = next(c for c in fam["checks"] if c["check"] == "dimensions")
    assert dims["status"] == "fail"


def test_platform_family_youtube_shorts_accepts_vertical():
    """YouTube Shorts is also 9:16/1080x1920 - the vertical frame PASSES."""
    fam = final_qa.platform_family(
        width=1080, height=1920, duration_s=45.0, platform="youtube_shorts"
    )
    dims = next(c for c in fam["checks"] if c["check"] == "dimensions")
    assert dims["status"] == "pass"


# --------------------------------------------------------------------------- #
# duration band comes from the pack's FormatSpec (G16 warn-not-fail)           #
# --------------------------------------------------------------------------- #

def test_platform_family_youtube_shorts_duration_in_band_pass():
    """45s is inside the Shorts band (15-60s) => duration_band PASSES."""
    fam = final_qa.platform_family(
        width=1080, height=1920, duration_s=45.0, platform="youtube_shorts"
    )
    band = next(c for c in fam["checks"] if c["check"] == "duration_band")
    assert band["status"] == "pass"


def test_platform_family_youtube_shorts_duration_out_of_band_warns_not_fails():
    """90s is outside the Shorts band => a WARNING, never a hard fail (G16)."""
    fam = final_qa.platform_family(
        width=1080, height=1920, duration_s=90.0, platform="youtube_shorts"
    )
    band = next(c for c in fam["checks"] if c["check"] == "duration_band")
    assert band["status"] == "warn"
    # A warn must not escalate the family to fail.
    assert fam["status"] != "fail"


def test_platform_family_instagram_has_no_duration_band_by_default():
    """The IG default declares no band => duration_band is a plain PASS."""
    fam = final_qa.platform_family(
        width=1080, height=1920, duration_s=600.0, platform="instagram_reels"
    )
    band = next(c for c in fam["checks"] if c["check"] == "duration_band")
    assert band["status"] == "pass"


def test_explicit_target_band_overrides_pack_band():
    """An explicit target_band_s argument still wins over the pack's band."""
    fam = final_qa.platform_family(
        width=1080,
        height=1920,
        duration_s=5.0,
        platform="youtube_shorts",
        target_band_s=(1.0, 10.0),
    )
    band = next(c for c in fam["checks"] if c["check"] == "duration_band")
    assert band["status"] == "pass"


# --------------------------------------------------------------------------- #
# run_final_qa / build_final_qa_report thread the platform through             #
# --------------------------------------------------------------------------- #

_APPROVED_REVIEWS = {
    "human_pass_test": "approved",
    "natural_motion": "approved",
    "skin_texture": "approved",
    "lighting_shadow_continuity": "approved",
    "physics_continuity": "approved",
    "color_grading": "approved",
    "voice_clear": "approved",
    "music_not_burying_voice": "approved",
    "no_clipping": "approved",
    "captions_readable": "approved",
    "safe_area_respected": "approved",
    "shaping_correct": "approved",
    "matches_approved_script": "approved",
    "no_drift_from_hero_proof": "approved",
}


def test_run_final_qa_youtube_long_landscape_ships():
    """A fully-approved 1920x1080 long-form render SHIPS under youtube_long."""
    result = final_qa.run_final_qa(
        width=1920,
        height=1080,
        duration_s=480.0,
        platform="youtube_long",
        reviews=_APPROVED_REVIEWS,
    )
    assert result["disposition"] == "SHIP"


def test_run_final_qa_landscape_blocks_under_instagram_default():
    """The same 1920x1080 render BLOCKS under the IG default (wrong dims)."""
    result = final_qa.run_final_qa(
        width=1920,
        height=1080,
        duration_s=480.0,
        reviews=_APPROVED_REVIEWS,
    )
    assert result["disposition"] == "BLOCK"


def test_build_final_qa_report_youtube_long_ships_ready():
    edit_plan = make_artifact(
        kind="edit_plan",
        project_id="proj-yt",
        body={"subject": "demo"},
        status="ready",
        agent="editing",
    )
    report = final_qa.build_final_qa_report(
        edit_plan,
        "proj-yt",
        width=1920,
        height=1080,
        duration_s=480.0,
        platform="youtube_long",
        reviews=_APPROVED_REVIEWS,
    )
    assert report.body["disposition"] == "SHIP"
    assert report.status == "ready"


def test_run_final_qa_unknown_platform_fails_closed():
    """An unknown platform id raises UnknownPlatform (ASUR-GATE-01)."""
    with pytest.raises(UnknownPlatform):
        final_qa.run_final_qa(
            width=1080,
            height=1920,
            duration_s=30.0,
            platform="tiktok",
            reviews=_APPROVED_REVIEWS,
        )


# --------------------------------------------------------------------------- #
# publish_package.metadata.aspect_ratio sourced from the pack                  #
# --------------------------------------------------------------------------- #

def _edit_and_viral():
    edit = make_artifact(
        kind="edit_plan",
        project_id="proj-pp",
        body={"subject": "demo", "clip_count": 3},
        status="ready",
        agent="editing",
    )
    viral = make_artifact(
        kind="viral_check",
        project_id="proj-pp",
        body={"verdict": "proceed"},
        status="ready",
        agent="viral-check",
    )
    return edit, viral


def test_publish_package_default_aspect_ratio_is_9_16():
    """No platform arg => metadata.aspect_ratio stays '9:16' (byte-identical)."""
    edit, viral = _edit_and_viral()
    pkg = build_publish_package(
        edit, viral, "proj-pp", title="t", caption="c"
    )
    assert pkg.body["metadata"]["aspect_ratio"] == "9:16"
    assert pkg.body["platform"] == "instagram_reels"


def test_publish_package_youtube_long_aspect_ratio_is_16_9():
    """platform='youtube_long' => metadata.aspect_ratio sourced from the pack."""
    edit, viral = _edit_and_viral()
    pkg = build_publish_package(
        edit, viral, "proj-pp", title="t", caption="c", platform="youtube_long"
    )
    assert pkg.body["metadata"]["aspect_ratio"] == "16:9"
    assert pkg.body["platform"] == "youtube_long"


def test_publish_package_aspect_ratio_matches_registry():
    """The aspect ratio always equals the registered pack's FormatSpec."""
    edit, viral = _edit_and_viral()
    for pid in ("instagram_reels", "youtube_shorts", "youtube_long"):
        pkg = build_publish_package(
            edit, viral, "proj-pp", title="t", caption="c", platform=pid
        )
        expected = get_platform(pid).format_spec.aspect_ratio
        assert pkg.body["metadata"]["aspect_ratio"] == expected


def test_publish_package_unknown_platform_fails_closed():
    """An unknown platform id raises UnknownPlatform (ASUR-GATE-01)."""
    edit, viral = _edit_and_viral()
    with pytest.raises(UnknownPlatform):
        build_publish_package(
            edit, viral, "proj-pp", title="t", caption="c", platform="tiktok"
        )
