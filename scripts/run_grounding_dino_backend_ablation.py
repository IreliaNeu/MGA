"""Run a compact Grounding DINO box-mask backend ablation on cached MGA scenes."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from mga.grounding.hf_dino_expanded import ExpandedHFGroundingDinoGrounder
from mga.io import load_manifest, write_jsonl
from mga.mask_ops import load_label_mask
from mga.models import ClaimRole, GroundingEvidence
from mga.scoring import MGAV2Scorer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--model", default="IDEA-Research/grounding-dino-tiny")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--box-threshold", type=float, default=0.30)
    parser.add_argument("--text-threshold", type=float, default=0.25)
    parser.add_argument("--query-expansion", default="remote-sensing")
    return parser


def mean(values):
    concrete = [float(value) for value in values if value is not None]
    return sum(concrete) / len(concrete) if concrete else None


def main() -> int:
    args = build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = load_manifest(args.manifest)
    by_scene = defaultdict(list)
    for record in records:
        by_scene[record.sample_id].append(record)
    grounder = ExpandedHFGroundingDinoGrounder(
        model_id=args.model,
        device=args.device,
        box_threshold=args.box_threshold,
        text_threshold=args.text_threshold,
        query_expansion=args.query_expansion,
    )
    scorer = MGAV2Scorer()
    score_rows = []
    detection_rows = []
    started = time.perf_counter()
    grounder._torch.cuda.reset_peak_memory_stats()
    for scene_index, (sample_id, scene_records) in enumerate(sorted(by_scene.items()), start=1):
        prototype = scene_records[0]
        entities = sorted(
            {
                claim.entity
                for record in scene_records
                for claim in record.claims
                if claim.role != ClaimRole.NO_CHANGE and claim.entity in {"building", "road"}
            }
            | {"building", "road"}
        )
        entity_evidence = {}
        for entity in entities:
            synthetic_claim = next(
                (
                    claim
                    for record in scene_records
                    for claim in record.claims
                    if claim.entity == entity and claim.role != ClaimRole.NO_CHANGE
                ),
                None,
            )
            if synthetic_claim is None:
                from mga.models import AtomicClaim, ChangeType

                synthetic_claim = AtomicClaim(
                    claim_id=f"{sample_id}:{entity}",
                    text=entity,
                    entity=entity,
                    role=ClaimRole.CHANGED,
                    change_type=ChangeType.MODIFY,
                )
            evidence = grounder.ground(prototype, synthetic_claim)
            entity_evidence[entity] = evidence
            detection_rows.append(
                {
                    "sample_id": sample_id,
                    "entity": entity,
                    "pre_confidence": evidence.pre_confidence,
                    "post_confidence": evidence.post_confidence,
                    "pre_boxes": evidence.metadata.get("pre_boxes", 0),
                    "post_boxes": evidence.metadata.get("post_boxes", 0),
                    "pre_mask_fraction": float(np.asarray(evidence.pre_mask).mean()),
                    "post_mask_fraction": float(np.asarray(evidence.post_mask).mean()),
                    "queries": evidence.metadata.get("queries", []),
                }
            )
        label_mask = load_label_mask(prototype.change_mask)
        for record in scene_records:
            evidence_by_claim = {}
            for claim in record.claims:
                if claim.role == ClaimRole.NO_CHANGE or claim.entity == "scene":
                    evidence_by_claim[claim.claim_id] = GroundingEvidence(
                        backend=grounder.backend_id
                    )
                else:
                    evidence_by_claim[claim.claim_id] = entity_evidence.get(
                        claim.entity,
                        GroundingEvidence(
                            backend=grounder.backend_id,
                            metadata={"missing_entity": claim.entity},
                        ),
                    )
            score = scorer.score(record, label_mask, evidence_by_claim)
            score_rows.append(
                {
                    "sample_id": sample_id,
                    "model": record.model,
                    "caption": record.caption,
                    "claims": [claim.to_dict() for claim in record.claims],
                    "score": score.to_dict(),
                }
            )
        print(f"[{scene_index}/{len(by_scene)}] {sample_id}", flush=True)

    by_model = defaultdict(list)
    statuses = Counter()
    for row in score_rows:
        by_model[row["model"]].append(row["score"])
        statuses.update(claim["status"] for claim in row["score"]["claim_scores"])
    metrics = ("faithfulness", "coverage", "temporal", "overall", "unverifiable_rate")
    summary = {
        "backend": grounder.backend_id,
        "scenes": len(by_scene),
        "captions": len(score_rows),
        "elapsed_seconds": time.perf_counter() - started,
        "peak_gpu_memory_mib": grounder._torch.cuda.max_memory_allocated() / (1024**2),
        "threshold_policy": "predeclared defaults; no test-set tuning",
        "models": {
            model: {
                "captions": len(scores),
                **{metric: mean(score.get(metric) for score in scores) for metric in metrics},
            }
            for model, scores in sorted(by_model.items())
        },
        "claim_statuses": dict(statuses),
        "detections": {
            "entity_rows": len(detection_rows),
            "zero_pre_boxes": sum(not row["pre_boxes"] for row in detection_rows),
            "zero_post_boxes": sum(not row["post_boxes"] for row in detection_rows),
            "mean_pre_mask_fraction": mean(row["pre_mask_fraction"] for row in detection_rows),
            "mean_post_mask_fraction": mean(row["post_mask_fraction"] for row in detection_rows),
        },
    }
    write_jsonl(args.output_dir / "detection_summary.jsonl", detection_rows)
    write_jsonl(args.output_dir / "mga_scores.jsonl", score_rows)
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
