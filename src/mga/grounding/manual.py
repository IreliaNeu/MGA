"""Grounder for precomputed masks referenced in claim metadata."""

from __future__ import annotations

from pathlib import Path

from mga.mask_ops import load_label_mask
from mga.models import AtomicClaim, GroundingEvidence, SampleRecord


class MetadataMaskGrounder:
    """Load evidence paths from claim.metadata for tests and offline experiments.

    Expected metadata keys are ``pre_support_mask``, ``post_support_mask``,
    ``pre_confidence`` and ``post_confidence``. Relative paths are resolved from
    ``base_dir``.
    """

    def __init__(self, base_dir: str | Path = ".") -> None:
        self.base_dir = Path(base_dir)

    @property
    def backend_id(self) -> str:
        return "metadata-mask-v1"

    def ground(self, record: SampleRecord, claim: AtomicClaim) -> GroundingEvidence:
        del record
        pre_path = claim.metadata.get("pre_support_mask")
        post_path = claim.metadata.get("post_support_mask")
        return GroundingEvidence(
            pre_mask=self._load(pre_path),
            post_mask=self._load(post_path),
            pre_confidence=float(claim.metadata.get("pre_confidence", 1.0 if pre_path else 0.0)),
            post_confidence=float(claim.metadata.get("post_confidence", 1.0 if post_path else 0.0)),
            backend=self.backend_id,
        )

    def _load(self, value: str | None):
        if not value:
            return None
        path = Path(value)
        if not path.is_absolute():
            path = self.base_dir / path
        return load_label_mask(path) != 0
