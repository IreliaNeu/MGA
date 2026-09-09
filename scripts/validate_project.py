"""Run the same offline CPU acceptance checks locally, on AutoDL, and in CI."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = [
    "scripts/analyze_heldout_human_validity.py",
    "scripts/audit_server_recovery.py",
    "scripts/build_paper_experiments.py",
    "scripts/evaluate_semantic_parser_v2.py",
    "scripts/validate_project.py",
]


def run_command(command: list[str], *, timeout: float) -> dict:
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"returncode": None, "error": str(error)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New JSON report; existing paths are refused")
    parser.add_argument("--server", action="store_true", help="Also verify restored AutoDL inputs")
    parser.add_argument("--timeout", type=float, default=300, help="Seconds per check")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.output and args.output.exists():
        parser.error("Output exists; choose a new versioned report")
    python = sys.executable
    checks = {
        "ruff": [python, "-m", "ruff", "check", "src", "tests", *ENTRYPOINTS],
        "pytest": [python, "-m", "pytest", "-q"],
        "paper_sources": [python, "scripts/build_paper_experiments.py", "--check"],
        "cli": [python, "-m", "mga.cli", "--help"],
        "diff_whitespace": ["git", "diff", "--check", "HEAD"],
    }
    if args.server:
        checks["server_recovery"] = [python, "scripts/audit_server_recovery.py"]
    report = {
        "protocol": "mga-offline-acceptance-v1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "executable": python,
        "root": str(ROOT),
        "head": run_command(["git", "rev-parse", "HEAD"], timeout=args.timeout),
        "git_status": run_command(["git", "status", "--short", "--branch"], timeout=args.timeout),
        "checks": {},
    }
    for name, command in checks.items():
        print(f"Running {name}...", flush=True)
        result = run_command(command, timeout=args.timeout)
        report["checks"][name] = result
        print(f"{name}: {'PASS' if result['returncode'] == 0 else 'FAIL'}", flush=True)
        if result["returncode"] != 0:
            print(result.get("stderr") or result.get("error") or result.get("stdout", ""))
    report["passed"] = all(result["returncode"] == 0 for result in report["checks"].values())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        print(f"Report: {args.output}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
