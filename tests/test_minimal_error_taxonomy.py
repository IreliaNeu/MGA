from __future__ import annotations

import importlib.util
from pathlib import Path


def load_script(name: str):
    path = Path(__file__).parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


taxonomy = load_script("build_minimal_error_taxonomy")


def factual_item() -> dict:
    return {
        "sample_id": "second_0001",
        "item_id": "second_0001:factual",
        "sample_type": "factual",
        "is_factually_correct": True,
        "caption": "Tree was converted to building.",
        "pre_image": "A.png",
        "post_image": "B.png",
        "pre_label": "L1.png",
        "post_label": "L2.png",
        "transition": {
            "source_entity": "tree",
            "target_entity": "building",
            "location": "upper-left",
        },
        "claims": [
            {"entity": "tree", "change_type": "remove", "location": "upper-left"},
            {"entity": "building", "change_type": "add", "location": "upper-left"},
        ],
    }


def contradiction_item() -> dict:
    item = factual_item()
    item.update(
        {
            "item_id": "second_0001:contradiction",
            "sample_type": "contradiction",
            "is_factually_correct": False,
            "caption": "Tree was converted to playground.",
            "claims": [
                {
                    "entity": "tree",
                    "change_type": "remove",
                    "location": "upper-left",
                },
                {
                    "entity": "playground",
                    "change_type": "add",
                    "location": "upper-left",
                },
            ],
        }
    )
    return item


def test_taxonomy_has_seven_single_slot_errors_and_original() -> None:
    rows, rejected = taxonomy.build_taxonomy_rows(
        [factual_item()],
        source_types={"factual"},
        entity_pool=("tree", "building", "water"),
    )

    assert not rejected
    assert len(rows) == 8
    assert rows[0]["error_type"] == "none"
    assert rows[0]["is_factually_correct"]
    errors = {row["error_type"]: row for row in rows[1:]}
    assert set(errors) == set(taxonomy.ERROR_SLOT)
    for error_type, expected_slot in taxonomy.ERROR_SLOT.items():
        row = errors[error_type]
        assert not row["is_factually_correct"]
        assert row["changed_slots"] == [expected_slot]
        assert row["audit"]["single_factor"] is True
        assert taxonomy.changed_slots(row["base_semantics"], row["perturbed_semantics"]) == [
            expected_slot
        ]


def test_derived_claims_follow_relation_hallucination_and_omission() -> None:
    rows, _ = taxonomy.build_taxonomy_rows(
        [factual_item()],
        source_types={"factual"},
        entity_pool=("tree", "building", "water"),
    )
    errors = {row["error_type"]: row for row in rows}

    relation_claims = errors["relation"]["claims"]
    assert [(claim["entity"], claim["change_type"]) for claim in relation_claims] == [
        ("building", "remove"),
        ("tree", "add"),
    ]
    assert errors["hallucination"]["claims"][-1]["entity"] == "water"
    assert len(errors["omission"]["claims"]) == 1
    assert errors["no-change"]["claims"][0]["change_type"] == "none"


def test_same_sample_contradiction_entity_has_priority_for_cached_grounding() -> None:
    rows, _ = taxonomy.build_taxonomy_rows(
        [factual_item(), contradiction_item()],
        source_types={"factual"},
        entity_pool=("tree", "building", "water"),
    )
    errors = {row["error_type"]: row for row in rows}

    assert errors["entity"]["perturbed_semantics"]["target_entity"] == "playground"
    assert errors["hallucination"]["perturbed_semantics"]["extra_claim"]["entity"] == ("playground")
    assert errors["entity"]["mutation_entity_pool"][0] == "playground"
