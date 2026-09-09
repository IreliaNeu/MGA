"""Run the semantic evidence experiment with corrected v2 route scoring."""

from __future__ import annotations

import runpy
from pathlib import Path

from mga import evidence_routing
from mga.evidence_routing_v2 import score_evidence_modes

if __name__ == "__main__":
    evidence_routing.score_evidence_modes = score_evidence_modes
    runpy.run_path(
        str(Path(__file__).with_name("run_semantic_evidence_experiments.py")),
        run_name="__main__",
    )
