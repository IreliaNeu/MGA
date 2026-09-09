"""Run corrected evidence routes with conservative semantic-class prompts."""

from __future__ import annotations

import runpy
from pathlib import Path

from mga import evidence_routing
from mga.evidence_routing_v2 import score_evidence_modes
from mga.grounding import segearth_ov3
from mga.grounding.semantic_query_expansion import expand_semantic_change_queries

if __name__ == "__main__":
    evidence_routing.score_evidence_modes = score_evidence_modes
    segearth_ov3.expand_grounding_queries = expand_semantic_change_queries
    runpy.run_path(
        str(Path(__file__).with_name("run_semantic_evidence_experiments.py")),
        run_name="__main__",
    )
