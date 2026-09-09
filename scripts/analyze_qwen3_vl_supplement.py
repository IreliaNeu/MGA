"""Analyze QA adaptation and linguistic invariance without per-item local export."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from mga.evidence_routing import binary_auc
from mga.evidence_routing_v2 import score_evidence_modes
from mga.parsing.configured import configured_entity_ontology
from mga.parsing.hybrid import HybridEntityClaimParser
from mga.parsing.ontology import core_entity_ontology
from mga.semantic_change import load_label_ids
from mga.task_adapters import (
    canonical_claim_signature,
    is_claim_preserving_rewrite,
    qa_answer_to_claims,
)

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
    parser.add_argument("--rewrites", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def ngrams(items: list[str], n: int) -> Counter:
    return Counter(tuple(items[index : index + n]) for index in range(len(items) - n + 1))


def sentence_bleu(candidate: str, reference: str, max_n: int) -> float:
    cand = tokens(candidate)
    ref = tokens(reference)
    if not cand or not ref:
        return 0.0
    precisions = []
    for n in range(1, max_n + 1):
        cand_counts = ngrams(cand, n)
        ref_counts = ngrams(ref, n)
        overlap = sum(min(value, ref_counts[key]) for key, value in cand_counts.items())
        precisions.append((overlap + 1.0) / (sum(cand_counts.values()) + 1.0))
    brevity = 1.0 if len(cand) > len(ref) else math.exp(1.0 - len(ref) / len(cand))
    return brevity * math.exp(sum(math.log(value) for value in precisions) / max_n)


def lcs_length(left: list[str], right: list[str]) -> int:
    row = [0] * (len(right) + 1)
    for left_item in left:
        previous = 0
        for index, right_item in enumerate(right, start=1):
            current = row[index]
            row[index] = previous + 1 if left_item == right_item else max(
                row[index], row[index - 1]
            )
            previous = current
    return row[-1]


def rouge_l(candidate: str, reference: str) -> float:
    cand = tokens(candidate)
    ref = tokens(reference)
    if not cand or not ref:
        return 0.0
    common = lcs_length(cand, ref)
    precision = common / len(cand)
    recall = common / len(ref)
    return 2 * precision * recall / max(precision + recall, 1e-12)


def token_f1(candidate: str, reference: str) -> float:
    cand = Counter(tokens(candidate))
    ref = Counter(tokens(reference))
    overlap = sum((cand & ref).values())
    if not cand or not ref:
        return 0.0
    precision = overlap / sum(cand.values())
    recall = overlap / sum(ref.values())
    return 2 * precision * recall / max(precision + recall, 1e-12)


def metric_vector(candidate: str, reference: str) -> dict[str, float]:
    return {
        "bleu1": sentence_bleu(candidate, reference, 1),
        "bleu4": sentence_bleu(candidate, reference, 4),
        "rouge_l": rouge_l(candidate, reference),
        "token_f1": token_f1(candidate, reference),
    }


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def analyze_qa(rows: list[dict]) -> tuple[dict, list[dict]]:
    ontology = configured_entity_ontology(class_names=SECOND_CLASSES)
    parser = HybridEntityClaimParser(ontology=ontology)
    class_ids = {value: key for key, value in SECOND_CLASSES.items()}
    details = []
    for row in rows:
        claims = qa_answer_to_claims(
            question=row["question"],
            answer=row["answer"],
            parser=parser,
        )
        claim_pairs = {
            (claim.entity, claim.change_type.value) for claim in claims
        }
        expected = row["expected_transition"]
        expected_pairs = {
            (expected["source_entity"], "remove"),
            (expected["target_entity"], "add"),
        }
        semantic_pre = load_label_ids(row["pre_label"])
        semantic_post = load_label_ids(row["post_label"])
        score_claims = [
            {
                "entity": claim.entity,
                "change_type": claim.change_type.value,
                "location": claim.location or expected["location"],
            }
            for claim in claims
        ]
        scores = score_evidence_modes(
            claims=score_claims,
            semantic_pre=semantic_pre,
            semantic_post=semantic_post,
            class_ids=class_ids,
            visible_entities=set(class_ids),
            open_vocab={},
        )
        exact = claim_pairs == expected_pairs
        details.append(
            {
                "sample_id": row["sample_id"],
                "answer": row["answer"],
                "expected_pairs": sorted(expected_pairs),
                "predicted_pairs": sorted(claim_pairs),
                "parser_success": len(claims) >= 2,
                "exact_transition": exact,
                "scores": scores,
            }
        )
    available = [
        (item["exact_transition"], item["scores"]["known_gt_unknown_ov"])
        for item in details
        if item["scores"]["known_gt_unknown_ov"] is not None
    ]
    return (
        {
            "n": len(details),
            "parser_success_rate": mean(
                [float(item["parser_success"]) for item in details]
            ),
            "exact_transition_accuracy": mean(
                [float(item["exact_transition"]) for item in details]
            ),
            "hybrid_score_coverage": len(available) / max(len(details), 1),
            "hybrid_auc_for_model_answers": (
                binary_auc(available)
                if any(label for label, _ in available)
                and any(not label for label, _ in available)
                else None
            ),
            "hybrid_mean_exact": mean(
                [score for label, score in available if label]
            ),
            "hybrid_mean_inexact": mean(
                [score for label, score in available if not label]
            ),
        },
        details,
    )


def analyze_rewrites(rows: list[dict]) -> tuple[dict, list[dict]]:
    parser = HybridEntityClaimParser(ontology=core_entity_ontology())
    details = []
    for row in rows:
        accepted, rewritten_claims = is_claim_preserving_rewrite(
            original_claims=row["original_claims"],
            rewritten_text=row["rewritten_caption"],
            parser=parser,
        )
        reference = row["reference_caption"] or row["original_caption"]
        original_metrics = metric_vector(row["original_caption"], reference)
        rewrite_metrics = metric_vector(row["rewritten_caption"], reference)
        self_similarity = metric_vector(
            row["rewritten_caption"], row["original_caption"]
        )
        original_score = row["original_score"]
        details.append(
            {
                "sample_id": row["sample_id"],
                "model": row["model"],
                "claim_preserving": accepted,
                "original_signature": canonical_claim_signature(
                    row["original_claims"]
                ),
                "rewritten_signature": canonical_claim_signature(rewritten_claims),
                "original_metrics_to_reference": original_metrics,
                "rewrite_metrics_to_reference": rewrite_metrics,
                "rewrite_to_original": self_similarity,
                "mga_reused_score": original_score if accepted else None,
                "mga_delta_if_accepted": 0.0 if accepted else None,
            }
        )
    by_model: dict[str, list[dict]] = defaultdict(list)
    for item in details:
        by_model[item["model"]].append(item)

    def summarize(items: list[dict]) -> dict:
        accepted = [item for item in items if item["claim_preserving"]]
        summary = {
            "n": len(items),
            "claim_preservation_rate": len(accepted) / max(len(items), 1),
            "mga_status_agreement_on_accepted": 1.0 if accepted else None,
            "mean_absolute_mga_delta_on_accepted": 0.0 if accepted else None,
        }
        for key in ("bleu1", "bleu4", "rouge_l", "token_f1"):
            summary[f"original_{key}_to_reference"] = mean(
                [item["original_metrics_to_reference"][key] for item in accepted]
            )
            summary[f"rewrite_{key}_to_reference"] = mean(
                [item["rewrite_metrics_to_reference"][key] for item in accepted]
            )
            summary[f"rewrite_{key}_to_original"] = mean(
                [item["rewrite_to_original"][key] for item in accepted]
            )
        return summary

    return (
        {
            "overall": summarize(details),
            "by_model": {
                key: summarize(values) for key, values in sorted(by_model.items())
            },
            "interpretation": (
                "MGA equality is asserted only after exact canonical claim-set "
                "matching; rejected rewrites are reported as semantic drift rather "
                "than counted as invariant."
            ),
        },
        details,
    )


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    qa_summary, qa_details = analyze_qa(read_jsonl(args.qa))
    rewrite_summary, rewrite_details = analyze_rewrites(read_jsonl(args.rewrites))
    summary = {
        "qa_adaptation": qa_summary,
        "language_invariance": rewrite_summary,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    with (args.output_dir / "qa_details.jsonl").open("w", encoding="utf-8") as handle:
        for row in qa_details:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=True) + "\n")
    with (args.output_dir / "rewrite_details.jsonl").open(
        "w", encoding="utf-8"
    ) as handle:
        for row in rewrite_details:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=True) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
