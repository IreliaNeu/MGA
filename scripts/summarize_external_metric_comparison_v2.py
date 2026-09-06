"""Compare MGA, ALOHa, and FMScore with neutral handling of unverifiable MGA."""

from __future__ import annotations

import argparse, json
from collections import defaultdict
from pathlib import Path
import numpy as np
from sklearn.metrics import balanced_accuracy_score, roc_auc_score


def read(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def metrics(labels, scores):
    ts = sorted(set(scores)); candidates = [ts[0] - 1e-9, *ts, ts[-1] + 1e-9]
    bacc, threshold = max((float(balanced_accuracy_score(labels, [int(x >= t) for x in scores])), float(t)) for t in candidates)
    return {"roc_auc": float(roc_auc_score(labels, scores)), "balanced_accuracy_oracle_threshold": bacc, "oracle_threshold": threshold}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--mga", type=Path, required=True)
    p.add_argument("--aloha", type=Path, required=True); p.add_argument("--fmscore", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True); p.add_argument("--bootstrap", type=int, default=2000)
    p.add_argument("--seed", type=int, default=20260813); a = p.parse_args()
    mga = {x["item_id"]: x for x in read(a.mga)}; aloha = {x["item_id"]: x for x in read(a.aloha)}
    fm = {x["item_id"]: x for x in read(a.fmscore)}; ids = sorted(set(mga) & set(aloha) & set(fm)); rows=[]; unverifiable=0
    for key in ids:
        r=mga[key]; raw=r["scores"]["hybrid"]["diagnostic_score"]; unverifiable += raw is None
        rows.append({"sample_id":r["sample_id"], "label":int(bool(r["is_factually_correct"])),
                     "MGA-Hybrid":0.5 if raw is None else float(raw), "ALOHa":float(aloha[key]["score"]),
                     "FMScore-Qwen":float(fm[key]["fmscore"])})
    names=("MGA-Hybrid","ALOHa","FMScore-Qwen"); labels=[x["label"] for x in rows]
    out={"rows":len(rows),"scenes":len({x["sample_id"] for x in rows}),"mga_neutral_mapping":0.5,
         "mga_unverifiable_rows":unverifiable,"metrics":{n:metrics(labels,[x[n] for x in rows]) for n in names},
         "bootstrap":{"replicates":a.bootstrap,"seed":a.seed,"unit":"scene"}}
    by_scene=defaultdict(list)
    for r in rows: by_scene[r["sample_id"]].append(r)
    scene_ids=sorted(by_scene); rng=np.random.default_rng(a.seed); vals={n:[] for n in names}
    for _ in range(a.bootstrap):
        sample=rng.choice(scene_ids,size=len(scene_ids),replace=True); boot=[x for s in sample for x in by_scene[s]]; y=[x["label"] for x in boot]
        for n in names: vals[n].append(float(roc_auc_score(y,[x[n] for x in boot])))
    for n in names: out["metrics"][n]["roc_auc_scene_bootstrap_95ci"]=[float(np.quantile(vals[n],.025)),float(np.quantile(vals[n],.975))]
    for left,right in (("MGA-Hybrid","ALOHa"),("MGA-Hybrid","FMScore-Qwen"),("FMScore-Qwen","ALOHa")):
        delta=np.asarray(vals[left])-np.asarray(vals[right]); out.setdefault("paired_auc_deltas",{})[f"{left}_minus_{right}"]={
            "point":out["metrics"][left]["roc_auc"]-out["metrics"][right]["roc_auc"],
            "scene_bootstrap_95ci":[float(np.quantile(delta,.025)),float(np.quantile(delta,.975))]}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)); return 0


if __name__=="__main__": raise SystemExit(main())
