"""Deterministic parser intended for smoke tests and parser ablations."""

from __future__ import annotations

import re
from dataclasses import dataclass

from mga.models import AtomicClaim, ChangeType, ClaimRole

DEFAULT_ENTITIES = (
    "residential areas",
    "residential area",
    "residential buildings",
    "residential building",
    "structures",
    "structure",
    "building",
    "buildings",
    "house",
    "houses",
    "villa",
    "villas",
    "paved roads",
    "paved road",
    "road",
    "roads",
    "street",
    "streets",
    "roadway",
    "roadways",
)

NO_CHANGE_PATTERNS = (
    "no change",
    "no changes",
    "unchanged",
    "identical",
    "same scene",
    "same as before",
    "remains the same",
    "no difference",
    "no differences",
)

CHANGE_PATTERNS = {
    ChangeType.ADD: (
        r"\badd(?:ed|s|ing)?\b",
        r"\bappear(?:s|ed|ing)?\b",
        r"\bbuilt\b",
        r"\bbuilds?\b",
        r"\bconstruct(?:ed|s|ing|ion)?\b",
        r"\bemerg(?:e|es|ed|ing)\b",
        r"\bnew\b",
        r"\berect(?:ed|s|ing)?\b",
    ),
    ChangeType.REMOVE: (
        r"\bremov(?:e|es|ed|ing)\b",
        r"\bdemolish(?:es|ed|ing)?\b",
        r"\bdisappear(?:s|ed|ing)?\b",
        r"\bdestroy(?:s|ed|ing)?\b",
        r"\bclear(?:s|ed|ing)?\b",
        r"\bvanish(?:es|ed|ing)?\b",
    ),
    ChangeType.MODIFY: (
        r"\bchang(?:e|es|ed|ing)\b",
        r"\bmodif(?:y|ies|ied|ying)\b",
        r"\breconstruct(?:s|ed|ing|ion)?\b",
        r"\breplac(?:e|es|ed|ing)\b",
        r"\bexpand(?:s|ed|ing|ion)?\b",
        r"\bconvert(?:s|ed|ing)?\b",
    ),
}
CONTEXT_PREFIX = re.compile(
    r"(?:near|beside|along|around|among|next\s+to|surrounded\s+by|"
    r"(?:on\s+)?(?:both\s+)?sides?\s+of|"
    r"(?:on\s+the\s+)?(?:left|right)(?:\s+side)?\s+of)\s+(?:(?:the|a|an)\s+)?$"
)
CLAUSE_BOUNDARY = re.compile(r"[.;,]|\b(?:and|while|but|whereas|then)\b")
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

        location = next((item for item in LOCATIONS if item in normalized), None)
        mentions = _entity_mentions(normalized, self.entities)
        claims: list[AtomicClaim] = []
        seen: set[tuple[str, ClaimRole, ChangeType]] = set()
        for mention in mentions:
            entity = _canonical(mention.group())
            role = (
                ClaimRole.CONTEXT
                if _is_context_mention(normalized, mention.start())
                else ClaimRole.CHANGED
            )
            change_type = (
                ChangeType.NONE
                if role == ClaimRole.CONTEXT
                else _change_type_near(normalized, mention.start(), mention.end())
            )
            key = (entity, role, change_type)
            if key in seen:
                continue
            seen.add(key)
            index = len(claims) + 1
            claims.append(
                AtomicClaim(
                    claim_id=f"c{index:03d}",
                    text=caption,
                    entity=entity,
                    role=role,
                    change_type=change_type,
                    location=location,
                    target_labels=(_target_label(entity),),
                )
            )
        return tuple(claims)


def _entity_mentions(text: str, entities: tuple[str, ...]) -> list[re.Match[str]]:
    candidates = []
    occupied: list[tuple[int, int]] = []
    for entity in sorted(set(entities), key=len, reverse=True):
        for match in re.finditer(rf"(?<!\w){re.escape(entity)}(?!\w)", text):
            if any(match.start() < end and match.end() > start for start, end in occupied):
                continue
            candidates.append(match)
            occupied.append(match.span())
    return sorted(candidates, key=lambda match: match.start())


def _change_type_near(text: str, start: int, end: int) -> ChangeType:
    cues = _cue_matches(text)
    if not cues:
        return ChangeType.UNKNOWN
    clause_start = max(
        (match.end() for match in CLAUSE_BOUNDARY.finditer(text, 0, start)), default=0
    )
    next_boundary = CLAUSE_BOUNDARY.search(text, end)
    clause_end = next_boundary.start() if next_boundary else len(text)
    local = [cue for cue in cues if clause_start <= cue[1] and cue[2] <= clause_end]
    candidates = local or cues
    return min(candidates, key=lambda cue: _span_distance(start, end, cue[1], cue[2]))[0]


def _cue_matches(text: str) -> list[tuple[ChangeType, int, int]]:
    matches = []
    for change_type, patterns in CHANGE_PATTERNS.items():
        for pattern in patterns:
            matches.extend(
                (change_type, match.start(), match.end())
                for match in re.finditer(pattern, text)
            )
    return matches


def _span_distance(left_start: int, left_end: int, right_start: int, right_end: int) -> int:
    if right_end <= left_start:
        return left_start - right_end
    if left_end <= right_start:
        return right_start - left_end
    return 0


def _is_context_mention(text: str, start: int) -> bool:
    return CONTEXT_PREFIX.search(text[max(0, start - 45) : start]) is not None


def _canonical(entity: str) -> str:
    normalized = entity.strip().lower()
    if normalized in {
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
    }:
        return "building"
    return "road"


def _target_label(entity: str) -> int:
    return 2 if entity == "building" else 1
