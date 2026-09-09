from __future__ import annotations

import numpy as np

from mga.evidence_routing import score_evidence_modes


def test_four_routes_separate_closed_and_hidden_classes() -> None:
    pre = np.ones((12, 12), dtype=np.uint8)
    post = pre.copy()
    post[:6, :6] = 2
    tree_pre = pre == 1
    tree_post = post == 1
    building_pre = pre == 2
    building_post = post == 2
    claims = [
        {"entity": "tree", "change_type": "remove", "location": "upper-left"},
        {"entity": "building", "change_type": "add", "location": "upper-left"},
    ]
    open_vocab = {
        "tree": {"pre_mask": tree_pre, "post_mask": tree_post},
        "building": {"pre_mask": building_pre, "post_mask": building_post},
    }

    scores = score_evidence_modes(
        claims=claims,
        semantic_pre=pre,
        semantic_post=post,
        class_ids={"tree": 1, "building": 2},
        visible_entities={"building"},
        open_vocab=open_vocab,
    )

    assert scores["gt_class_lookup"] is None
    assert scores["oracle_all_class"] == 1.0
    assert scores["known_gt_unknown_ov"] == 1.0
    assert scores["open_vocab_only"] == 1.0


def test_oracle_rejects_wrong_target_relation() -> None:
    pre = np.ones((12, 12), dtype=np.uint8)
    post = pre.copy()
    post[:6, :6] = 2
    claims = [
        {"entity": "tree", "change_type": "remove", "location": "upper-left"},
        {"entity": "water", "change_type": "add", "location": "upper-left"},
    ]

    scores = score_evidence_modes(
        claims=claims,
        semantic_pre=pre,
        semantic_post=post,
        class_ids={"tree": 1, "building": 2, "water": 3},
        visible_entities={"tree", "building", "water"},
        open_vocab={},
    )

    assert scores["oracle_all_class"] == 0.0
    assert scores["gt_class_lookup"] == 0.0
