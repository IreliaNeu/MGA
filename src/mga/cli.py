"""Command-line interface for local preparation and AutoDL evaluation."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from mga.grounding import CachedGrounder, EvidenceCache, HFGroundingDinoGrounder
from mga.grounding.manual import MetadataMaskGrounder
from mga.io import load_manifest, read_jsonl, validate_files, write_jsonl
from mga.parsing import HeuristicClaimParser, OpenAICompatibleClaimParser
from mga.perturbations import make_perturbations
from mga.pipeline import enrich_claims, score_records
from mga.prepare import attach_change_agent_texts, convert_feedback_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mga", description="Mask-Guided Alignment toolkit")
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare-feedback", help="Convert Draft/Guided result JSONL")
    prepare.add_argument("--input", required=True)
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--mask-root", required=True)
    prepare.add_argument("--mask-template", default="{image_stem}.png")
    prepare.add_argument("--dataset", default="LEVIR-MCI")

    attach = commands.add_parser("attach-change-agent", help="Attach per-sample text outputs")
    attach.add_argument("--manifest", required=True)
    attach.add_argument("--results-dir", required=True)
    attach.add_argument("--output", required=True)
    attach.add_argument("--glob", default="*.txt")
    attach.add_argument("--allow-missing", action="store_true")

    validate = commands.add_parser("validate", help="Validate a canonical manifest")
    validate.add_argument("--manifest", required=True)

    parse = commands.add_parser("parse", help="Extract and persist atomic claims")
    parse.add_argument("--manifest", required=True)
    parse.add_argument("--output", required=True)
    parse.add_argument("--parser", choices=("heuristic", "openai"), default="heuristic")
    parse.add_argument("--model", default=os.getenv("MGA_PARSER_MODEL"))
    parse.add_argument("--force", action="store_true")

    perturb = commands.add_parser("perturb", help="Create controlled caption corruptions")
    perturb.add_argument("--manifest", required=True)
    perturb.add_argument("--output", required=True)
    perturb.add_argument("--injected-entity", default="a new building appears in the center")

    score = commands.add_parser("score", help="Run grounding and MGA scoring")
    score.add_argument("--manifest", required=True)
    score.add_argument("--output", required=True)
    score.add_argument("--method", choices=("v1", "v2"), default="v2")
    score.add_argument("--grounder", choices=("metadata", "hf-dino"), default="metadata")
    score.add_argument("--cache-dir", default="cache/grounding")
    score.add_argument("--device", default="cuda")
    score.add_argument("--dino-model", default="IDEA-Research/grounding-dino-tiny")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "prepare-feedback":
        count = convert_feedback_jsonl(
            args.input,
            args.output,
            args.mask_root,
            mask_template=args.mask_template,
            dataset=args.dataset,
        )
        print(f"Wrote {count} Draft/Guided records to {args.output}")
        return 0

    if args.command == "attach-change-agent":
        appended, missing = attach_change_agent_texts(
            read_jsonl(args.manifest),
            args.results_dir,
            args.output,
            glob_pattern=args.glob,
            strict=not args.allow_missing,
        )
        print(f"Attached {appended} Change-Agent records; missing={len(missing)}")
        return 0

    if args.command == "validate":
        records = load_manifest(args.manifest)
        errors = validate_files(records)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"Valid manifest: {len(records)} records")
        return 0

    if args.command == "parse":
        records = load_manifest(args.manifest, resolve_paths=False)
        parser = _claim_parser(args)
        enriched = list(enrich_claims(records, parser, force=args.force))
        write_jsonl(args.output, (record.to_dict() for record in enriched))
        print(f"Wrote {len(enriched)} parsed records to {args.output}")
        return 0

    if args.command == "perturb":
        records = load_manifest(args.manifest, resolve_paths=False)
        variants = make_perturbations(records, injected_entity=args.injected_entity)
        write_jsonl(args.output, (record.to_dict() for record in variants))
        print(f"Wrote {len(variants)} controlled perturbations to {args.output}")
        return 0

    if args.command == "score":
        records = load_manifest(args.manifest)
        missing_claims = [record for record in records if not record.claims]
        if missing_claims:
            raise SystemExit(
                f"{len(missing_claims)} records have no claims. Run `mga parse` first."
            )
        grounder = _grounder(args, Path(args.manifest).resolve().parent)
        rows = score_records(records, grounder, method=args.method)
        write_jsonl(args.output, rows)
        print(f"Wrote {args.method} scores to {args.output}")
        return 0
    return 2


def _claim_parser(args):
    if args.parser == "heuristic":
        return HeuristicClaimParser()
    if not args.model:
        raise SystemExit("--model or MGA_PARSER_MODEL is required for the OpenAI parser")
    return OpenAICompatibleClaimParser(model=args.model)


def _grounder(args, manifest_dir: Path):
    if args.grounder == "metadata":
        backend = MetadataMaskGrounder(manifest_dir)
    else:
        backend = HFGroundingDinoGrounder(model_id=args.dino_model, device=args.device)
    return CachedGrounder(backend, EvidenceCache(args.cache_dir))


if __name__ == "__main__":
    raise SystemExit(main())
