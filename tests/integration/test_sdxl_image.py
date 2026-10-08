"""ASUR-INTEG-SDXL: opt-in real SDXL image render.

Double-gated so it never runs in CI or on a stdlib-only machine:
  * marked ``integration`` -> default pytest (``-m 'not integration'``) skips it;
  * ``importorskip`` on torch + diffusers -> even ``-m integration`` skips when
    the generation extra / ~7 GB SDXL weights are not installed (G10: no GPU,
    no network, no model download in CI).
Run locally, after ``pip install -e '.[generation]'``, with ``-m integration``.
"""

import pytest

pytestmark = pytest.mark.integration


def test_sdxl_generates_a_vertical_png_with_provenance(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("diffusers")
    pytest.importorskip("PIL")

    from asur.generation.adapters import sdxl

    out = tmp_path / "scene.png"
    result = sdxl.generate(
        "a calm minimalist studio desk, soft window light, vertical",
        str(out),
        seed=7,
    )

    assert out.exists() and out.stat().st_size > 0
    from PIL import Image

    with Image.open(out) as img:
        assert img.size == (sdxl.TARGET_WIDTH, sdxl.TARGET_HEIGHT)

    assert result["media_type"] == "image"
    assert result["origin"] == "ai_generated"
    assert result["file_path"] == str(out)
    prov = result["provenance"]
    assert prov["model"] == "SDXL"
    assert prov["model_version"] == sdxl.MODEL_ID
    assert prov["seed"] == 7
    assert prov["render_cost_usd"] == 0
    assert prov["resolution"] == "1080x1920"
    assert result["license"]["name"] == "OpenRAIL++-M"
    assert result["license"]["commercial_ok"] is True
