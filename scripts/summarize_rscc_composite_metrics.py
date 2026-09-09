"""Summarize RSCC composite S*m and SPIDEr from existing metric outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-summary", required=True, type=Path)
    parser.add_argument("--spice-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    text = json.loads(args.text_summary.read_text(encoding="utf-8"))
    spice = json.loads(args.spice_summary.read_text(encoding="utf-8"))
    models = {}
    for name, row in text["models"].items():
        sp = float(spice["models"][name]["SPICE"])
        models[name] = {
            "count": int(row["count"]),
            "S*m": (float(row["BLEU-4"]) + float(row["METEOR"]) + float(row["ROUGE-L"]) + float(row["CIDEr"])) / 4.0,
            "SPIDEr": (float(row["CIDEr"]) + sp) / 2.0,
            "components": {"BLEU-4": row["BLEU-4"], "METEOR": row["METEOR"], "ROUGE-L": row["ROUGE-L"], "CIDEr": row["CIDEr"], "SPICE": sp},
        }
    summary = {
        "scope": "Draft/Refined, aligned 1000-scene LEVIR-MCI subset",
        "S*m_definition": "(BLEU-4 + METEOR + ROUGE-L + CIDEr-D) / 4, following RSICCformer/CCExpert reporting",
        "SPIDEr_definition": "(SPICE + CIDEr-D) / 2",
        "models": models,
        "interpretation": "Both remain reference-based composites and do not add image or bi-temporal verification.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
