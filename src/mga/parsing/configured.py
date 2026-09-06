"""Build dataset-specific entity ontologies from versioned JSON mappings."""

from __future__ import annotations

import json
from pathlib import Path

from mga.parsing.ontology import (
    REMOTE_SENSING_ALIASES,
    EntityOntology,
    normalize_entity,
)


def configured_entity_ontology(
    *,
    class_names: dict[int, str],
    surface_forms: dict[str, tuple[str, ...]] | None = None,
    allow_unknown: bool = True,
) -> EntityOntology:
    """Merge canonical labels, shared aliases, and dataset surface forms."""

    aliases: dict[str, tuple[str, ...]] = {}
    label_map: dict[str, tuple[int, ...]] = {}
    configured = surface_forms or {}
    for class_id, raw_entity in class_names.items():
        entity = normalize_entity(raw_entity)
        candidates = (
            entity,
            *REMOTE_SENSING_ALIASES.get(entity, ()),
            *configured.get(entity, ()),
        )
        aliases[entity] = tuple(
            dict.fromkeys(
                value.strip().lower()
                for value in candidates
                if value and value.strip()
            )
        )
        label_map[entity] = (int(class_id),)
    return EntityOntology(
        aliases=aliases,
        label_map=label_map,
        allow_unknown=allow_unknown,
    )


def load_surface_forms(path: str | Path) -> dict[str, tuple[str, ...]]:
    """Load ``canonical -> aliases`` mappings from a JSON file."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        normalize_entity(str(entity)): tuple(str(value) for value in values)
        for entity, values in raw.items()
    }
