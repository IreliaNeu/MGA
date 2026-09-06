"""Run compact five-model SegEarth MGA evidence modes without saving scene masks."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from mga.grounding.segearth_ov3 import SegEarthOV3Grounder
from mga.io import load_manifest, write_jsonl
from mga.mask_ops import load_label_mask
from mga.models import ClaimRole, EvidenceMode, GroundingEvidence
from mga.scoring import MGAV2Config, MGAV2Scorer


MODES = (
    EvidenceMode.FULL_TARGET,
    EvidenceMode.TEMPORAL_DELTA,
    EvidenceMode.GT_ROI_GATED,
    EvidenceMode.MASK_LABEL_ONLY,
    EvidenceMode.HYBRID_MASK_TEMPORAL,
)
METRICS = ("faithfulness", "coverage", "temporal", "overall", "unverifiable_rate")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--vendor-root", required=True, type=Path)
    parser.add_argument("--checkpoint")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--confidence-threshold", type=float, default=0.10)
    parser.add_argument("--logit-threshold", type=float, default=0.10)
    parser.add_argument("--query-expansion", default="remote-sensing")
    parser.add_argument("--max-scenes", type=int, default=0)
    return parser


def mean(values) -> float | None:
    concrete = [float(value) for value in values if value is not None]
    return sum(concrete) / len(concrete) if concrete else None


def evidence(entity: str, pre: dict, post: dict, backend: str) -> GroundingEvidence:
    if entity not in pre or entity not in post:
        return GroundingEvidence(backend=backend, metadata={"missing_entity": entity})
    return GroundingEvidence(
        pre_mask=pre[entity].mask,
        post_mask=post[entity].mask,
        pre_confidence=pre[entity].confidence,
        post_confidence=post[entity].confidence,
        backend=backend,
        metadata={"entity": entity, "compact_unified_eval": True},
    )


def summarize(rows_by_mode: dict[str, list[dict]], *, elapsed: float, peak_mib: float) -> dict:
    results = {}
    for mode, rows in rows_by_mode.items():
        by_model = defaultdict(list)
        statuses = Counter()
        for row in rows:
            by_model[row["model"]].append(row["score"])
            statuses.update(item["status"] for item in row["score"]["claim_scores"])
        results[mode] = {
            "captions": len(rows),
            "claim_statuses": dict(statuses),
            "models": {
                model: {
                    "captions": len(scores),
                    **{
                        metric: mean(score.get(metric) for score in scores)
                        for metric in METRICS
                    },
                }
                for model, scores in sorted(by_model.items())
            },
        }
    return {
        "protocol": "compact-segearth-five-model-unified-eval-v1",
        "elapsed_seconds": elapsed,
        "peak_gpu_memory_mib": peak_mib,
        "results": results,
    }


def main() -> int:
    args = build_parser().parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = load_manifest(args.manifest)
    by_scene = defaultdict(list)
    for record in records:
        by_scene[record.sample_id].append(record)
    scenes = sorted(by_scene.items())
    if args.max_scenes:
        scenes = scenes[: args.max_scenes]

    grounder = SegEarthOV3Grounder(
        vendor_root=args.vendor_root,
        checkpoint_path=args.checkpoint,
        device=args.device,
        confidence_threshold=args.confidence_threshold,
        logit_threshold=args.logit_threshold,
        query_expansion=args.query_expansion,
    )
    scorers = {
        mode.value: MGAV2Scorer(MGAV2Config(evidence_mode=mode)) for mode in MODES
    }
    rows_by_mode = {mode.value: [] for mode in MODES}
    if args.device.startswith("cuda"):
        grounder._torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    for scene_index, (sample_id, scene_records) in enumerate(scenes, start=1):
        prototype = scene_records[0]
        pre = grounder.segment_queries(prototype.pre_image, ("building", "road"))
        post = grounder.segment_queries(prototype.post_image, ("building", "road"))
        by_entity = {
            entity: evidence(entity, pre, post, grounder.backend_id)
            for entity in ("building", "road")
        }
        label_mask = load_label_mask(prototype.change_mask)
        for record in scene_records:
            evidence_by_claim = {}
            for claim in record.claims:
                if claim.role == ClaimRole.NO_CHANGE or claim.entity == "scene":
                    evidence_by_claim[claim.claim_id] = GroundingEvidence(
                        backend=grounder.backend_id
                    )
                else:
                    evidence_by_claim[claim.claim_id] = by_entity.get(
                        claim.entity,
                        GroundingEvidence(
                            backend=grounder.backend_id,
                            metadata={"missing_entity": claim.entity},
                        ),
                    )
            for mode, scorer in scorers.items():
                score = scorer.score(record, label_mask, evidence_by_claim)
                rows_by_mode[mode].append(
                    {
                        "sample_id": sample_id,
                        "model": record.model,
                        "score": score.to_dict(),
                    }
                )
        if scene_index == 1 or scene_index % 25 == 0 or scene_index == len(scenes):
            print(f"[{scene_index}/{len(scenes)}] {sample_id}", flush=True)

    elapsed = time.perf_counter() - started
    peak_mib = (
        grounder._torch.cuda.max_memory_allocated() / (1024**2)
        if args.device.startswith("cuda")
        else 0.0
    )
    for mode, rows in rows_by_mode.items():
        if mode == EvidenceMode.HYBRID_MASK_TEMPORAL.value:
            write_jsonl(args.output_dir / "hybrid_sample_scores.jsonl", rows)
    summary = {
        "manifest": str(args.manifest.resolve()),
        "backend": grounder.backend_id,
        "scenes": len(scenes),
        "captions": sum(len(rows) for rows in by_scene.values()),
        **summarize(rows_by_mode, elapsed=elapsed, peak_mib=peak_mib),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
