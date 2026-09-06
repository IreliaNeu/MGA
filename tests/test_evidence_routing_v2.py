from __future__ import annotations

import numpy as np

from mga.evidence_routing_v2 import score_evidence_modes


def test_valid_open_vocab_query_without_relation_scores_zero() -> None:
    pre = np.ones((12, 12), dtype=np.uint8)
    post = pre.copy()
    post[:6, :6] = 2
    empty = np.zeros_like(pre, dtype=bool)
    claims = [
        {"entity": "tree", "change_type": "remove", "location": "upper-left"},
        {"entity": "building", "change_type": "add", "location": "upper-left"},
    ]
    scores = score_evidence_modes(
        claims=claims,
        semantic_pre=pre,
        semantic_post=post,
        class_ids={"tree": 1, "building": 2},
        visible_entities=set(),
        open_vocab={
            "tree": {"pre_mask": empty, "post_mask": empty},
            "building": {"pre_mask": empty, "post_mask": empty},
        },
    )
    assert scores["open_vocab_only"] == 0.0
    assert scores["known_gt_unknown_ov"] == 0.0


def test_hybrid_routes_known_source_and_open_vocab_target_independently() -> None:
    pre = np.ones((12, 12), dtype=np.uint8)
    post = pre.copy()
    post[:6, :6] = 2
    target_pre = np.zeros_like(pre, dtype=bool)
    target_post = post == 2
    claims = [
        {"entity": "tree", "change_type": "remove", "location": "upper-left"},
        {"entity": "building", "change_type": "add", "location": "upper-left"},
    ]
    scores = score_evidence_modes(
        claims=claims,
        semantic_pre=pre,
        semantic_post=post,
        class_ids={"tree": 1, "building": 2},
        visible_entities={"tree"},
        open_vocab={
            "tree": {
                "pre_mask": np.zeros_like(pre, dtype=bool),
                "post_mask": np.zeros_like(pre, dtype=bool),
            },
            "building": {"pre_mask": target_pre, "post_mask": target_post},
        },
    )
    assert scores["open_vocab_only"] == 0.0
    assert scores["known_gt_unknown_ov"] == 1.0
