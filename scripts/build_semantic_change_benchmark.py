"""Build fact graphs and three controlled language samples from semantic labels."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict, deque
from pathlib import Path

from mga.semantic_change import build_fact_graph, controlled_samples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-name", default="SECOND")
    parser.add_argument("--split", default="train")
    parser.add_argument("--pre-image-dir", default="im1")
    parser.add_argument("--post-image-dir", default="im2")
    parser.add_argument("--pre-label-dir", default="label1")
    parser.add_argument("--post-label-dir", default="label2")
    parser.add_argument(
        "--class-map",
        required=True,
        help='JSON id-to-name map, e.g. \'{"1":"ground","2":"tree"}\'',
    )
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--candidate-limit", type=int, default=0)
    parser.add_argument("--min-pixels", type=int, default=64)
    parser.add_argument("--seed", type=int, default=20260726)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    class_names = {int(key): str(value) for key, value in json.loads(args.class_map).items()}
    split_root = args.dataset_root / args.split
    directories = {
        "pre_image": split_root / args.pre_image_dir,
        "post_image": split_root / args.post_image_dir,
        "pre_label": split_root / args.pre_label_dir,
        "post_label": split_root / args.post_label_dir,
    }
    missing = [f"{key}={path}" for key, path in directories.items() if not path.is_dir()]
    if missing:
        raise FileNotFoundError("Missing semantic dataset directories: " + ", ".join(missing))

    names = sorted(path.name for path in directories["pre_image"].glob("*.png"))
    if args.candidate_limit > 0:
        names = names[: args.candidate_limit]
    candidates = []
    rejected = []
    for name in names:
        paths = {key: path / name for key, path in directories.items()}
        if not all(path.is_file() for path in paths.values()):
            rejected.append({"name": name, "reason": "missing_aligned_file"})
            continue
        graph = build_fact_graph(
            sample_id=f"{args.dataset_name.lower()}_{Path(name).stem}",
            pre_image=paths["pre_image"],
            post_image=paths["post_image"],
            pre_label=paths["pre_label"],
            post_label=paths["post_label"],
            class_names=class_names,
            min_pixels=args.min_pixels,
        )
        if not graph.transitions:
            rejected.append({"name": name, "reason": "no_eligible_transition"})
            continue
        candidates.append((graph, graph.transitions[0]))

    selected = balanced_select(candidates, args.limit, args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fact_path = args.output_dir / "fact_graphs.jsonl"
    item_path = args.output_dir / "evaluation_samples.jsonl"
    transition_counts: dict[str, int] = defaultdict(int)
    sample_type_counts: dict[str, int] = defaultdict(int)
    all_entities = tuple(dict.fromkeys(class_names.values()))

    with fact_path.open("w", encoding="utf-8") as fact_file, item_path.open(
        "w", encoding="utf-8"
    ) as item_file:
        for graph, transition in selected:
            fact_file.write(json.dumps(graph.to_dict(), ensure_ascii=False) + "\n")
            transition_key = (
                f"{transition.source_entity}->{transition.target_entity}"
            )
            transition_counts[transition_key] += 1
            alternatives = [
                item
                for item in all_entities
                if item not in {transition.source_entity, transition.target_entity}
            ]
            if not alternatives:
                alternatives = ["unrelated object"]
            alternative = alternatives[
                sum(ord(char) for char in graph.sample_id) % len(alternatives)
            ]
            for item in controlled_samples(
                graph,
                transition,
                alternative_entity=alternative,
            ):
                item["dataset"] = args.dataset_name
                item_file.write(json.dumps(item, ensure_ascii=False) + "\n")
                sample_type_counts[item["sample_type"]] += 1

    manifest = {
        "dataset": args.dataset_name,
        "split": args.split,
        "requested_scene_count": args.limit,
        "selected_scene_count": len(selected),
        "evaluation_item_count": sum(sample_type_counts.values()),
        "class_map": class_names,
        "min_pixels": args.min_pixels,
        "seed": args.seed,
        "transition_counts": dict(sorted(transition_counts.items())),
        "sample_type_counts": dict(sorted(sample_type_counts.items())),
        "rejected_count": len(rejected),
        "fact_graphs": str(fact_path),
        "evaluation_samples": str(item_path),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


def balanced_select(
    candidates: list[tuple[object, object]],
    limit: int,
    seed: int,
) -> list[tuple[object, object]]:
    rng = random.Random(seed)
    groups: dict[tuple[int, int], list[tuple[object, object]]] = defaultdict(list)
    for graph, transition in candidates:
        groups[(transition.source_id, transition.target_id)].append((graph, transition))
    queues = {}
    for key, values in groups.items():
        rng.shuffle(values)
        queues[key] = deque(values)

    selected = []
    keys = sorted(queues)
    while len(selected) < limit and keys:
        next_keys = []
        for key in keys:
            queue = queues[key]
            if queue and len(selected) < limit:
                selected.append(queue.popleft())
            if queue:
                next_keys.append(key)
        keys = next_keys
    return selected


if __name__ == "__main__":
    main()
