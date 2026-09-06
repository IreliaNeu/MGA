"""Compare Grounding DINO Tiny and Base on the same scenes and captions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tiny-dir", required=True, type=Path); p.add_argument("--base-dir", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path); p.add_argument("--top-scenes", type=int, default=3)
    a = p.parse_args(); tiny_s=json.loads((a.tiny_dir/"summary.json").read_text()); base_s=json.loads((a.base_dir/"summary.json").read_text())
    tiny_d={(x["sample_id"],x["entity"]):x for x in read_jsonl(a.tiny_dir/"detection_summary.jsonl")}
    base_d={(x["sample_id"],x["entity"]):x for x in read_jsonl(a.base_dir/"detection_summary.jsonl")}
    models={}
    for name in sorted(tiny_s["models"]):
        t,b=tiny_s["models"][name],base_s["models"][name]
        models[name]={key:{"tiny":t[key],"base":b[key],"base_minus_tiny":b[key]-t[key]}
                      for key in ("faithfulness","coverage","temporal","overall","unverifiable_rate")}
    scenes={}
    for key,t in tiny_d.items():
        b=base_d[key]; row=scenes.setdefault(key[0],{"sample_id":key[0],"entities":{}})
        row["entities"][key[1]]={"tiny_pre_fraction":t["pre_mask_fraction"],"tiny_post_fraction":t["post_mask_fraction"],
                                  "base_pre_fraction":b["pre_mask_fraction"],"base_post_fraction":b["post_mask_fraction"]}
    for row in scenes.values():
        row["oversize_reduction"] = float(sum(
            (v["tiny_pre_fraction"]+v["tiny_post_fraction"])-(v["base_pre_fraction"]+v["base_post_fraction"])
            for v in row["entities"].values()))
    top=sorted(scenes.values(),key=lambda x:x["oversize_reduction"],reverse=True)[:a.top_scenes]
    out={"protocol":"same 500 scenes, same claims, box=0.30, text=0.25, remote-sensing query expansion",
         "scenes":tiny_s["scenes"],"captions":tiny_s["captions"],"models":models,
         "macro_model_mean":{},"detection_delta":{"mean_pre_mask_fraction":base_s["detections"]["mean_pre_mask_fraction"]-tiny_s["detections"]["mean_pre_mask_fraction"],
         "mean_post_mask_fraction":base_s["detections"]["mean_post_mask_fraction"]-tiny_s["detections"]["mean_post_mask_fraction"],
         "zero_pre_boxes":base_s["detections"]["zero_pre_boxes"]-tiny_s["detections"]["zero_pre_boxes"],
         "zero_post_boxes":base_s["detections"]["zero_post_boxes"]-tiny_s["detections"]["zero_post_boxes"]},
         "representative_scenes_by_oversize_reduction":top}
    for key in ("faithfulness","coverage","temporal","overall","unverifiable_rate"):
        vals=[models[m][key]["base_minus_tiny"] for m in models]; out["macro_model_mean"][key]={"base_minus_tiny":float(np.mean(vals))}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)); return 0


if __name__=="__main__": raise SystemExit(main())
