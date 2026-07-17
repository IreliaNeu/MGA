"""Typed data contracts shared by parsers, grounders, scorers, and the CLI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class StrEnum(str, Enum):
    """A Python 3.10 compatible string enum."""

    def __str__(self) -> str:
        return self.value


class ClaimRole(StrEnum):
    CHANGED = "changed"
    CONTEXT = "context"
    NO_CHANGE = "no_change"


class ChangeType(StrEnum):
    ADD = "add"
    REMOVE = "remove"
    MODIFY = "modify"
    UNKNOWN = "unknown"
    NONE = "none"


class ClaimStatus(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True)
class AtomicClaim:
    """A spatially verifiable atomic assertion extracted from a caption."""

    claim_id: str
    text: str
    entity: str
    role: ClaimRole
    change_type: ChangeType = ChangeType.UNKNOWN
    location: str | None = None
    count: str | None = None
    attributes: tuple[str, ...] = ()
    target_labels: tuple[int, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> AtomicClaim:
        return cls(
            claim_id=str(value["claim_id"]),
            text=str(value.get("text", "")),
            entity=str(value.get("entity", "scene")),
            role=ClaimRole(value["role"]),
            change_type=ChangeType(value.get("change_type", "unknown")),
            location=value.get("location"),
            count=value.get("count"),
            attributes=tuple(value.get("attributes", ())),
            target_labels=tuple(int(item) for item in value.get("target_labels", ())),
            metadata=dict(value.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["role"] = self.role.value
        value["change_type"] = self.change_type.value
        value["attributes"] = list(self.attributes)
        value["target_labels"] = list(self.target_labels)
        return value


@dataclass(frozen=True)
class SampleRecord:
    """One model caption aligned to a bi-temporal image pair and change mask."""

    sample_id: str
    model: str
    caption: str
    pre_image: str
    post_image: str
    change_mask: str
    dataset: str = "unknown"
    split: str = "test"
    feedback: str | None = None
    claims: tuple[AtomicClaim, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> SampleRecord:
        required = ("sample_id", "model", "caption", "pre_image", "post_image", "change_mask")
        missing = [key for key in required if not value.get(key)]
        if missing:
            raise ValueError(f"Missing required manifest fields: {', '.join(missing)}")
        return cls(
            sample_id=str(value["sample_id"]),
            model=str(value["model"]),
            caption=str(value["caption"]),
            pre_image=str(value["pre_image"]),
            post_image=str(value["post_image"]),
            change_mask=str(value["change_mask"]),
            dataset=str(value.get("dataset", "unknown")),
            split=str(value.get("split", "test")),
            feedback=value.get("feedback"),
            claims=tuple(AtomicClaim.from_dict(item) for item in value.get("claims", ())),
            metadata=dict(value.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["claims"] = [claim.to_dict() for claim in self.claims]
        return value


@dataclass
class GroundingEvidence:
    """Entity support masks grounded independently in pre and post images."""

    pre_mask: np.ndarray | None = None
    post_mask: np.ndarray | None = None
    pre_confidence: float = 0.0
    post_confidence: float = 0.0
    backend: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClaimScore:
    claim_id: str
    role: ClaimRole
    change_type: ChangeType
    status: ClaimStatus
    faithfulness: float | None
    spatial_support: float | None
    temporal_support: float | None
    grounding_confidence: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["role"] = self.role.value
        value["change_type"] = self.change_type.value
        value["status"] = self.status.value
        return value


@dataclass(frozen=True)
class CaptionScore:
    sample_id: str
    model: str
    faithfulness: float | None
    coverage: float | None
    temporal: float | None
    context_support: float | None
    unverifiable_rate: float
    overall: float | None
    claim_scores: tuple[ClaimScore, ...]
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["claim_scores"] = [score.to_dict() for score in self.claim_scores]
        return value


@dataclass(frozen=True)
class LegacyCaptionScore:
    sample_id: str
    model: str
    changed_score: float
    context_score: float
    mga: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
