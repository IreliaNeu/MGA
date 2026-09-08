from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_acceptance_timeout_is_a_failure():
    result = module("validate_project").run_command(
        [sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.05
    )
    assert result["returncode"] is None
    assert "error" in result


def test_existing_report_is_preserved(tmp_path):
    path = tmp_path / "report.json"
    path.write_text("original", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_project.py"), "--output", str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert path.read_text(encoding="utf-8") == "original"


def test_recovery_gate_detects_missing_inputs_and_wrong_package():
    root = Path("/project")
    report = {
        "head": {"returncode": 0},
        "git_status": {"returncode": 0},
        "package": {"returncode": 0, "stdout": str(root / "src" / "mga") + "/__init__.py"},
        "inputs": {"manifest": {"matches_recovery_record": True}},
        "dataset_counts": {"rgb/A": 1227},
        "checks": {},
    }
    audit = module("audit_server_recovery")
    assert audit.audit_failures(report, root) == []
    report["inputs"]["manifest"] = {"exists": False}
    report["package"]["stdout"] = "/old/project/src/mga/__init__.py"
    report["dataset_counts"]["rgb/A"] = 1226
    report["checks"]["smoke"] = {"returncode": 1}
    assert set(audit.audit_failures(report, root)) == {
        "input:manifest",
        "package_outside_current_project",
        "dataset_count:rgb/A",
        "check:smoke",
    }


def test_human_validity_cli_serializes_and_preserves_output(tmp_path):
    rows = [
        {
            "scene_id": scene,
            "item_id": scene + str(label),
            "dimension": "direction",
            "split": "test",
            "caption_sha256": "a" * 64,
            "human_status": "rated",
            "human_score": label,
            "human_binary": label,
            "scores": {"metric": label},
        }
        for scene in ("synthetic-a", "synthetic-b")
        for label in (0, 1)
    ]
    inputs, specs, output = [tmp_path / name for name in ("input.jsonl", "spec.json", "out.json")]
    inputs.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    specs.write_text(json.dumps({"metric": {"direction": 1, "threshold": 0.5}}), encoding="utf-8")
    command = [
        sys.executable,
        str(ROOT / "scripts/analyze_heldout_human_validity.py"),
        "--input",
        str(inputs),
        "--metric-specs",
        str(specs),
        "--output",
        str(output),
        "--replicates",
        "4",
    ]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    original = output.read_bytes()
    report = json.loads(original)
    assert (
        report["dimensions"]["direction"]["common_support"]["point_estimates"]["metric"]["roc_auc"]
        == 1
    )
    assert report["rater_agreement"] is None
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode != 0
    assert output.read_bytes() == original
