"""Structured fact graphs and controlled language samples for semantic change data."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class TransitionFact:
    source_id: int
    target_id: int
    source_entity: str
    target_entity: str
    pixel_count: int
    pixel_fraction: float
    location: str
    centroid_xy: tuple[float, float]
    bbox_xyxy: tuple[int, int, int, int]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["centroid_xy"] = list(self.centroid_xy)
        value["bbox_xyxy"] = list(self.bbox_xyxy)
        return value


@dataclass(frozen=True)
class FactGraph:
    sample_id: str
    pre_image: str
    post_image: str
    pre_label: str
    post_label: str
    height: int
    width: int
    transitions: tuple[TransitionFact, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["transitions"] = [item.to_dict() for item in self.transitions]
        return value


def load_label_ids(path: str | Path) -> np.ndarray:
    """Load an indexed/paletted semantic label without converting palette ids to RGB."""

    with Image.open(path) as image:
        array = np.asarray(image)
    if array.ndim != 2:
        raise ValueError(
            f"Expected an indexed two-dimensional semantic label at {path}, "
            f"got shape {array.shape}. Supply a dataset-specific RGB decoder first."
        )
    return array.astype(np.int32, copy=False)


def build_fact_graph(
    *,
    sample_id: str,
    pre_image: str | Path,
    post_image: str | Path,
    pre_label: str | Path,
    post_label: str | Path,
    class_names: dict[int, str],
    min_pixels: int = 64,
) -> FactGraph:
    pre = load_label_ids(pre_label)
    post = load_label_ids(post_label)
    if pre.shape != post.shape:
        raise ValueError(
            f"Semantic labels differ in shape for {sample_id}: {pre.shape} vs {post.shape}"
        )

    height, width = pre.shape
    transitions = []
    for source_id in sorted(int(item) for item in np.unique(pre)):
        if source_id not in class_names:
            continue
        for target_id in sorted(int(item) for item in np.unique(post)):
            if target_id not in class_names or target_id == source_id:
                continue
            mask = np.logical_and(pre == source_id, post == target_id)
            count = int(mask.sum())
            if count < min_pixels:
                continue
            ys, xs = np.nonzero(mask)
            centroid_x = float(xs.mean())
            centroid_y = float(ys.mean())
            transitions.append(
                TransitionFact(
                    source_id=source_id,
                    target_id=target_id,
                    source_entity=class_names[source_id],
                    target_entity=class_names[target_id],
                    pixel_count=count,
                    pixel_fraction=count / float(height * width),
                    location=spatial_location(
                        centroid_x=centroid_x,
                        centroid_y=centroid_y,
                        width=width,
                        height=height,
                    ),
                    centroid_xy=(centroid_x, centroid_y),
                    bbox_xyxy=(
                        int(xs.min()),
                        int(ys.min()),
                        int(xs.max()) + 1,
                        int(ys.max()) + 1,
                    ),
                )
            )
    transitions.sort(key=lambda item: item.pixel_count, reverse=True)
    return FactGraph(
        sample_id=sample_id,
        pre_image=str(pre_image),
        post_image=str(post_image),
        pre_label=str(pre_label),
        post_label=str(post_label),
        height=height,
        width=width,
        transitions=tuple(transitions),
    )


def spatial_location(
    *, centroid_x: float, centroid_y: float, width: int, height: int
) -> str:
    x_ratio = centroid_x / max(width, 1)
    y_ratio = centroid_y / max(height, 1)
    if 1 / 3 <= x_ratio <= 2 / 3 and 1 / 3 <= y_ratio <= 2 / 3:
        return "center"
    vertical = "upper" if y_ratio < 0.5 else "lower"
    horizontal = "left" if x_ratio < 0.5 else "right"
    return f"{vertical}-{horizontal}"


def controlled_samples(
    graph: FactGraph,
    transition: TransitionFact,
    *,
    alternative_entity: str,
) -> tuple[dict[str, Any], ...]:
    """Create factual, minimally contradicted, and paraphrased samples."""

    source = transition.source_entity
    target = transition.target_entity
    location = transition.location
    base = {
        "sample_id": graph.sample_id,
        "pre_image": graph.pre_image,
        "post_image": graph.post_image,
        "pre_label": graph.pre_label,
        "post_label": graph.post_label,
        "transition": transition.to_dict(),
    }
    factual = {
        **base,
        "item_id": f"{graph.sample_id}:factual",
        "sample_type": "factual",
        "caption": (
            f"In the {location}, {source} areas disappeared while "
            f"{target} areas appeared."
        ),
        "is_factually_correct": True,
        "perturbation": None,
        "claims": _claims(source, target, location, transition),
    }
    contradiction = {
        **base,
        "item_id": f"{graph.sample_id}:contradiction",
        "sample_type": "contradiction",
        "caption": (
            f"In the {location}, {source} areas disappeared while "
            f"{alternative_entity} areas appeared."
        ),
        "is_factually_correct": False,
        "perturbation": "target_entity_substitution",
        "claims": _claims(source, alternative_entity, location, transition),
    }
    paraphrase = {
        **base,
        "item_id": f"{graph.sample_id}:paraphrase",
        "sample_type": "paraphrase",
        "caption": (
            f"The {source} cover in the {location} was converted to {target}."
        ),
        "is_factually_correct": True,
        "perturbation": "meaning_preserving_paraphrase",
        "claims": _claims(source, target, location, transition),
    }
    return factual, contradiction, paraphrase


def _claims(
    source: str,
    target: str,
    location: str,
    transition: TransitionFact,
) -> list[dict[str, Any]]:
    return [
        {
            "entity": source,
            "change_type": "remove",
            "location": location,
            "source_id": transition.source_id,
            "target_id": transition.target_id,
        },
        {
            "entity": target,
            "change_type": "add",
            "location": location,
            "source_id": transition.source_id,
            "target_id": transition.target_id,
        },
    ]
