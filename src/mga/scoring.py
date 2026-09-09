"""Legacy MGA and MGA v2 scoring implementations.

MGA v2 deliberately reports a score vector. A single scalar is retained as an
optional summary, not as a replacement for faithfulness, coverage, temporal
support, context support, and the unverifiable rate.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np

from mga.mask_ops import (
    as_bool_mask,
    component_coverage,
    filter_intersecting_components,
    intersection_over_union,
    non_overlap_ratio,
    support_precision,
    temporal_difference,
    temporal_novelty,
)
from mga.models import (
    AtomicClaim,
    CaptionScore,
    ChangeType,
    ClaimRole,
    ClaimScore,
    ClaimStatus,
    EvidenceMode,
    GroundingEvidence,
    LegacyCaptionScore,
    SampleRecord,
)


@dataclass(frozen=True)
class MGAV2Config:
    evidence_mode: EvidenceMode = EvidenceMode.FULL_TARGET
    min_grounding_confidence: float = 0.25
    supported_threshold: float = 0.60
    contradicted_threshold: float = 0.25
    spatial_weight: float = 0.65
    temporal_weight: float = 0.35
    overall_faithfulness_weight: float = 0.55
    overall_coverage_weight: float = 0.25
    overall_temporal_weight: float = 0.20
    component_overlap_threshold: float = 0.10
    min_component_area: int = 4

    def __post_init__(self) -> None:
        try:
            evidence_mode = EvidenceMode(self.evidence_mode)
        except ValueError as exc:
            valid = ", ".join(mode.value for mode in EvidenceMode)
            raise ValueError(
                f"Unknown evidence_mode {self.evidence_mode!r}; choose {valid}"
            ) from exc
        object.__setattr__(self, "evidence_mode", evidence_mode)
        probabilities = (
            self.min_grounding_confidence,
            self.supported_threshold,
            self.contradicted_threshold,
            self.component_overlap_threshold,
        )
        if any(value < 0 or value > 1 for value in probabilities):
            raise ValueError("Thresholds must be in [0, 1]")
        if self.contradicted_threshold >= self.supported_threshold:
            raise ValueError("contradicted_threshold must be lower than supported_threshold")
        if self.min_component_area < 1:
            raise ValueError("min_component_area must be positive")


class MGAV2Scorer:
    """Score atomic claims against mask and bi-temporal grounding evidence."""

    def __init__(self, config: MGAV2Config | None = None) -> None:
        self.config = config or MGAV2Config()

    def score(
        self,
        record: SampleRecord,
        change_mask: np.ndarray,
        evidence_by_claim: Mapping[str, GroundingEvidence],
    ) -> CaptionScore:
        label_mask = np.asarray(change_mask)
        if label_mask.ndim != 2:
            raise ValueError(f"Expected a 2D change mask, got {label_mask.shape}")
        mask_labels = tuple(int(value) for value in record.metadata.get("mask_labels", ()))
        coverage_change_mask = _select_labels(label_mask, mask_labels)

        claim_scores: list[ClaimScore] = []
        coverage_support = np.zeros_like(coverage_change_mask, dtype=bool)
        context_values: list[float] = []

        for claim in record.claims:
            evidence = evidence_by_claim.get(claim.claim_id, GroundingEvidence())
            claim_change_mask = _select_labels(label_mask, claim.target_labels)
            score, coverage_mask = self.score_claim(claim, evidence, claim_change_mask)
            claim_scores.append(score)
            if coverage_mask is not None:
                coverage_support |= coverage_mask
            if claim.role == ClaimRole.CONTEXT and score.faithfulness is not None:
                context_values.append(score.faithfulness)

        changed_scores = [
            item.faithfulness
            for item in claim_scores
            if item.role in {ClaimRole.CHANGED, ClaimRole.NO_CHANGE}
            and item.faithfulness is not None
        ]
        temporal_scores = [
            item.temporal_support for item in claim_scores if item.temporal_support is not None
        ]

        faithfulness = _mean(changed_scores)
        temporal = _mean(temporal_scores)
        context_support = _mean(context_values)
        coverage = self._coverage(
            record.claims, coverage_change_mask, coverage_support, claim_scores
        )
        unverifiable_rate = (
            sum(item.status == ClaimStatus.UNVERIFIABLE for item in claim_scores)
            / len(claim_scores)
            if claim_scores
            else 1.0
        )
        overall = self._overall(faithfulness, coverage, temporal)

        return CaptionScore(
            sample_id=record.sample_id,
            model=record.model,
            faithfulness=faithfulness,
            coverage=coverage,
            temporal=temporal,
            context_support=context_support,
            unverifiable_rate=float(unverifiable_rate),
            overall=overall,
            claim_scores=tuple(claim_scores),
            metadata={
                "metric": "mga_v2",
                "evidence_mode": self.config.evidence_mode.value,
                "num_claims": len(claim_scores),
                "mask_labels": list(mask_labels),
            },
        )

    def score_claim(
        self,
        claim: AtomicClaim,
        evidence: GroundingEvidence,
        change_mask: np.ndarray,
    ) -> tuple[ClaimScore, np.ndarray | None]:
        shape = change_mask.shape
        pre = as_bool_mask(evidence.pre_mask, shape)
        post = as_bool_mask(evidence.post_mask, shape)
        max_confidence = float(max(evidence.pre_confidence, evidence.post_confidence))

        if claim.role == ClaimRole.NO_CHANGE:
            value = float(not change_mask.any())
            status = ClaimStatus.SUPPORTED if value == 1.0 else ClaimStatus.CONTRADICTED
            return (
                ClaimScore(
                    claim_id=claim.claim_id,
                    role=claim.role,
                    change_type=ChangeType.NONE,
                    status=status,
                    faithfulness=value,
                    spatial_support=value,
                    temporal_support=None,
                    grounding_confidence=1.0,
                    reason="The no-change assertion is evaluated directly against the change mask.",
                ),
                None,
            )

        if self.config.evidence_mode == EvidenceMode.MASK_LABEL_ONLY:
            return self._score_mask_label_only(claim, change_mask)

        if claim.role == ClaimRole.CONTEXT:
            if max_confidence < self.config.min_grounding_confidence or not (
                pre.any() or post.any()
            ):
                return self._unknown(
                    claim, max_confidence, "Context entity could not be grounded."
                ), None
            # v1 assumed context must avoid change pixels. v2 verifies existence only and does
            # not treat overlap as an error because a valid reference object can touch a change.
            value = max_confidence
            status = self._status(value)
            return (
                ClaimScore(
                    claim_id=claim.claim_id,
                    role=claim.role,
                    change_type=claim.change_type,
                    status=status,
                    faithfulness=value,
                    spatial_support=None,
                    temporal_support=None,
                    grounding_confidence=max_confidence,
                    reason="Context existence is supported; change-mask overlap is not penalized.",
                ),
                None,
            )

        if not change_mask.any():
            return (
                ClaimScore(
                    claim_id=claim.claim_id,
                    role=claim.role,
                    change_type=claim.change_type,
                    status=ClaimStatus.CONTRADICTED,
                    faithfulness=0.0,
                    spatial_support=0.0,
                    temporal_support=0.0,
                    grounding_confidence=max_confidence,
                    reason="A changed-entity claim contradicts an empty ground-truth change mask.",
                ),
                None,
            )

        temporal_pre = pre
        temporal_post = post
        if self.config.evidence_mode == EvidenceMode.GT_ROI_GATED:
            temporal_pre = np.logical_and(pre, change_mask)
            temporal_post = np.logical_and(post, change_mask)

        target, other, target_confidence = self._temporal_masks(
            claim.change_type, temporal_pre, temporal_post, evidence
        )
        if target_confidence < self.config.min_grounding_confidence or not target.any():
            if self.config.evidence_mode == EvidenceMode.HYBRID_MASK_TEMPORAL:
                if not claim.target_labels:
                    return (
                        self._unknown(
                            claim,
                            target_confidence,
                            "Hybrid mode requires parser-provided target_labels.",
                        ),
                        None,
                    )
                return (
                    ClaimScore(
                        claim_id=claim.claim_id,
                        role=claim.role,
                        change_type=claim.change_type,
                        status=ClaimStatus.UNVERIFIABLE,
                        faithfulness=None,
                        spatial_support=1.0,
                        temporal_support=None,
                        grounding_confidence=target_confidence,
                        reason=(
                            "The GT class supports entity presence, but SegEarth "
                            "cannot verify the temporal direction."
                        ),
                    ),
                    change_mask.copy(),
                )
            return (
                self._unknown(
                    claim,
                    target_confidence,
                    "Target-time entity support is missing or below the grounding threshold.",
                ),
                None,
            )

        support = target
        if self.config.evidence_mode == EvidenceMode.HYBRID_MASK_TEMPORAL:
            if not claim.target_labels:
                return (
                    self._unknown(
                        claim,
                        target_confidence,
                        "Hybrid mode requires parser-provided target_labels.",
                    ),
                    None,
                )
            support = change_mask.copy()
        elif self.config.evidence_mode == EvidenceMode.TEMPORAL_DELTA:
            support = self._delta_mask(claim.change_type, pre, post)

        spatial = support_precision(support, change_mask)
        temporal_value: float | None
        if claim.change_type in {ChangeType.ADD, ChangeType.REMOVE}:
            temporal_value = temporal_novelty(target, other, change_mask)
        elif claim.change_type == ChangeType.MODIFY:
            temporal_value = temporal_difference(
                temporal_pre, temporal_post, change_mask
            )
        else:
            temporal_value = None

        faithfulness = _weighted_available(
            (spatial, self.config.spatial_weight),
            (temporal_value, self.config.temporal_weight),
        )
        status = self._joint_status(spatial, temporal_value)
        if self.config.evidence_mode == EvidenceMode.HYBRID_MASK_TEMPORAL:
            reason = {
                ClaimStatus.SUPPORTED: (
                    "The GT class supports entity presence and SegEarth supports "
                    "the temporal direction."
                ),
                ClaimStatus.CONTRADICTED: (
                    "The GT class is present, but SegEarth contradicts the claimed "
                    "temporal direction."
                ),
                ClaimStatus.UNVERIFIABLE: (
                    "The GT class is present, but temporal evidence is ambiguous."
                ),
            }[status]
        else:
            reason = {
                ClaimStatus.SUPPORTED: (
                    "Spatial and temporal evidence support the changed-entity claim."
                ),
                ClaimStatus.CONTRADICTED: (
                    "The grounded entity is inconsistent with the change evidence."
                ),
                ClaimStatus.UNVERIFIABLE: (
                    "Evidence is ambiguous under the configured thresholds."
                ),
            }[status]
        return (
            ClaimScore(
                claim_id=claim.claim_id,
                role=claim.role,
                change_type=claim.change_type,
                status=status,
                faithfulness=faithfulness,
                spatial_support=spatial,
                temporal_support=temporal_value,
                grounding_confidence=target_confidence,
                reason=reason,
            ),
            support,
        )

    def _score_mask_label_only(
        self,
        claim: AtomicClaim,
        change_mask: np.ndarray,
    ) -> tuple[ClaimScore, np.ndarray | None]:
        if claim.role == ClaimRole.CONTEXT:
            return (
                self._unknown(
                    claim,
                    0.0,
                    "MaskLabelOnly cannot verify static context because the label mask "
                    "contains changed classes only.",
                ),
                None,
            )
        if claim.role != ClaimRole.CHANGED:
            return self._unknown(claim, 0.0, "Unsupported claim role."), None
        if not claim.target_labels:
            return (
                self._unknown(
                    claim,
                    0.0,
                    "MaskLabelOnly requires parser-provided target_labels.",
                ),
                None,
            )

        value = float(change_mask.any())
        status = ClaimStatus.SUPPORTED if value == 1.0 else ClaimStatus.CONTRADICTED
        reason = (
            "Parser target_labels match a non-empty ground-truth change class; "
            "no SegEarth evidence is used."
            if value == 1.0
            else "The parser-mapped ground-truth change class is absent."
        )
        return (
            ClaimScore(
                claim_id=claim.claim_id,
                role=claim.role,
                change_type=claim.change_type,
                status=status,
                faithfulness=value,
                spatial_support=value,
                temporal_support=None,
                grounding_confidence=1.0,
                reason=reason,
            ),
            change_mask.copy() if value == 1.0 else None,
        )

    def _coverage(
        self,
        claims: Iterable[AtomicClaim],
        change_mask: np.ndarray,
        support: np.ndarray,
        scores: Iterable[ClaimScore],
    ) -> float | None:
        if not change_mask.any():
            no_change_supported = any(
                score.role == ClaimRole.NO_CHANGE and score.status == ClaimStatus.SUPPORTED
                for score in scores
            )
            changed_claim_exists = any(claim.role == ClaimRole.CHANGED for claim in claims)
            return float(no_change_supported and not changed_claim_exists)
        if not any(claim.role == ClaimRole.CHANGED for claim in claims):
            return 0.0
        return component_coverage(
            change_mask,
            support,
            overlap_threshold=self.config.component_overlap_threshold,
            min_component_area=self.config.min_component_area,
        )

    def _overall(
        self,
        faithfulness: float | None,
        coverage: float | None,
        temporal: float | None,
    ) -> float | None:
        return _weighted_available(
            (faithfulness, self.config.overall_faithfulness_weight),
            (coverage, self.config.overall_coverage_weight),
            (temporal, self.config.overall_temporal_weight),
        )

    def _status(self, value: float) -> ClaimStatus:
        if value >= self.config.supported_threshold:
            return ClaimStatus.SUPPORTED
        if value <= self.config.contradicted_threshold:
            return ClaimStatus.CONTRADICTED
        return ClaimStatus.UNVERIFIABLE

    def _joint_status(self, spatial: float, temporal: float | None) -> ClaimStatus:
        """Require every available evidence axis to pass its own threshold.

        A weighted average alone can hide a reversed add/remove direction behind a
        high spatial score. Joint thresholding makes the diagnostic status strict,
        while the continuous faithfulness value remains available for correlation.
        """
        axes = [spatial] if temporal is None else [spatial, temporal]
        if any(value <= self.config.contradicted_threshold for value in axes):
            return ClaimStatus.CONTRADICTED
        if all(value >= self.config.supported_threshold for value in axes):
            return ClaimStatus.SUPPORTED
        return ClaimStatus.UNVERIFIABLE

    def _unknown(self, claim: AtomicClaim, confidence: float, reason: str) -> ClaimScore:
        return ClaimScore(
            claim_id=claim.claim_id,
            role=claim.role,
            change_type=claim.change_type,
            status=ClaimStatus.UNVERIFIABLE,
            faithfulness=None,
            spatial_support=None,
            temporal_support=None,
            grounding_confidence=float(confidence),
            reason=reason,
        )

    @staticmethod
    def _temporal_masks(
        change_type: ChangeType,
        pre: np.ndarray,
        post: np.ndarray,
        evidence: GroundingEvidence,
    ) -> tuple[np.ndarray, np.ndarray, float]:
        if change_type == ChangeType.ADD:
            return post, pre, float(evidence.post_confidence)
        if change_type == ChangeType.REMOVE:
            return pre, post, float(evidence.pre_confidence)
        return (
            np.logical_or(pre, post),
            np.zeros_like(pre),
            float(max(evidence.pre_confidence, evidence.post_confidence)),
        )

    @staticmethod
    def _delta_mask(
        change_type: ChangeType,
        pre: np.ndarray,
        post: np.ndarray,
    ) -> np.ndarray:
        if change_type == ChangeType.ADD:
            return np.logical_and(post, np.logical_not(pre))
        if change_type == ChangeType.REMOVE:
            return np.logical_and(pre, np.logical_not(post))
        return np.logical_xor(pre, post)


@dataclass(frozen=True)
class LegacyMGAConfig:
    changed_weight: float = 0.7
    context_weight: float = 0.3


class LegacyMGAScorer:
    """A documented reconstruction of the original MGA v1 equations."""

    def __init__(self, config: LegacyMGAConfig | None = None) -> None:
        self.config = config or LegacyMGAConfig()

    def score(
        self,
        record: SampleRecord,
        change_mask: np.ndarray,
        evidence_by_claim: Mapping[str, GroundingEvidence],
    ) -> LegacyCaptionScore:
        change_mask = np.asarray(change_mask, dtype=bool)
        changed_values: list[float] = []
        context_values: list[float] = []
        for claim in record.claims:
            evidence = evidence_by_claim.get(claim.claim_id, GroundingEvidence())
            pre = as_bool_mask(evidence.pre_mask, change_mask.shape)
            post = as_bool_mask(evidence.post_mask, change_mask.shape)
            if claim.role == ClaimRole.CHANGED:
                raw = post if claim.change_type == ChangeType.ADD else pre
                if claim.change_type not in {ChangeType.ADD, ChangeType.REMOVE}:
                    raw = np.logical_or(pre, post)
                filtered = filter_intersecting_components(raw, change_mask)
                changed_values.append(intersection_over_union(filtered, change_mask))
            elif claim.role == ClaimRole.CONTEXT:
                raw = np.logical_or(pre, post)
                context_values.append(non_overlap_ratio(raw, change_mask))
            elif claim.role == ClaimRole.NO_CHANGE:
                changed_values.append(float(not change_mask.any()))

        # The original formulation assigns an empty entity group the maximum score.
        changed_score = _mean(changed_values) if changed_values else 1.0
        context_score = _mean(context_values) if context_values else 1.0
        denominator = self.config.changed_weight + self.config.context_weight
        mga = (
            self.config.changed_weight * changed_score + self.config.context_weight * context_score
        ) / denominator
        return LegacyCaptionScore(
            sample_id=record.sample_id,
            model=record.model,
            changed_score=float(changed_score),
            context_score=float(context_score),
            mga=float(mga),
        )


def _mean(values: Iterable[float | None]) -> float | None:
    concrete = [float(value) for value in values if value is not None]
    if not concrete:
        return None
    return float(sum(concrete) / len(concrete))


def _select_labels(mask: np.ndarray, labels: Iterable[int]) -> np.ndarray:
    selected_labels = tuple(int(value) for value in labels)
    if selected_labels and mask.dtype != np.bool_:
        return np.isin(mask, selected_labels)
    return np.asarray(mask, dtype=bool)


def _weighted_available(*items: tuple[float | None, float]) -> float | None:
    available = [(float(value), weight) for value, weight in items if value is not None]
    if not available:
        return None
    total_weight = sum(weight for _, weight in available)
    if total_weight <= 0:
        raise ValueError("At least one positive weight is required")
    return float(sum(value * weight for value, weight in available) / total_weight)
