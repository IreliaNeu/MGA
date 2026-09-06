"""Conservative query expansions for multi-class semantic-change evaluation."""

from __future__ import annotations

import re

SEMANTIC_CHANGE_QUERY_GROUPS: dict[str, tuple[str, ...]] = {
    "building": ("building", "house", "residential building", "villa"),
    "tree": ("tree", "tree cover"),
    "low vegetation": ("low vegetation", "grassland"),
    "non-vegetated ground": (
        "non-vegetated ground",
        "bare ground",
        "impervious surface",
    ),
    "water": ("water", "water body", "river", "pond"),
    "playground": ("playground", "sports field", "playing field"),
    "cropland": ("cropland", "cultivated field"),
    "vegetation": ("vegetation", "green cover"),
    "road": ("road", "paved road"),
}


def expand_semantic_change_queries(
    entity: str,
    profile: str = "remote-sensing",
) -> tuple[str, ...]:
    normalized = re.sub(r"\s+", " ", entity.strip().lower().strip(" ."))
    if not normalized:
        return ()
    if profile == "none":
        return (normalized,)
    if profile != "remote-sensing":
        raise ValueError(f"Unsupported query expansion profile: {profile}")
    group = SEMANTIC_CHANGE_QUERY_GROUPS.get(normalized, (normalized,))
    return tuple(dict.fromkeys((normalized, *group)))
