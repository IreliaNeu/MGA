"""Evaluate the QA adapter on controlled factual/paraphrase/contradiction answers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mga.evidence_routing import summarize_scores
from mga.evidence_routing_v2 import score_evidence_modes
from mga.parsing.configured import configured_entity_ontology
from mga.parsing.hybrid import HybridEntityClaimParser
from mga.semantic_change import load_label_ids
from mga.task_adapters import qa_answer_to_claims

SECOND_CLASSES = {
    1: "low vegetation",
    2: "tree",
    3: "non-vegetated ground",
    4: "water",
    5: "playground",
    6: "building",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    args = parse_args()
    ontology = configured_entity_ontology(class_names=SECOND_CLASSES)
    parser = HybridEntityClaimParser(ontology=ontology)
    class_ids = {value: key for key, value in SECOND_CLASSES.items()}
    rows = []
    for item in read_jsonl(args.qa):
        transition = item["expected_transition"]
        source = transition["source_entity"]
        target = transition["target_entity"]
        location = transition["location"]
        alternative = next(
            entity
            for entity in class_ids
            if entity not in {source, target}
        )
        variants = (
            (
                "factual",
                f"In the {location}, {source} disappeared while {target} appeared.",
                True,
            ),
            (
                "paraphrase",
                f"The {source} cover in the {location} was converted to {target}.",
                True,
            ),
            (
                "contradiction",
                f"The {source} cover in the {location} was converted to {alternative}.",
                False,
            ),
        )
        semantic_pre = load_label_ids(item["pre_label"])
        semantic_post = load_label_ids(item["post_label"])
        for sample_type, answer, label in variants:
            claims = qa_answer_to_claims(
                question=item["question"],
                answer=answer,
                parser=parser,
            )
            routed_claims = [
                {
                    "entity": claim.entity,
                    "change_type": claim.change_type.value,
                    "location": claim.location or location,
                }
                for claim in claims
            ]
            scores = score_evidence_modes(
                claims=routed_claims,
                semantic_pre=semantic_pre,
                semantic_post=semantic_post,
                class_ids=class_ids,
                visible_entities=set(class_ids),
                open_vocab={},
            )
            rows.append(
                {
                    "sample_id": item["sample_id"],
                    "sample_type": sample_type,
                    "answer": answer,
                    "is_factually_correct": label,
                    "claim_count": len(claims),
                    "scores": scores,
                }
            )
    summary = {
        "scene_count": len(read_jsonl(args.qa)),
        "answer_count": len(rows),
        "sample_types": {
            name: sum(row["sample_type"] == name for row in rows)
            for name in ("factual", "paraphrase", "contradiction")
        },
        "metrics": summarize_scores(rows),
        "note": (
            "All variants enter the unchanged MGA scorer through the Q+A adapter. "
            "OpenVocabOnly is unavailable here because this adapter test isolates "
            "task format under complete semantic evidence."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
