"""Select representative Tiny/Base Grounding DINO visualization scenes."""

from __future__ import annotations

import argparse, json
from collections import defaultdict
from pathlib import Path


def read(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--tiny",type=Path,required=True)
    p.add_argument("--base",type=Path,required=True); p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True); a=p.parse_args()
    tiny={(x["sample_id"],x["entity"]):x for x in read(a.tiny)}; base={(x["sample_id"],x["entity"]):x for x in read(a.base)}
    prototypes={}
    for x in read(a.manifest): prototypes.setdefault(x["sample_id"],x)
    candidates=defaultdict(list); abstention=[]
    for key,t in tiny.items():
        b=base[key]; tm=(t["pre_mask_fraction"]+t["post_mask_fraction"])/2; bm=(b["pre_mask_fraction"]+b["post_mask_fraction"])/2
        row={"sample_id":key[0],"entity":key[1],"tiny_mean_fraction":tm,"base_mean_fraction":bm,"reduction":tm-bm}
        if tm>.7 and .005<bm<.5: candidates[key[1]].append(row)
        if tm>.9 and bm==0: abstention.append(row)
    selected=[]; used=set()
    for entity in ("building","road"):
        for row in sorted(candidates[entity],key=lambda x:x["reduction"],reverse=True):
            if row["sample_id"] not in used: selected.append({"case":"base_selective",**row}); used.add(row["sample_id"]); break
    for row in sorted(abstention,key=lambda x:x["reduction"],reverse=True):
        if row["sample_id"] not in used: selected.append({"case":"base_abstains",**row}); break
    for row in selected:
        proto=prototypes[row["sample_id"]]; row["pre_image"]=proto["pre_image"]; row["post_image"]=proto["post_image"]
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(selected,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(selected,ensure_ascii=False,indent=2)); return 0


if __name__=="__main__": raise SystemExit(main())
