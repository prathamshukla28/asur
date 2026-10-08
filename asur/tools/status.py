"""ASUR test-count single source of truth (stdlib-only).

Hand-typed test counts drift (README said 36, STATUS said 214, reality was
different). This module derives the real number from pytest itself so docs can
never silently go stale (ASUR-HONEST-01, ASUR-EXPLAIN-01).

`pytest --collect-only` does not execute any test — it only lists them — so this
is safe and fast even where running the full suite is slow. Stdlib-only
(ADR-0002): subprocess + re + sys only; no network, no third-party.
"""

from __future__ import annotations

import re
import subprocess
import sys

# pytest prints a trailing summary like "216/221 tests collected (5 deselected)"
# (when a marker deselects some) or "221 tests collected". Match both shapes.
_COLLECTED = re.compile(r"(\d+)\s*/\s*(\d+)\s+tests collected|(\d+)\s+tests collected")


def _collect(args: list[str]) -> str:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout + proc.stderr


def _parse(output: str) -> tuple[int, int]:
    """Return (selected, total). total == selected when nothing is deselected."""
    for line in reversed(output.splitlines()):
        match = _COLLECTED.search(line)
        if match:
            if match.group(1) is not None:
                return int(match.group(1)), int(match.group(2))
            return int(match.group(3)), int(match.group(3))
    raise RuntimeError("could not parse a 'tests collected' line from pytest output")


def test_counts() -> dict[str, int]:
    """Count the default (unit) suite and the full suite including integration.

    The default run excludes the `integration` marker via pyproject `addopts`,
    so the honest default number is the unit count; `-m integration` re-adds the
    opt-in real-render tests.
    """
    unit_selected, _total = _parse(_collect([]))
    _all_selected, all_total = _parse(_collect(["-m", "integration or not integration"]))
    return {
        "unit": unit_selected,
        "integration": all_total - unit_selected,
        "total": all_total,
    }


def main() -> int:
    counts = test_counts()
    print("ASUR test counts (source of truth):")
    print(f"  unit (default run):  {counts['unit']}")
    print(f"  integration (opt-in): {counts['integration']}")
    print(f"  total collected:     {counts['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
