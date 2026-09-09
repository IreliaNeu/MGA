"""Recoverable on-disk cache for expensive grounding calls."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from mga.grounding.base import Grounder
from mga.models import AtomicClaim, GroundingEvidence, SampleRecord


@dataclass
class EvidenceCache:
    root: Path

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def key(self, backend_id: str, record: SampleRecord, claim: AtomicClaim) -> str:
        payload = {
            "backend": backend_id,
            "sample_id": record.sample_id,
            "pre_image": record.pre_image,
            "post_image": record.post_image,
            "claim": claim.to_dict(),
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def load(self, key: str) -> GroundingEvidence | None:
        path = self._path(key)
        if not path.is_file():
            return None
        with np.load(path, allow_pickle=False) as value:
            metadata = json.loads(str(value["metadata_json"].item()))
            pre_present = bool(value["pre_present"].item())
            post_present = bool(value["post_present"].item())
            return GroundingEvidence(
                pre_mask=value["pre_mask"].astype(bool) if pre_present else None,
                post_mask=value["post_mask"].astype(bool) if post_present else None,
                pre_confidence=float(value["pre_confidence"].item()),
                post_confidence=float(value["post_confidence"].item()),
                backend=str(value["backend"].item()),
                metadata=metadata,
            )

    def save(self, key: str, evidence: GroundingEvidence) -> Path:
        path = self._path(key)
        empty = np.zeros((0, 0), dtype=bool)
        np.savez_compressed(
            path,
            pre_mask=empty
            if evidence.pre_mask is None
            else np.asarray(evidence.pre_mask, dtype=bool),
            post_mask=empty
            if evidence.post_mask is None
            else np.asarray(evidence.post_mask, dtype=bool),
            pre_present=np.asarray(evidence.pre_mask is not None),
            post_present=np.asarray(evidence.post_mask is not None),
            pre_confidence=np.asarray(evidence.pre_confidence),
            post_confidence=np.asarray(evidence.post_confidence),
            backend=np.asarray(evidence.backend),
            metadata_json=np.asarray(json.dumps(evidence.metadata, sort_keys=True)),
        )
        return path

    def _path(self, key: str) -> Path:
        directory = self.root / key[:2]
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{key}.npz"


@dataclass
class CachedGrounder:
    grounder: Grounder
    cache: EvidenceCache

    @property
    def backend_id(self) -> str:
        return self.grounder.backend_id

    def ground(self, record: SampleRecord, claim: AtomicClaim) -> GroundingEvidence:
        key = self.cache.key(self.backend_id, record, claim)
        cached = self.cache.load(key)
        if cached is not None:
            cached.metadata = {**cached.metadata, "cache_hit": True}
            return cached
        evidence = self.grounder.ground(record, claim)
        evidence.metadata = {**evidence.metadata, "cache_hit": False}
        self.cache.save(key, evidence)
        return evidence
