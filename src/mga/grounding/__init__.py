"""Pluggable entity-grounding backends and persistent evidence cache."""

from mga.grounding.base import Grounder
from mga.grounding.cache import CachedGrounder, EvidenceCache
from mga.grounding.hf_dino import HFGroundingDinoGrounder
from mga.grounding.manual import MetadataMaskGrounder

__all__ = [
    "CachedGrounder",
    "EvidenceCache",
    "Grounder",
    "HFGroundingDinoGrounder",
    "MetadataMaskGrounder",
]
