from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_configured_parser_can_run_without_model_dependencies(tmp_path):
    root = Path(__file__).parents[1]
    samples = tmp_path / "samples.jsonl"
    samples.write_text(
        json.dumps(
            {
                "item_id": "synthetic-parser-smoke",
                "sample_type": "factual",
                "caption": "Trees were replaced by buildings in the upper-left.",
                "claims": [
                    {"entity": "tree", "change_type": "remove"},
                    {"entity": "building", "change_type": "add"},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "summary.json"
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/evaluate_semantic_parser_v2.py"),
            "--samples",
            str(samples),
            "--output",
            str(output),
            "--skip-model",
            "--device",
            "cpu",
            "--surface-map-file",
            str(root / "configs/parser_surface_forms/second_cc_v3.json"),
            "--class-map",
            str(root / "configs/semantic_class_maps/second_cc_v2.json"),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["model_name"] is None
    assert set(result["parsers"]) == {"configured_ontology"}
    assert result["parsers"]["configured_ontology"]["exact_match"] == 1
    assert len(result["input_sha256"]) == 64
