"""Controlled entity-query expansion for remote-sensing grounding."""

from __future__ import annotations

import re

QUERY_EXPANSION_PROFILES = ("none", "remote-sensing")

REMOTE_SENSING_QUERY_GROUPS: dict[str, tuple[str, ...]] = {
    "building": ("building", "house", "residential building", "villa"),
    "road": ("road", "paved road"),
    "parking lot": ("parking lot", "parking area", "car park"),
    "playground": ("playground", "sports field", "playing field"),
    "water": ("water", "water body", "river", "pond"),
}

_ALIASES = {
    "buildings": "building",
    "home": "building",
    "homes": "building",
    "house": "building",
    "houses": "building",
    "residential building": "building",
    "residential buildings": "building",
    "villa": "building",
    "villas": "building",
    "roads": "road",
    "street": "road",
    "streets": "road",
    "roadway": "road",
    "roadways": "road",
    "parking area": "parking lot",
    "parking lots": "parking lot",
    "playgrounds": "playground",
    "water bodies": "water",
}


def expand_grounding_queries(entity: str, profile: str = "none") -> tuple[str, ...]:
    """Return stable, deduplicated text queries for an extracted entity."""
    if profile not in QUERY_EXPANSION_PROFILES:
        raise ValueError(
            f"Unknown query expansion profile {profile!r}; expected {QUERY_EXPANSION_PROFILES}"
        )
    normalized = _normalize(entity)
    if not normalized:
        return ()
    if profile == "none":
        return (normalized,)
    canonical = _ALIASES.get(normalized, normalized)
    group = REMOTE_SENSING_QUERY_GROUPS.get(canonical)
    if group is None:
        return (normalized,)
    return tuple(dict.fromkeys((normalized, *group)))


def format_grounding_query(queries: tuple[str, ...]) -> str:
    """Format multiple Grounding DINO categories as a period-separated prompt."""
    cleaned = tuple(query.strip(" .") for query in queries if query.strip(" ."))
    if not cleaned:
        return "scene."
    return ". ".join(cleaned) + "."


def _normalize(entity: str) -> str:
    return re.sub(r"\s+", " ", entity.strip().lower().strip(" ."))
