"""Mask-Guided Alignment evaluation package."""

from mga.models import (
    AtomicClaim,
    CaptionScore,
    ChangeType,
    ClaimRole,
    ClaimStatus,
    EvidenceMode,
)
from mga.scoring import LegacyMGAScorer, MGAV2Config, MGAV2Scorer

__all__ = [
    "AtomicClaim",
    "CaptionScore",
    "ChangeType",
    "ClaimRole",
    "ClaimStatus",
    "EvidenceMode",
    "LegacyMGAScorer",
    "MGAV2Config",
    "MGAV2Scorer",
]

__version__ = "0.1.0"
