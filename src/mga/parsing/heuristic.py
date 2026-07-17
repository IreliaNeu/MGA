"""Deterministic parser intended for smoke tests and parser ablations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from mga.models import AtomicClaim, ChangeType, ClaimRole

DEFAULT_ENTITIES = (
    "building",
    "buildings",
    "house",
    "houses",
    "road",
    "roads",
    "tree",
    "trees",
    "vegetation",
    "forest",
    "water",
    "parking lot",
    "playground",
)

NO_CHANGE_PATTERNS = (
    "no change",
    "no changes",
    "unchanged",
    "identical",
    "same scene",
)

ADD_CUES = ("add", "appear", "build", "construct", "emerge", "new", "erect")
REMOVE_CUES = ("remove", "demolish", "disappear", "destroy", "clear", "vanish")
MODIFY_CUES = ("change", "modify", "reconstruct", "replace", "expand", "convert")
CONTEXT_CUES = ("near", "beside", "along", "next to", "surrounded by", "among")
LOCATIONS = (
    "upper-left",
    "upper-right",
    "lower-left",
    "lower-right",
    "left",
    "right",
    "center",
    "central",
    "top",
    "bottom",
)


@dataclass
class HeuristicClaimParser:
    entities: tuple[str, ...] = DEFAULT_ENTITIES

    def parse(self, caption: str) -> tuple[AtomicClaim, ...]:
        normalized = " ".join(caption.lower().split())
        if any(pattern in normalized for pattern in NO_CHANGE_PATTERNS):
            return (
                AtomicClaim(
                    claim_id="c001",
                    text=caption,
                    entity="scene",
                    role=ClaimRole.NO_CHANGE,
                    change_type=ChangeType.NONE,
                ),
            )

        change_type = _change_type(normalized)
        location = next((item for item in LOCATIONS if item in normalized), None)
        found = [entity for entity in self.entities if _contains(normalized, entity)]
        claims: list[AtomicClaim] = []
        for index, entity in enumerate(found, start=1):
            role = ClaimRole.CHANGED
            if any(f"{cue} {entity}" in normalized for cue in CONTEXT_CUES):
                role = ClaimRole.CONTEXT
            claims.append(
                AtomicClaim(
                    claim_id=f"c{index:03d}",
                    text=caption,
                    entity=_singular(entity),
                    role=role,
                    change_type=change_type if role == ClaimRole.CHANGED else ChangeType.NONE,
                    location=location,
                )
            )
        return tuple(claims)


def _change_type(text: str) -> ChangeType:
    if any(cue in text for cue in REMOVE_CUES):
        return ChangeType.REMOVE
    if any(cue in text for cue in ADD_CUES):
        return ChangeType.ADD
    if any(cue in text for cue in MODIFY_CUES):
        return ChangeType.MODIFY
    return ChangeType.UNKNOWN


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def _singular(entity: str) -> str:
    mapping = {"buildings": "building", "houses": "house", "roads": "road", "trees": "tree"}
    return mapping.get(entity, entity)
