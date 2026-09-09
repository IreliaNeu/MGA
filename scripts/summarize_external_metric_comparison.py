"""Create a unified bootstrap comparison of MGA, ALOHa, and FMScore."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.metrics import balanced_accuracy_score, roc_auc_score


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def bacc(labels: list[int], scores: list[float]) -> tuple[float, float]:
    ts = sorted(set(scores)); candidates = [ts[0] - 1e-9, *ts, ts[-1] + 1e-9]
    return max((float(balanced_accuracy_score(labels, [int(x >= t) for x in scores])), float(t)) for t in candidates)


def metric(labels: list[int], scores: list[float]) -> dict:
    value, threshold = bacc(labels, scores)
    return {"roc_auc": float(roc_auc_score(labels, scores)),
            "balanced_accuracy_oracle_threshold": value, "oracle_threshold": threshold}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mga", required=True, type=Path); parser.add_argument("--aloha", required=True, type=Path)
    parser.add_argument("--fmscore", required=True, type=Path); parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bootstrap", type=int, default=2000); parser.add_argument("--seed", type=int, default=20260813)
    args = parser.parse_args()
    mga = {x["item_id"]: x for x in read(args.mga)}; aloha = {x["item_id"]: x for x in read(args.aloha)}
    fm = {x["item_id"]: x for x in read(args.fmscore)}; ids = sorted(set(mga) & set(aloha) & set(fm))
    rows = []
    for item_id in ids:
        row = mga[item_id]
        rows.append({"item_id": item_id, "sample_id": row["sample_id"], "error_type": row["error_type"],
                     "label": int(bool(row["is_factually_correct"])),
                     "MGA-Hybrid": float(row["scores"]["hybrid"]["diagnostic_score"]),
                     "ALOHa": float(aloha[item_id]["score"]), "FMScore-Qwen": float(fm[item_id]["fmscore"])})
    labels = [x["label"] for x in rows]; names = ("MGA-Hybrid", "ALOHa", "FMScore-Qwen")
    summary = {"rows": len(rows), "scenes": len({x["sample_id"] for x in rows}),
               "metrics": {name: metric(labels, [x[name] for x in rows]) for name in names},
               "bootstrap": {"replicates": args.bootstrap, "seed": args.seed, "unit": "scene"}}
    by_scene = defaultdict(list)
    for row in rows: by_scene[row["sample_id"]].append(row)
    scene_ids = sorted(by_scene); rng = np.random.default_rng(args.seed); values = {name: [] for name in names}
    for _ in range(args.bootstrap):
        sampled = rng.choice(scene_ids, size=len(scene_ids), replace=True); boot = [x for scene in sampled for x in by_scene[scene]]
        boot_labels = [x["label"] for x in boot]
        for name in names: values[name].append(float(roc_auc_score(boot_labels, [x[name] for x in boot])))
    for name in names:
        summary["metrics"][name]["roc_auc_scene_bootstrap_95ci"] = [float(np.quantile(values[name], .025)), float(np.quantile(values[name], .975))]
    for left, right in (("MGA-Hybrid", "ALOHa"), ("MGA-Hybrid", "FMScore-Qwen"), ("FMScore-Qwen", "ALOHa")):
        delta = np.asarray(values[left]) - np.asarray(values[right])
        summary.setdefault("paired_auc_deltas", {})[f"{left}_minus_{right}"] = {
            "point": summary["metrics"][left]["roc_auc"] - summary["metrics"][right]["roc_auc"],
            "scene_bootstrap_95ci": [float(np.quantile(delta, .025)), float(np.quantile(delta, .975))]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
