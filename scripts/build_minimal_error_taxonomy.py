"""Build auditable single-factor caption perturbations from structured transitions.

The input is the ``evaluation_samples.jsonl`` produced by
``build_semantic_change_benchmark.py`` (or an equivalent JSONL with
``claims``/``transition`` fields).  Only factually correct source rows are used.
Each negative changes exactly one *controllable semantic slot*; all text and
claim differences are deterministic consequences of that one slot.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ERROR_SLOT = {
    "entity": "target_entity",
    "direction": "target_change",
    "location": "location",
    "relation": "relation_direction",
    "hallucination": "extra_claim",
    "omission": "included_target",
    "no-change": "scene_change_state",
}

LOCATION_CYCLE = (
    "upper-left",
    "upper-right",
    "lower-left",
    "lower-right",
    "center",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--source-types",
        default="factual",
        help="Comma-separated source sample types; default: factual.",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--entity",
        action="append",
        default=[],
        help="Additional canonical entity available for substitutions (repeatable).",
    )
    parser.add_argument("--exclude-original", action="store_true")
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def source_state(item: dict[str, Any]) -> dict[str, Any] | None:
    claims = list(item.get("claims") or [])
    transition = dict(item.get("transition") or {})
    source_claim = next(
        (claim for claim in claims if claim.get("change_type") == "remove"),
        None,
    )
    target_claim = next(
        (claim for claim in claims if claim.get("change_type") == "add"),
        None,
    )
    source_entity = transition.get("source_entity") or (
        source_claim.get("entity") if source_claim else None
    )
    target_entity = transition.get("target_entity") or (
        target_claim.get("entity") if target_claim else None
    )
    if not source_entity or not target_entity:
        return None
    location = transition.get("location")
    if not location:
        location = next(
            (claim.get("location") for claim in claims if claim.get("location")),
            "center",
        )
    return {
        "source_entity": str(source_entity),
        "target_entity": str(target_entity),
        "source_change": "remove",
        "target_change": "add",
        "location": str(location),
        "relation_direction": "source-to-target",
        "extra_claim": None,
        "included_target": True,
        "scene_change_state": "changed",
    }


def collect_entity_pool(items: list[dict[str, Any]], extra_entities: list[str]) -> tuple[str, ...]:
    values = [entity.strip() for entity in extra_entities if entity.strip()]
    for item in items:
        transition = item.get("transition") or {}
        values.extend(
            str(value)
            for value in (
                transition.get("source_entity"),
                transition.get("target_entity"),
            )
            if value
        )
        values.extend(
            str(claim["entity"]) for claim in (item.get("claims") or []) if claim.get("entity")
        )
    return tuple(dict.fromkeys(values))


def alternative_entity(state: dict[str, Any], entity_pool: tuple[str, ...]) -> str:
    excluded = {state["source_entity"], state["target_entity"]}
    candidate = next((entity for entity in entity_pool if entity not in excluded), None)
    return candidate or "unrelated object"


def alternative_location(location: str) -> str:
    normalized = location.lower().replace("_", "-")
    if normalized in LOCATION_CYCLE:
        return LOCATION_CYCLE[(LOCATION_CYCLE.index(normalized) + 1) % len(LOCATION_CYCLE)]
    return "upper-left" if normalized != "upper-left" else "lower-right"


def mutate_state(
    state: dict[str, Any], error_type: str, entity_pool: tuple[str, ...]
) -> dict[str, Any]:
    result = copy.deepcopy(state)
    if error_type == "entity":
        result["target_entity"] = alternative_entity(state, entity_pool)
    elif error_type == "direction":
        result["target_change"] = "remove"
    elif error_type == "location":
        result["location"] = alternative_location(str(state["location"]))
    elif error_type == "relation":
        result["relation_direction"] = "target-to-source"
    elif error_type == "hallucination":
        result["extra_claim"] = {
            "entity": alternative_entity(state, entity_pool),
            "change_type": "add",
            "location": state["location"],
        }
    elif error_type == "omission":
        result["included_target"] = False
    elif error_type == "no-change":
        result["scene_change_state"] = "no-change"
    else:
        raise ValueError(f"Unsupported error type: {error_type}")
    expected = ERROR_SLOT[error_type]
    changed = changed_slots(state, result)
    if changed != [expected]:
        raise AssertionError(f"{error_type} must change only {expected!r}; changed={changed!r}")
    return result


def changed_slots(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    keys = sorted(set(left) | set(right))
    return [key for key in keys if left.get(key) != right.get(key)]


def verb(entity: str, change_type: str) -> str:
    if change_type == "add":
        return f"{entity} areas appeared"
    if change_type == "remove":
        return f"{entity} areas disappeared"
    return f"{entity} areas changed"


def render_caption(state: dict[str, Any]) -> str:
    location = state["location"]
    if state["scene_change_state"] == "no-change":
        return f"No change occurred in the {location}."
    source = state["source_entity"]
    target = state["target_entity"]
    if state["relation_direction"] == "target-to-source":
        main = f"{target} was converted into {source}"
    elif state["included_target"]:
        main = (
            f"{verb(source, state['source_change'])} while {verb(target, state['target_change'])}"
        )
    else:
        main = verb(source, state["source_change"])
    caption = f"In the {location}, {main}."
    if state["extra_claim"]:
        extra = state["extra_claim"]
        caption += " " + verb(extra["entity"], extra["change_type"]).capitalize() + "."
    return caption


def derived_claims(state: dict[str, Any]) -> list[dict[str, Any]]:
    if state["scene_change_state"] == "no-change":
        return [
            {
                "entity": "scene",
                "change_type": "none",
                "location": state["location"],
                "role": "no_change",
            }
        ]
    if state["relation_direction"] == "target-to-source":
        claims = [
            {
                "entity": state["target_entity"],
                "change_type": "remove",
                "location": state["location"],
            },
            {
                "entity": state["source_entity"],
                "change_type": "add",
                "location": state["location"],
            },
        ]
    else:
        claims = [
            {
                "entity": state["source_entity"],
                "change_type": state["source_change"],
                "location": state["location"],
            }
        ]
        if state["included_target"]:
            claims.append(
                {
                    "entity": state["target_entity"],
                    "change_type": state["target_change"],
                    "location": state["location"],
                }
            )
    if state["extra_claim"]:
        claims.append(dict(state["extra_claim"]))
    return claims


def build_taxonomy_rows(
    items: list[dict[str, Any]],
    *,
    source_types: set[str],
    entity_pool: tuple[str, ...],
    limit: int = 0,
    include_original: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    items_by_sample: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        items_by_sample.setdefault(str(item.get("sample_id", "")), []).append(item)
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_samples: set[str] = set()
    for item in sorted(items, key=lambda row: (str(row.get("sample_id")), str(row.get("item_id")))):
        if item.get("sample_type") not in source_types:
            continue
        if not bool(item.get("is_factually_correct", True)):
            continue
        sample_id = str(item.get("sample_id", ""))
        if not sample_id or sample_id in seen_samples:
            continue
        state = source_state(item)
        if state is None:
            rejected.append(
                {
                    "sample_id": sample_id,
                    "item_id": item.get("item_id"),
                    "reason": "missing_remove_add_transition",
                }
            )
            continue
        selected.append({"item": item, "state": state})
        seen_samples.add(sample_id)
        if limit > 0 and len(selected) >= limit:
            break

    rows: list[dict[str, Any]] = []
    for selected_item in selected:
        item = selected_item["item"]
        base = selected_item["state"]
        source_id = str(item.get("item_id") or item["sample_id"])
        local_entities = []
        for related in items_by_sample.get(str(item["sample_id"]), []):
            if related.get("sample_type") != "contradiction":
                continue
            for claim in related.get("claims") or []:
                entity = str(claim.get("entity", "")).strip()
                if entity and entity not in {
                    base["source_entity"],
                    base["target_entity"],
                }:
                    local_entities.append(entity)
        mutation_entity_pool = tuple(dict.fromkeys([*local_entities, *entity_pool]))
        common = {
            "sample_id": str(item["sample_id"]),
            "source_item_id": source_id,
            "source_caption": str(item.get("caption", render_caption(base))),
            "pre_image": item.get("pre_image"),
            "post_image": item.get("post_image"),
            "pre_label": item.get("pre_label"),
            "post_label": item.get("post_label"),
            "transition": item.get("transition"),
            "base_semantics": base,
            "mutation_entity_pool": list(mutation_entity_pool),
        }
        if include_original:
            rows.append(
                {
                    **common,
                    "item_id": f"{source_id}:minimal:original",
                    "sample_type": "minimal_original",
                    "error_type": "none",
                    "is_factually_correct": True,
                    "caption": render_caption(base),
                    "claims": derived_claims(base),
                    "perturbed_semantics": base,
                    "changed_slots": [],
                    "audit": {"single_factor": True, "expected_slot": None},
                }
            )
        for error_type, expected_slot in ERROR_SLOT.items():
            perturbed = mutate_state(base, error_type, mutation_entity_pool)
            rows.append(
                {
                    **common,
                    "item_id": f"{source_id}:minimal:{error_type}",
                    "sample_type": "minimal_error",
                    "error_type": error_type,
                    "is_factually_correct": False,
                    "caption": render_caption(perturbed),
                    "claims": derived_claims(perturbed),
                    "perturbed_semantics": perturbed,
                    "changed_slots": [expected_slot],
                    "audit": {
                        "single_factor": changed_slots(base, perturbed) == [expected_slot],
                        "expected_slot": expected_slot,
                    },
                }
            )
    return rows, rejected


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    items = read_jsonl(args.input)
    source_types = {value.strip() for value in args.source_types.split(",") if value.strip()}
    entity_pool = collect_entity_pool(items, args.entity)
    rows, rejected = build_taxonomy_rows(
        items,
        source_types=source_types,
        entity_pool=entity_pool,
        limit=args.limit,
        include_original=not args.exclude_original,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "minimal_error_manifest.jsonl"
    rejected_path = args.output_dir / "rejected_sources.jsonl"
    write_jsonl(output_path, rows)
    write_jsonl(rejected_path, rejected)
    counts = Counter(row["error_type"] for row in rows)
    summary = {
        "protocol": "minimal-error-taxonomy-v1",
        "input": str(args.input),
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "source_types": sorted(source_types),
        "entity_pool": list(entity_pool),
        "source_scene_count": len({row["sample_id"] for row in rows}),
        "item_count": len(rows),
        "error_counts": dict(sorted(counts.items())),
        "error_slot": ERROR_SLOT,
        "strict_single_factor": all(row["audit"]["single_factor"] for row in rows),
        "rejected_source_count": len(rejected),
        "manifest": str(output_path),
        "rejected_sources": str(rejected_path),
        "note": (
            "Exactly one controllable semantic slot changes per negative. "
            "Caption and derived-claim differences are consequences of that slot."
        ),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
