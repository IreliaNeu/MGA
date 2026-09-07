"""Read-only audit of the restored MGA-current environment and compact inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def command(args, cwd=None, timeout=180):
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"returncode": None, "error": str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-checks", action="store_true")
    args = parser.parse_args()
    root = Path("/root/autodl-tmp/MGA-current")
    disk = Path("/root/autodl-tmp")
    artifact = disk / "mga-artifacts"
    expected = {
        "semantic-eval/second-cc-200-v1/manifest.json": (
            None,
            "36ed910f1eff3506b02077fb8122a9f4682d2cd95c1c20cab7c2f9d58acd43c5",
        ),
        "semantic-eval/second-cc-200-v1/fact_graphs.jsonl": (
            200,
            "6698c00a81f2bef7b6e248f476b406653f39e8c78e0d1f3897e9deae22f38a42",
        ),
        "semantic-eval/second-cc-200-v1/evaluation_samples.jsonl": (
            600,
            "22c7eeb25e943f6c06d594acb0bd2752809371d31d0e30c6504b6ef4c420cfe9",
        ),
        "semantic-eval/second-cc-200-v1/parser_all_samples.jsonl": (
            1200,
            "7e3fc5925a307802bd45bb0a74b217d951613f6386e022069e695506a099104a",
        ),
        "controlled-errors/second-cc-200-v1/minimal_error_manifest.jsonl": (
            1600,
            "cde0a928ca7c8c522c82b7f5a07b3f9a7bc4e4a7b4a135488af5c4b8ba0d7d87",
        ),
    }
    report = {
        "protocol": "mga-current-server-readonly-audit-v1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "python": sys.version,
        "executable": sys.executable,
        "project": str(root),
        "head": command(["git", "rev-parse", "HEAD"], root),
        "git_status": command(["git", "status", "--short", "--branch"], root),
        "package": command([sys.executable, "-c", "import mga; print(mga.__file__)"], root),
        "gpu": command(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                "--format=csv",
            ]
        ),
        "disk": dict(zip(("total", "used", "free"), shutil.disk_usage(disk), strict=True)),
        "inputs": {},
        "dataset_counts": {},
        "candidate_outputs": [],
        "checks": {},
    }
    for relative, (count, digest) in expected.items():
        path = artifact / relative
        entry = {"exists": path.is_file(), "expected_sha256": digest, "expected_rows": count}
        if path.is_file():
            raw = path.read_bytes()
            actual = hashlib.sha256(raw).hexdigest()
            rows = sum(bool(line.strip()) for line in raw.splitlines()) if count else None
            entry.update(
                bytes=len(raw),
                sha256=actual,
                rows=rows,
                matches_recovery_record=actual == digest and rows == count,
            )
        report["inputs"][relative] = entry
    dataset = disk / "datasets/SECOND-CC/extracted/SECOND-CC-AUG/test"
    for relative in ("rgb/A", "rgb/B", "sem/A", "sem/B"):
        folder = dataset / relative
        report["dataset_counts"][relative] = sum(1 for _ in folder.glob("*.png"))
    wanted = {
        "rsiccformer_mga1000.jsonl",
        "chg2cap_mga1000.jsonl",
        "model_outputs_manifest.jsonl",
        "model_outputs_claims.jsonl",
        "per_subset.jsonl",
    }
    for parent in (artifact, disk / "caption-bench-20260808"):
        if parent.exists():
            report["candidate_outputs"] += [
                {"path": str(path), "bytes": path.stat().st_size}
                for path in parent.rglob("*.jsonl")
                if path.name in wanted
            ]
    report["cache_directories"] = [str(path) for path in (disk / "mga-cache").glob("*")]
    report["third_party_directories"] = [str(path) for path in (disk / "third_party").glob("*")]
    if args.run_checks:
        for name, cmd in {
            "pytest": [sys.executable, "-m", "pytest", "-q"],
            "ruff_core": [sys.executable, "-m", "ruff", "check", "src", "tests"],
            "paper_sources": [sys.executable, "scripts/build_paper_experiments.py", "--check"],
            "cli": [sys.executable, "-m", "mga.cli", "--help"],
            "smoke": [
                sys.executable,
                "-m",
                "mga.cli",
                "validate",
                "--manifest",
                str(artifact / "smoke/manifest.jsonl"),
            ],
        }.items():
            report["checks"][name] = command(cmd, root)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
