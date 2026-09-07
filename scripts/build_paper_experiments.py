"""Render bilingual experiment chapters and a source ledger from archived JSON.

No model execution, score modification, or inference from aggregate means occurs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "availability": (
        "semantic-change/second-cc-200-v1/label-availability-curve-v2-verifiable/curve_summary.json"
    ),
    "evidence": "semantic-change/second-cc-200-v1/evidence_summary.json",
    "errors": "ablations/minimal-error-decomposition-secondcc-200-v1/summary.json",
    "external": "baselines/p0-grounding-factual-2026-08-13/external-metric-comparison.json",
    "unified": "baselines/p0-unified-2026-08-12/segearth_unified_1000_summary.json",
    "manifest": "baselines/p0-unified-2026-08-12/model_outputs_manifest.summary.json",
    "text": "baselines/p0-unified-2026-08-12/text_metric_summary.json",
    "spice": "baselines/p0-unified-2026-08-12/spice_summary.json",
    "bert": "baselines/p0-unified-2026-08-12/bertscore_summary.json",
    "clip": "baselines/p0-unified-2026-08-12/clipscore_summary.json",
    "composites": "baselines/p0-grounding-factual-2026-08-13/rscc-composite-metrics.json",
    "alignment": "baselines/p0-unified-2026-08-12/unified_metric_alignment.json",
    "roi": "ablations/predicted-roi-calibration-secondcc-200-v1/hybrid_calibration_summary.json",
    "dino": "baselines/p0-grounding-factual-2026-08-13/grounding-dino-size-ablation.json",
    "human": "ablations/hybrid-human-50x3-3raters-v1/human_alignment_summary.json",
    "raters": "human-eval/three-rater-v1/summary.json",
    "parser": "semantic-change/second-cc-200-v1/parser_report_compact.json",
    "parser_configured": "semantic-change/second-cc-200-v1/parser_report_v3.json",
    "selective": (
        "ablations/selective-prediction-minimal-errors-200-v1/visual_confidence_summary.json"
    ),
    "qwen": "qwen3-vl-supplement-v1/summary.json",
}


def fmt(value):
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def build():
    data = {
        name: json.loads((ROOT / "artifacts" / path).read_text(encoding="utf-8"))
        for name, path in SOURCES.items()
    }
    tables = {}

    def add(name, headers, rows, sources, selector):
        tables[name] = {"headers": headers, "rows": rows, "sources": sources, "selector": selector}

    add(
        "availability",
        [
            "Visible classes",
            "Subsets",
            "Eval. coverage ↑",
            "Neutral AUC ↑",
            "BAcc ↑",
            "FSR ↓",
            "U ↓",
        ],
        [
            [
                f"{r['visible_class_count']}/6",
                r["subset_count"],
                r["coverage"],
                r["neutral_auc"],
                r["balanced_accuracy"],
                r["false_support_rate"],
                r["unverifiable_rate"],
            ]
            for r in data["availability"]["curve"]
        ],
        ["availability"],
        "curve[*]",
    )
    names = {
        "gt_class_lookup": "GTClassLookup",
        "open_vocab_only": "MGA-OV + GT-ROI",
        "known_gt_unknown_ov": "MGA-Hybrid",
        "oracle_all_class": "MGA-GT (oracle)",
    }
    add(
        "routes",
        ["Condition", "Method", "Eval. coverage ↑", "Neutral AUC ↑", "BAcc ↑", "FSR ↓"],
        [
            [
                condition,
                names[name],
                r["coverage"],
                r["neutral_auc"],
                r["balanced_accuracy"],
                r["false_support_rate"],
            ]
            for condition, methods in data["evidence"]["conditions"].items()
            for name, r in methods.items()
        ],
        ["evidence"],
        "conditions.*.*",
    )
    add(
        "errors",
        ["Error", "Strict pair acc. ↑", "Neutral AUC ↑", "BAcc ↑", "FSR ↓", "U ↓"],
        [
            [
                r["error_type"],
                r["paired_accuracy"],
                r["neutral_auc"],
                r["balanced_accuracy"],
                r["false_support_rate"],
                r["unverifiable_rate"],
            ]
            for r in data["errors"]["paired_diagnostic"]
            if r["mode"] == "hybrid"
        ],
        ["errors"],
        "paired_diagnostic[mode=hybrid]",
    )
    add(
        "external",
        ["Method", "ROC-AUC ↑", "Scene bootstrap 95% CI", "Oracle BAcc ↑"],
        [
            [
                name.replace("ALOHa", "ALOHa-local"),
                r["roc_auc"],
                "[" + ", ".join(fmt(v) for v in r["roc_auc_scene_bootstrap_95ci"]) + "]",
                r["balanced_accuracy_oracle_threshold"],
            ]
            for name, r in data["external"]["metrics"].items()
        ],
        ["external"],
        "metrics.*",
    )
    add(
        "deltas",
        ["Paired contrast", "AUC difference", "Scene bootstrap 95% CI"],
        [
            [name, r["point"], "[" + ", ".join(fmt(v) for v in r["scene_bootstrap_95ci"]) + "]"]
            for name, r in data["external"]["paired_auc_deltas"].items()
            if name.startswith("MGA-Hybrid")
        ],
        ["external"],
        "paired_auc_deltas.MGA-Hybrid*",
    )
    models = data["unified"]["results"]["hybrid_mask_temporal"]["models"]
    add(
        "unified",
        [
            "System",
            "Captions",
            "Faithfulness",
            "Fact coverage",
            "Temporal",
            "Overall",
            "U",
            "Parser no-claim rate",
        ],
        [
            [
                name,
                r["captions"],
                r["faithfulness"],
                r["coverage"],
                r["temporal"],
                r["overall"],
                r["unverifiable_rate"],
                data["manifest"]["parser"][name]["no_claim"] / r["captions"],
            ]
            for name, r in models.items()
        ],
        ["unified", "manifest"],
        "results.hybrid_mask_temporal.models.*; parser.*.no_claim/captions",
    )
    add(
        "text",
        ["System", "BLEU-4", "METEOR", "ROUGE-L", "CIDEr"],
        [
            [name, *[r[key] for key in ("BLEU-4", "METEOR", "ROUGE-L", "CIDEr")]]
            for name, r in data["text"]["models"].items()
        ],
        ["text"],
        "models.*",
    )
    add(
        "semantic_text",
        ["System", "SPICE", "BERTScore-F1", "BiTemporal CLIP mean", "S*m", "SPIDEr"],
        [
            [
                name,
                data["spice"]["models"][name]["SPICE"],
                data["bert"]["models"][name]["BERTScore-F1"],
                data["clip"]["models"][name]["BiTemporal-CLIP-mean"],
                data["composites"]["models"][name]["S*m"],
                data["composites"]["models"][name]["SPIDEr"],
            ]
            for name in ("Draft", "Refined")
        ],
        ["spice", "bert", "clip", "composites"],
        "models.{Draft,Refined}",
    )
    add(
        "correlations",
        ["Metric", "MGA component", "n", "Spearman ρ", "Kendall τ"],
        [
            [r["metric"], r["mga_component"], r["n"], r["spearman_rho"], r["kendall_tau"]]
            for r in data["alignment"]["correlations"]
            if r["metric"] in ("BLEU-4", "CIDEr", "BERTScore-F1", "BiTemporal-CLIP-mean")
            and r["mga_component"] in ("MGA-Overall", "MGA-Temporal")
        ],
        ["alignment"],
        "correlations[metric/component filter]",
    )
    add(
        "roi",
        ["ROI", "Eval. coverage ↑", "Neutral AUC ↑", "BAcc ↑", "FSR ↓"],
        [
            [
                name,
                *[
                    r["test_at_selected_threshold"][key]
                    for key in (
                        "coverage",
                        "neutral_auc",
                        "balanced_accuracy",
                        "false_support_rate",
                    )
                ],
            ]
            for name, r in data["roi"]["methods"].items()
        ],
        ["roi"],
        "methods.*.test_at_selected_threshold",
    )
    add(
        "dino",
        ["Component", "Base minus Tiny (five-system macro mean)"],
        [[name, r["base_minus_tiny"]] for name, r in data["dino"]["macro_model_mean"].items()],
        ["dino"],
        "macro_model_mean.*.base_minus_tiny",
    )
    add(
        "parser",
        ["Parser setting", "Exact match ↑", "Precision ↑", "Recall ↑", "F1 ↑"],
        [
            [
                name,
                *[r[key] for key in ("exact_match", "claim_precision", "claim_recall", "claim_f1")],
            ]
            for source in ("parser", "parser_configured")
            for name, r in data[source]["parsers"].items()
        ],
        ["parser", "parser_configured"],
        "parsers.* (distinct ontology configurations)",
    )
    add(
        "pilot",
        ["Mode", "Component", "n", "ROC-AUC ↑", "BAcc @ 0.60 ↑"],
        [
            [name, component, r["n"], r["roc_auc"], r["balanced_accuracy_at_0_60"]]
            for name, components in data["human"]["validity_alignment"].items()
            for component, r in components.items()
            if component in ("overall", "temporal")
        ],
        ["human"],
        "validity_alignment.*.{overall,temporal}",
    )
    sel = data["selective"]["methods"]["MGA-Hybrid"]
    add(
        "selective",
        ["Selection", "Coverage", "Accuracy ↑", "FSR ↓", "Supported precision ↑"],
        [
            [
                "All scored",
                sel["evaluation_coverage"],
                *[
                    sel["full_scored_set"][key]
                    for key in ("accuracy", "false_support_rate", "supported_precision")
                ],
            ],
            *[
                [
                    f"Requested {r['target_coverage']:.2f}",
                    r["coverage"],
                    r["accuracy"],
                    r["false_support_rate"],
                    r["supported_precision"],
                ]
                for r in sel["target_coverages"]
                if r.get("attainable")
            ],
        ],
        ["selective"],
        "methods.MGA-Hybrid.{full_scored_set,target_coverages}",
    )
    ledger = {
        "protocol": "paper-experiments-source-ledger-v1",
        "source_hash_contract": (
            "SHA-256 of parsed JSON serialized with sorted keys, UTF-8, "
            "ensure_ascii=False, separators=(',', ':'); independent of checkout line endings"
        ),
        "sources": {
            name: {
                "path": "artifacts/" + path,
                "canonical_json_sha256": hashlib.sha256(
                    json.dumps(
                        json.loads((ROOT / "artifacts" / path).read_text(encoding="utf-8")),
                        sort_keys=True,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
            }
            for name, path in SOURCES.items()
        },
        "tables": tables,
    }
    products = {}
    for language in ("zh-CN", "en"):
        template = ROOT / "paper" / "sections" / f"experiments.{language}.v2.template.md"
        text = template.read_text(encoding="utf-8")
        for name, table in tables.items():
            lines = [
                "| " + " | ".join(table["headers"]) + " |",
                "| " + " | ".join("---" for _ in table["headers"]) + " |",
            ]
            lines += ["| " + " | ".join(fmt(v) for v in row) + " |" for row in table["rows"]]
            lines += [
                "",
                "Source: "
                + "; ".join(
                    f"[{source}](../../artifacts/{SOURCES[source]})" for source in table["sources"]
                ),
            ]
            text = text.replace("{{table:" + name + "}}", "\n".join(lines))
        for source, path in SOURCES.items():
            text = text.replace("{{source:" + source + "}}", f"../../artifacts/{path}")
        if "{{" in text:
            raise ValueError(f"Unresolved placeholder in {template}")
        products[ROOT / "paper" / "sections" / f"experiments.{language}.v2.md"] = text
    products[ROOT / "artifacts" / "paper" / "experiments-v2-source-ledger.json"] = (
        json.dumps(ledger, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    return products


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check outputs without writing")
    args = parser.parse_args()
    for path, text in build().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                raise SystemExit(f"Outdated or missing: {path.relative_to(ROOT)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        print(f"{'Checked' if args.check else 'Wrote'} {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
