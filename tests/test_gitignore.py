"""``.gitignore`` patterns must actually match.

Git has no inline comments: in ``/build/   # note`` the ``# note`` text is part
of the pattern, so ``build/`` (left behind by ``pip install .``) was never
ignored. Comments must sit on their own line.
"""

from __future__ import annotations

from pathlib import Path

GITIGNORE = Path(__file__).resolve().parent.parent / ".gitignore"


def test_gitignore_has_no_inline_comments():
    bad = [
        f"{n}: {line}"
        for n, line in enumerate(GITIGNORE.read_text(encoding="utf-8").splitlines(), 1)
        if line.strip() and not line.lstrip().startswith("#") and " #" in line
    ]
    assert not bad, "inline '#' is part of a gitignore pattern, not a comment: " + "; ".join(bad)


def test_root_build_dir_is_ignored():
    patterns = {
        line.strip()
        for line in GITIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert "/build/" in patterns
