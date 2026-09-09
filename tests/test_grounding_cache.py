from __future__ import annotations

from pathlib import Path

import numpy as np

from mga.grounding.cache import EvidenceCache
from mga.models import AtomicClaim, ChangeType, ClaimRole, GroundingEvidence, SampleRecord


def test_evidence_cache_round_trip(tmp_path: Path) -> None:
    cache = EvidenceCache(tmp_path)
    claim = AtomicClaim("c001", "a building appears", "building", ClaimRole.CHANGED, ChangeType.ADD)
    record = SampleRecord("sample", "model", "caption", "a.png", "b.png", "mask.png")
    evidence = GroundingEvidence(
        pre_mask=np.zeros((3, 3), dtype=bool),
        post_mask=np.eye(3, dtype=bool),
        pre_confidence=0.1,
        post_confidence=0.9,
        backend="unit-test",
        metadata={"boxes": 1},
    )
    key = cache.key("unit-test", record, claim)
    cache.save(key, evidence)

    restored = cache.load(key)

    assert restored is not None
    assert np.array_equal(restored.post_mask, evidence.post_mask)
    assert restored.post_confidence == 0.9
    assert restored.metadata == {"boxes": 1}
