"""Grounding backend protocol."""

from __future__ import annotations

from typing import Protocol

from mga.models import AtomicClaim, GroundingEvidence, SampleRecord


class Grounder(Protocol):
    @property
    def backend_id(self) -> str:
        """Stable backend identifier included in cache keys."""

    def ground(self, record: SampleRecord, claim: AtomicClaim) -> GroundingEvidence:
        """Ground an entity independently in both temporal images."""
