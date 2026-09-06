"""Ontology-aware parser with an optional lightweight GLiNER recall stage."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from mga.models import AtomicClaim, ChangeType, ClaimRole
from mga.parsing.heuristic import (
    LOCATIONS,
    NO_CHANGE_PATTERNS,
    _change_type_near,
    _is_context_mention,
)
from mga.parsing.ontology import EntityOntology, second_entity_ontology


@dataclass(frozen=True)
class EntityMention:
    text: str
    entity: str
    start: int
    end: int
    score: float
    source: str


class EntityExtractor(Protocol):
    def extract(
        self, text: str, candidate_entities: tuple[str, ...]
    ) -> tuple[EntityMention, ...]:
        """Return normalized entity mentions from text."""


@dataclass
class GlinerEntityExtractor:
    """Lazy zero-shot NER wrapper around the Apache-2.0 GLiNER small model."""

    model_name: str = "urchade/gliner_small-v2.1"
    threshold: float = 0.35
    device: str = "cpu"
    _model: Any = field(default=None, init=False, repr=False)

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from gliner import GLiNER
        except ImportError as exc:
            raise RuntimeError(
                "The optional GLiNER parser requires `pip install gliner`."
            ) from exc
        model = GLiNER.from_pretrained(self.model_name)
        if hasattr(model, "to"):
            model = model.to(self.device)
        self._model = model
        return model

    def extract(
        self, text: str, candidate_entities: tuple[str, ...]
    ) -> tuple[EntityMention, ...]:
        predictions = self._load().predict_entities(
            text,
            list(candidate_entities),
            threshold=self.threshold,
        )
        mentions = []
        for item in predictions:
            entity = str(item.get("label", "")).strip().lower()
            mention_text = str(item.get("text", "")).strip()
            if not entity or not mention_text:
                continue
            start = int(item.get("start", text.lower().find(mention_text.lower())))
            end = int(item.get("end", start + len(mention_text)))
            mentions.append(
                EntityMention(
                    text=mention_text,
                    entity=entity,
                    start=max(0, start),
                    end=max(0, end),
                    score=float(item.get("score", 0.0)),
                    source="gliner",
                )
            )
        return tuple(mentions)


@dataclass
class HybridEntityClaimParser:
    """Use exact ontology aliases first and GLiNER only to recover missed mentions."""

    ontology: EntityOntology = field(default_factory=second_entity_ontology)
    extractor: EntityExtractor | None = None

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
                    metadata={"parser_source": "heuristic"},
                ),
            )

        mentions = list(self._exact_mentions(normalized))
        if self.extractor is not None:
            mentions.extend(
                self.extractor.extract(normalized, tuple(self.ontology.aliases))
            )
        mentions = self._deduplicate_mentions(mentions)
        location = next((item for item in LOCATIONS if item in normalized), None)

        claims: list[AtomicClaim] = []
        seen: set[tuple[str, ClaimRole, ChangeType]] = set()
        for mention in sorted(mentions, key=lambda item: (item.start, item.end)):
            entity = self.ontology.canonicalize(mention.entity)
            if entity is None:
                continue
            role = (
                ClaimRole.CONTEXT
                if _is_context_mention(normalized, mention.start)
                else ClaimRole.CHANGED
            )
            change_type = (
                ChangeType.NONE
                if role == ClaimRole.CONTEXT
                else self._change_type(normalized, mention)
            )
            key = (entity, role, change_type)
            if key in seen:
                continue
            seen.add(key)
            claims.append(
                AtomicClaim(
                    claim_id=f"c{len(claims) + 1:03d}",
                    text=caption,
                    entity=entity,
                    role=role,
                    change_type=change_type,
                    location=location,
                    target_labels=self.ontology.labels_for(entity),
                    metadata={
                        "parser_source": mention.source,
                        "mention": mention.text,
                        "mention_score": mention.score,
                    },
                )
            )
        return tuple(claims)

    def _exact_mentions(self, text: str) -> tuple[EntityMention, ...]:
        mentions = []
        occupied: list[tuple[int, int]] = []
        for alias in sorted(self.ontology.mentions, key=len, reverse=True):
            canonical = self.ontology.canonicalize(alias)
            if canonical is None:
                continue
            for match in re.finditer(rf"(?<!\w){re.escape(alias)}(?!\w)", text):
                if any(
                    match.start() < end and match.end() > start
                    for start, end in occupied
                ):
                    continue
                mentions.append(
                    EntityMention(
                        text=match.group(),
                        entity=canonical,
                        start=match.start(),
                        end=match.end(),
                        score=1.0,
                        source="ontology",
                    )
                )
                occupied.append(match.span())
        return tuple(mentions)

    @staticmethod
    def _deduplicate_mentions(
        mentions: list[EntityMention],
    ) -> tuple[EntityMention, ...]:
        ranked = sorted(
            mentions,
            key=lambda item: (
                item.source != "ontology",
                -item.score,
                -(item.end - item.start),
            ),
        )
        kept: list[EntityMention] = []
        for mention in ranked:
            overlaps = any(
                mention.start < other.end
                and mention.end > other.start
                and mention.entity == other.entity
                for other in kept
            )
            if not overlaps:
                kept.append(mention)
        return tuple(kept)

    @staticmethod
    def _change_type(text: str, mention: EntityMention) -> ChangeType:
        for cue in ("replaced by", "converted to", "turned into"):
            cue_start = text.find(cue)
            if cue_start >= 0:
                cue_end = cue_start + len(cue)
                if mention.end <= cue_start:
                    return ChangeType.REMOVE
                if mention.start >= cue_end:
                    return ChangeType.ADD
        return _change_type_near(text, mention.start, mention.end)
