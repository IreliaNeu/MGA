"""Entity ontology helpers shared by deterministic and model-assisted parsers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

REMOTE_SENSING_ALIASES: dict[str, tuple[str, ...]] = {
    "building": (
        "building",
        "buildings",
        "house",
        "houses",
        "villa",
        "villas",
        "residential building",
        "residential buildings",
        "residential area",
        "residential areas",
        "structure",
        "structures",
        "built-up area",
        "built-up areas",
        "construction",
        "constructions",
    ),
    "road": (
        "road",
        "roads",
        "paved road",
        "paved roads",
        "street",
        "streets",
        "roadway",
        "roadways",
        "transportation surface",
        "transportation surfaces",
    ),
    "tree": (
        "tree",
        "trees",
        "tree cover",
        "woodland",
        "woodlands",
        "forest",
        "forests",
        "wooded area",
        "wooded areas",
    ),
    "low vegetation": (
        "low vegetation",
        "vegetation",
        "vegetated area",
        "vegetated areas",
        "grass",
        "grassland",
        "grasslands",
        "lawn",
        "lawns",
        "shrub",
        "shrubs",
    ),
    "water": (
        "water",
        "water body",
        "water bodies",
        "river",
        "rivers",
        "lake",
        "lakes",
        "pond",
        "ponds",
        "canal",
        "canals",
    ),
    "non-vegetated ground": (
        "non-vegetated ground",
        "non vegetated ground",
        "non-vegetated surface",
        "non vegetated surface",
        "bare ground",
        "bare land",
        "impervious surface",
        "impervious surfaces",
        "paved surface",
        "paved surfaces",
        "open ground",
    ),
    "playground": (
        "playground",
        "playgrounds",
        "sports field",
        "sports fields",
        "sports ground",
        "sports grounds",
        "athletic field",
        "athletic fields",
    ),
    "bridge": ("bridge", "bridges", "overpass", "overpasses"),
    "greenhouse": ("greenhouse", "greenhouses", "green house", "green houses"),
}


def _singularize(value: str) -> str:
    if value.endswith("ies") and len(value) > 3:
        return f"{value[:-3]}y"
    if value.endswith("ses") and len(value) > 3:
        return value[:-2]
    if value.endswith("s") and not value.endswith("ss") and len(value) > 2:
        return value[:-1]
    return value


def normalize_entity(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9 -]+", " ", value.lower())
    normalized = " ".join(normalized.split()).strip(" -")
    return _singularize(normalized)


@dataclass
class EntityOntology:
    """Map textual mentions to canonical entities and optional dataset labels."""

    aliases: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: dict(REMOTE_SENSING_ALIASES)
    )
    label_map: dict[str, tuple[int, ...]] = field(
        default_factory=lambda: {"road": (1,), "building": (2,)}
    )
    allow_unknown: bool = False

    @property
    def mentions(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                alias
                for values in self.aliases.values()
                for alias in sorted(values, key=len, reverse=True)
            )
        )

    def canonicalize(self, value: str) -> str | None:
        normalized = normalize_entity(value)
        for canonical, aliases in self.aliases.items():
            normalized_aliases = {normalize_entity(alias) for alias in aliases}
            if normalized == normalize_entity(canonical) or normalized in normalized_aliases:
                return canonical
        return normalized if self.allow_unknown and normalized else None

    def labels_for(self, entity: str) -> tuple[int, ...]:
        return tuple(int(item) for item in self.label_map.get(entity, ()))


def core_entity_ontology() -> EntityOntology:
    """Closed building/road ontology used by the original LEVIR-MCI setup."""

    return EntityOntology(
        aliases={key: REMOTE_SENSING_ALIASES[key] for key in ("building", "road")},
        label_map={"road": (1,), "building": (2,)},
    )


def second_entity_ontology(
    label_map: dict[str, tuple[int, ...]] | None = None,
) -> EntityOntology:
    """Open ontology for SECOND; label ids are supplied after palette inspection."""

    keys = (
        "building",
        "tree",
        "low vegetation",
        "water",
        "non-vegetated ground",
        "playground",
        "road",
        "bridge",
        "greenhouse",
    )
    return EntityOntology(
        aliases={key: REMOTE_SENSING_ALIASES[key] for key in keys},
        label_map={} if label_map is None else dict(label_map),
        allow_unknown=True,
    )
