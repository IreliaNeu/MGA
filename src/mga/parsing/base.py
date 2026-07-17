"""Parser protocol."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from mga.models import AtomicClaim


class ClaimParser(Protocol):
    def parse(self, caption: str) -> Sequence[AtomicClaim]:
        """Convert one caption into independently verifiable claims."""
