"""ASUR daily development driver (stdlib-only).

A standing, safe-by-construction daily health + drift + horizon check. It proves
the system still works, detects documentation/code drift, surfaces the real
remaining HUMAN-GATED work, writes a dated report, and then STOPS.

Why this shape (and not an autonomous "develop every day" agent):
  * ASUR-HUMAN-01 forbids machine commits. This driver NEVER runs git, NEVER
    pushes, NEVER publishes. Its only write is its own dated report.
  * AGENTS.md section 11 lists the human gates (publish, hero-proof, enabling
    paid/cloud deps, deleting data). The driver can only SURFACE these as a
    checklist; it is structurally incapable of clearing them.
  * ASUR-GATE-01 (fail closed): any failed/missing check caps the disposition at
    DRIFT or FAIL and is reported as such; absence of evidence is never a pass.

What it runs (mirrors .github/workflows/ci.yml exactly, no invented commands):
  1. asur.tools.status            -> test-count source of truth
  2. stdlib-only import probe     -> no forbidden media/network dep leaks into core
  3. firewall grep guard          -> no quality/hardness TARGET names leak across the wall
  4. ruff check .                 -> lint
  5. mypy asur                    -> types (advisory, mirrors CI `|| true`)
  6. pytest -q                    -> unit suite (integration excluded by addopts)

Stdlib-only (ADR-0002): subprocess, datetime, pathlib, re, sys, shutil only.
No third-party imports, no network. Must run from the repo root (the directory
that contains pyproject.toml and the asur/ package), exactly like CI.

Exit code: 0 when every REQUIRED check passed and no drift was detected; 1
otherwise. mypy is advisory and never changes the exit code (it mirrors CI).

Usage:
    python3 -m asur.tools.daily_driver [--no-report] [--root PATH]
"""

from __future__ import annotations

import argparse
import datetime
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants copied verbatim from ci.yml so the driver and CI cannot diverge.
# If CI changes, these must change in lockstep (that itself is a drift signal).
# ---------------------------------------------------------------------------

# ci.yml "Assert stdlib-only core" step: importing these layers must not pull in
# any forbidden dependency.
_CORE_IMPORT_PROBE = (
    "import sys\n"
    "before = set(sys.modules)\n"
    "import asur, asur.core, asur.script, asur.orchestrator, "
    "asur.tools, asur.viral_check, asur.learning\n"
    "after = set(sys.modules)\n"
    "forbidden = {\n"
    '    "torch", "diffusers", "transformers", "kokoro", "soundfile",\n'
    '    "numpy", "PIL", "cv2", "opentimelineio", "moviepy", "librosa",\n'
    '    "faster_whisper", "stable_audio_tools",\n'
    '    "requests", "httpx", "aiohttp", "urllib3",\n'
    "}\n"
    'leaked = sorted(forbidden & {m.split(".")[0] for m in after - before})\n'
    "if leaked:\n"
    '    print("FORBIDDEN DEPENDENCIES LEAKED INTO STDLIB CORE:", leaked)\n'
    "    sys.exit(1)\n"
    'print("stdlib-only core OK: no forbidden dependency imported.")\n'
)

# ci.yml "Firewall grep guard" step: these target field names must not appear in
# any generation/editing/viral path. Mirrors the egrep alternation in CI.
_FIREWALL_FORBIDDEN = (
    "quality_targets",
    "hardness_targets",
    "target_score",
    "per_dimension_target",
    "what_good_is",
)
_FIREWALL_DIRS = ("asur/generation", "asur/editing", "asur/viral_check")

# The two remaining HUMAN-GATED items (AGENTS.md section 11 + DEFERRED.md). The
# driver can only list these; it can never act on them.
_HUMAN_GATED_BACKLOG = (
    (
        "PUBLISH approval (pipeline stage 25) — a human must clear the publish gate; "
        "no machine may publish (ASUR-HUMAN-01, section 11)."
    ),
    (
        "Local-GPU generation adapters are stubs by design: sdxl.py, kokoro.py, "
        "stable_audio.py, wan22.py, faster_whisper.py, editing/adapters/otio.py. "
        "Wiring any of them enables heavy/paid/model deps -> human gate (section 11). "
        "Run locally/manually; never from this driver."
    ),
)


@dataclass
class CheckResult:
    """One check's outcome. `required` controls whether failure fails the run."""

    name: str
    ok: bool
    required: bool
    detail: str = ""


