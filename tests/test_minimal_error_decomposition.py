from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest


def load_script():
    path = Path(__file__).parents[1] / "scripts" / "run_minimal_error_decomposition.py"
    spec = importlib.util.spec_from_file_location("minimal_error_decomposition", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


scoring = load_script()


CLASS_IDS = {"tree": 1, "building": 2, "water": 3}


def scene_arrays() -> tuple[np.ndarray, np.ndarray]:
    pre = np.ones((12, 12), dtype=np.uint8)
    post = pre.copy()
    post[1:5, 1:5] = 2
    return pre, post


def open_vocab(pre: np.ndarray, post: np.ndarray) -> dict:
    empty = np.zeros_like(pre, dtype=bool)
    return {
        "tree": scoring.RoutedMasks(pre == 1, post == 1, "open_vocab", 0.9, 0.8),
        "building": scoring.RoutedMasks(pre == 2, post == 2, "open_vocab", 0.7, 0.85),
        "water": scoring.RoutedMasks(empty, empty, "open_vocab", 0.6, 0.6),
    }


def state(**changes) -> dict:
    value = {
        "source_entity": "tree",
        "target_entity": "building",
        "source_change": "remove",
        "target_change": "add",
        "location": "upper-left",
        "relation_direction": "source-to-target",
        "extra_claim": None,
        "included_target": True,
        "scene_change_state": "changed",
    }
    value.update(changes)
    return value


def claim(entity: str, change_type: str, location: str = "upper-left") -> dict:
    return {"entity": entity, "change_type": change_type, "location": location}


def row(error_type: str, claims: list[dict], **state_changes) -> dict:
    return {
        "sample_id": "second_1",
        "item_id": f"second_1:minimal:{error_type}",
        "error_type": error_type,
        "is_factually_correct": error_type == "none",
        "caption": error_type,
        "transition": {
            "source_entity": "tree",
            "target_entity": "building",
            "location": "upper-left",
        },
        "base_semantics": state(),
        "perturbed_semantics": state(**state_changes),
        "claims": claims,
    }


def oracle_score(item: dict) -> dict:
    pre, post = scene_arrays()
    return scoring.score_row(
        item,
        mode="oracle",
        semantic_pre=pre,
        semantic_post=post,
        class_ids=CLASS_IDS,
        hybrid_visible_entities=set(CLASS_IDS),
        open_vocab=open_vocab(pre, post),
        min_event_pixels=1,
        ov_tolerance_radius=0,
        relation_radius=1,
    )


def test_one_claim_omission_is_scored_and_atomic_coverage_catches_it() -> None:
    omitted = row(
        "omission",
        [claim("tree", "remove")],
        included_target=False,
    )
    result = oracle_score(omitted)

    assert result["claim_count"] == 1
    assert result["evidence_score"] == 1.0
    assert result["components"]["atomic_fact_coverage"] == 1 / 3
    assert result["diagnostic_score"] == 1 / 3
    assert result["atomic_facts"]["missing"] == [
        "claim:building:add",
        "relation:tree:building",
    ]


def test_every_claim_is_scored_so_third_claim_hallucination_lowers_conjunction() -> None:
    hallucinated = row(
        "hallucination",
        [
            claim("tree", "remove"),
            claim("building", "add"),
            claim("water", "add"),
        ],
        extra_claim={"entity": "water", "change_type": "add", "location": "upper-left"},
    )
    result = oracle_score(hallucinated)

    assert result["claim_count"] == 3
    assert [item["claim_support"] for item in result["claims"]] == [1.0, 1.0, 0.0]
    assert result["components"]["claim_support_mean"] == 2 / 3
    assert result["components"]["claim_support"] == 0.0
    assert result["diagnostic_score"] == 0.0


def test_direction_does_not_fall_back_to_an_unrelated_remove_add_pair() -> None:
    wrong_direction = row(
        "direction",
        [claim("tree", "remove"), claim("building", "remove")],
        target_change="remove",
    )
    result = oracle_score(wrong_direction)

    assert result["relation"]["reason"] == "directional_endpoint_claims_missing"
    assert result["relation"]["relation_support"] == 0.0
    assert result["diagnostic_score"] == 0.0


def test_relation_location_and_no_change_have_distinct_target_failures() -> None:
    wrong_relation = row(
        "relation",
        [claim("building", "remove"), claim("tree", "add")],
        relation_direction="target-to-source",
    )
    relation_result = oracle_score(wrong_relation)
    assert relation_result["components"]["relation_support"] == 0.0

    wrong_location = row(
        "location",
        [claim("tree", "remove", "upper-right"), claim("building", "add", "upper-right")],
        location="upper-right",
    )
    location_result = oracle_score(wrong_location)
    assert location_result["components"]["location_support"] == 0.0

    no_change = row(
        "no-change",
        [claim("scene", "none")],
        scene_change_state="no-change",
    )
    no_change_result = oracle_score(no_change)
    assert no_change_result["claim_count"] == 1
    assert no_change_result["claims"][0]["temporal_support"] == 0.0
    assert no_change_result["diagnostic_score"] == 0.0


def test_atomic_truth_comes_from_base_semantics_not_visual_score() -> None:
    item = row("entity", [claim("tree", "remove"), claim("water", "add")])
    coverage = scoring.atomic_fact_coverage(item)

    assert coverage["expected"] == [
        "claim:building:add",
        "claim:tree:remove",
        "relation:tree:building",
    ]
    assert coverage["coverage"] == 1 / 3


def test_cache_loader_and_independent_confidence(tmp_path: Path) -> None:
    pre, post = scene_arrays()
    path = tmp_path / "second_1.npz"
    np.savez_compressed(
        path,
        entities_json=np.asarray(json.dumps(["tree", "building"])),
        pre_masks=np.stack([pre == 1, pre == 2]),
        post_masks=np.stack([post == 1, post == 2]),
        pre_confidences=np.asarray([0.9, 0.7]),
        post_confidences=np.asarray([0.8, 0.85]),
    )
    loaded = scoring.load_open_vocab_cache(path)
    assert set(loaded) == {"tree", "building"}
    assert loaded["building"].post_confidence == 0.85

    original = row(
        "none",
        [claim("tree", "remove"), claim("building", "add")],
    )
    result = scoring.score_row(
        original,
        mode="open_vocab",
        semantic_pre=pre,
        semantic_post=post,
        class_ids=CLASS_IDS,
        hybrid_visible_entities=set(),
        open_vocab=loaded,
        min_event_pixels=1,
        ov_tolerance_radius=0,
        relation_radius=1,
    )
    assert scoring.independent_visual_confidence(result) == 0.85


def test_paired_summary_reports_requested_metrics_and_target_delta() -> None:
    original = row(
        "none",
        [claim("tree", "remove"), claim("building", "add")],
    )
    omitted = row(
        "omission",
        [claim("tree", "remove")],
        included_target=False,
    )
    output_rows = []
    for item in (original, omitted):
        detail = oracle_score(item)
        output_rows.append(
            {
                "sample_id": item["sample_id"],
                "error_type": item["error_type"],
                "score_details": {"MGA-GT": detail},
            }
        )
    summary = scoring.summarize_pairs(
        output_rows,
        mode="oracle",
        error_type="omission",
        threshold=0.5,
    )

    assert summary["paired_accuracy"] == 1.0
    assert summary["neutral_auc"] == 1.0
    assert summary["balanced_accuracy"] == 1.0
    assert summary["false_support_rate"] == 0.0
    assert summary["unverifiable_rate"] == 0.0
    assert summary["target_component"] == "atomic_fact_coverage"
    assert summary["target_component_delta"] == pytest.approx(2 / 3)
