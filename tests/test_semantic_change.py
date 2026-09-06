from __future__ import annotations

import numpy as np
from PIL import Image

from mga.semantic_change import build_fact_graph, controlled_samples


def test_fact_graph_and_three_controlled_samples(tmp_path) -> None:
    pre = np.ones((12, 12), dtype=np.uint8)
    post = pre.copy()
    post[:6, :6] = 2
    pre_label = tmp_path / "pre.png"
    post_label = tmp_path / "post.png"
    Image.fromarray(pre).save(pre_label)
    Image.fromarray(post).save(post_label)

    graph = build_fact_graph(
        sample_id="second_0001",
        pre_image="A.png",
        post_image="B.png",
        pre_label=pre_label,
        post_label=post_label,
        class_names={1: "tree", 2: "building", 3: "water"},
        min_pixels=8,
    )

    assert len(graph.transitions) == 1
    fact = graph.transitions[0]
    assert fact.source_entity == "tree"
    assert fact.target_entity == "building"
    assert fact.location == "upper-left"

    items = controlled_samples(graph, fact, alternative_entity="water")

    assert [item["sample_type"] for item in items] == [
        "factual",
        "contradiction",
        "paraphrase",
    ]
    assert [item["is_factually_correct"] for item in items] == [True, False, True]
    assert "water areas appeared" in items[1]["caption"]