@dataclass
class DriverReport:
    checks: list[CheckResult] = field(default_factory=list)
    drift: list[str] = field(default_factory=list)
    status_text: str = ""

    @property
    def required_failures(self) -> list[CheckResult]:
        return [c for c in self.checks if c.required and not c.ok]

    @property
    def healthy(self) -> bool:
        return not self.required_failures and not self.drift

    @property
    def disposition(self) -> str:
        # Fail closed: any required failure is FAIL; drift alone is DRIFT.
        if self.required_failures:
            return "FAIL"
        if self.drift:
            return "DRIFT"
        return "PASS"


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a subprocess, capturing output. Never raises on non-zero exit."""
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, check=False
    )


def _tail(text: str, lines: int = 12) -> str:
    kept = [ln for ln in text.splitlines() if ln.strip()][-lines:]
    return "\n".join(kept)


# ---------------------------------------------------------------------------
# Individual checks (each mirrors one CI step).
# ---------------------------------------------------------------------------


def check_status(root: Path) -> tuple[CheckResult, str]:
    """Run the test-count source of truth. Returns (result, raw status text)."""
    proc = _run([sys.executable, "-m", "asur.tools.status"], root)
    text = (proc.stdout + proc.stderr).strip()
    ok = proc.returncode == 0
    return (
        CheckResult(
            name="status (test-count source of truth)",
            ok=ok,
            required=True,
            detail=text if ok else _tail(text),
        ),
        text,
    )


def check_stdlib_core(root: Path) -> CheckResult:
    """ci.yml: assert the stdlib core imports no forbidden dependency."""
    proc = _run([sys.executable, "-c", _CORE_IMPORT_PROBE], root)
    text = (proc.stdout + proc.stderr).strip()
    return CheckResult(
        name="stdlib-only core (no forbidden dep leak)",
        ok=proc.returncode == 0,
        required=True,
        detail=_tail(text),
    )


def check_firewall(root: Path) -> CheckResult:
    """ci.yml firewall grep guard, reimplemented in pure Python (stdlib-only).

    Fails closed: any forbidden TARGET field name found in a generation/editing/
    viral path is a leak. Scans *.py text directly so it needs no `grep` binary.
    """
    pattern = re.compile("|".join(re.escape(name) for name in _FIREWALL_FORBIDDEN))
    hits: list[str] = []
    for rel in _FIREWALL_DIRS:
        base = root / rel
        if not base.exists():
            # Missing a firewall dir is itself suspicious -> fail closed.
            hits.append(f"{rel}: MISSING (expected firewall path absent)")
            continue
        for py in sorted(base.rglob("*.py")):
            try:
                content = py.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                hits.append(f"{py}: unreadable ({exc})")
                continue
            for lineno, line in enumerate(content.splitlines(), start=1):
                if pattern.search(line):
                    rel_py = py.relative_to(root)
                    hits.append(f"{rel_py}:{lineno}: {line.strip()}")
    ok = not hits
    detail = "no forbidden target-name leak" if ok else "\n".join(hits[:20])
    return CheckResult(
        name="firewall grep guard (ASUR-FIREWALL-01)",
        ok=ok,
        required=True,
        detail=detail,
    )


def check_ruff(root: Path) -> CheckResult:
    if shutil.which("ruff") is None:
        return CheckResult(
            name="ruff check",
            ok=False,
            required=True,
            detail="ruff not installed (CI installs it; `pip install ruff`)",
        )
    proc = _run(["ruff", "check", "."], root)
    return CheckResult(
        name="ruff check",
        ok=proc.returncode == 0,
        required=True,
        detail=_tail(proc.stdout + proc.stderr),
    )


def check_mypy(root: Path) -> CheckResult:
    """Advisory, mirrors CI `mypy asur || true`. Never fails the run."""
    if shutil.which("mypy") is None:
        return CheckResult(
            name="mypy asur (advisory)",
            ok=True,
            required=False,
            detail="mypy not installed; skipped (advisory, like CI `|| true`)",
        )
    proc = _run(["mypy", "asur"], root)
    return CheckResult(
        name="mypy asur (advisory)",
        ok=proc.returncode == 0,
        required=False,
        detail=_tail(proc.stdout + proc.stderr),
    )


def check_pytest(root: Path) -> CheckResult:
    """ci.yml: unit suite (integration excluded by pyproject addopts)."""
    proc = _run([sys.executable, "-m", "pytest", "-q"], root)
    return CheckResult(
        name="pytest -q (unit suite)",
        ok=proc.returncode == 0,
        required=True,
        detail=_tail(proc.stdout + proc.stderr, lines=15),
    )


# ---------------------------------------------------------------------------
# Drift detection: hand-typed numbers in docs vs the live source of truth.
# ---------------------------------------------------------------------------


def detect_drift(root: Path, status_text: str) -> list[str]:
    """Compare live test counts against any hand-typed counts in key docs.

    The status tool is the single source of truth (ASUR-HONEST-01). If a doc
    hard-codes a different total, that is drift to flag — never silently fixed
    (ASUR-VERSION-01: nothing silently overwritten; humans own history).
    """
    drift: list[str] = []
    total_match = re.search(r"total collected:\s*(\d+)", status_text)
    if not total_match:
        return ["could not read live total from status output (fail closed)"]
    live_total = int(total_match.group(1))

    # Docs that historically carried hand-typed counts.
    doc_candidates = [
        root / "README.md",
        root / "docs" / "build" / "STATUS.md",
    ]
    # Look for phrases like "227 tests", "222 + 5", "total: 227".
    count_phrase = re.compile(r"\b(\d{3})\s*(?:tests|total)\b", re.IGNORECASE)
    for doc in doc_candidates:
        if not doc.exists():
            continue
        try:
            text = doc.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in count_phrase.finditer(text):
            claimed = int(match.group(1))
            if claimed != live_total:
                rel = doc.relative_to(root)
                drift.append(
                    f"{rel}: doc says {claimed} tests but live total is "
                    f"{live_total} (status tool is source of truth)"
                )
    return drift


# ---------------------------------------------------------------------------
# Report rendering.
# ---------------------------------------------------------------------------


def render_report(report: DriverReport, when: datetime.datetime) -> str:
    lines: list[str] = []
    lines.append(f"# ASUR daily driver — {when:%Y-%m-%d %H:%M}")
    lines.append("")
    lines.append(f"**Disposition:** {report.disposition}")
    lines.append("")
    lines.append(
        "_Safe-by-construction: this driver ran health + drift + horizon checks "
        "only. It made NO git commits, NO push, NO publish (ASUR-HUMAN-01)._"
    )
    lines.append("")

    lines.append("## Health checks (mirror CI)")
    lines.append("")
    lines.append("| Check | Result | Required |")
    lines.append("|---|---|---|")
    for c in report.checks:
        mark = "PASS" if c.ok else "FAIL"
        req = "yes" if c.required else "advisory"
        lines.append(f"| {c.name} | {mark} | {req} |")
    lines.append("")

    failures = [c for c in report.checks if not c.ok]
    if failures:
        lines.append("### Failure detail")
        lines.append("")
        for c in failures:
            lines.append(f"**{c.name}**")
            lines.append("")
            lines.append("```")
            lines.append(c.detail or "(no output)")
            lines.append("```")
            lines.append("")

    lines.append("## Drift")
    lines.append("")
    if report.drift:
        for d in report.drift:
            lines.append(f"- DRIFT: {d}")
    else:
        lines.append("- none detected")
    lines.append("")

    lines.append("## Remaining work — HUMAN-GATED (driver cannot act)")
    lines.append("")
    for item in _HUMAN_GATED_BACKLOG:
        lines.append(f"- [ ] {item}")
    lines.append("")

    lines.append("## Status tool output")
    lines.append("")
    lines.append("```")
    lines.append(report.status_text or "(status tool produced no output)")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def render_console(report: DriverReport, report_path: Path | None) -> str:
    out: list[str] = []
    out.append(f"ASUR daily driver: {report.disposition}")
    for c in report.checks:
        out.append(f"  [{'OK ' if c.ok else 'XX '}] {c.name}")
    if report.drift:
        out.append("  DRIFT:")
        for d in report.drift:
            out.append(f"    - {d}")
    out.append("  Remaining work is HUMAN-GATED (see report). No git/publish performed.")
    if report_path is not None:
        out.append(f"  Report: {report_path}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Entry point.
# ---------------------------------------------------------------------------


def run(root: Path, write_report: bool = True) -> DriverReport:
    status_result, status_text = check_status(root)
    report = DriverReport(status_text=status_text)
    report.checks.append(status_result)
    report.checks.append(check_stdlib_core(root))
    report.checks.append(check_firewall(root))
    report.checks.append(check_ruff(root))
    report.checks.append(check_mypy(root))
    report.checks.append(check_pytest(root))
    report.drift = detect_drift(root, status_text)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ASUR daily development driver")
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="print to console only; do not write a report file",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="repo root containing pyproject.toml and the asur/ package (default: .)",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not (root / "pyproject.toml").exists() or not (root / "asur").is_dir():
        print(
            f"error: --root {root} is not the ASUR repo root "
            "(expected pyproject.toml + asur/ package). Run from the repo root.",
            file=sys.stderr,
        )
        return 2

    when = datetime.datetime.now(tz=datetime.timezone.utc)
    report = run(root, write_report=not args.no_report)

    report_path: Path | None = None
    if not args.no_report:
        out_dir = root / "docs" / "build" / "daily"
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / f"{when:%Y-%m-%d}.md"
        report_path.write_text(render_report(report, when), encoding="utf-8")

    print(render_console(report, report_path))

    # Fail closed: required failure OR drift => non-zero. mypy is advisory only.
    return 0 if report.healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())
