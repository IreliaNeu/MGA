"""Experimental Grounding DINO backend with controlled query expansion."""

from __future__ import annotations

from dataclasses import dataclass

from mga.grounding.hf_dino import HFGroundingDinoGrounder
from mga.grounding.query_expansion import expand_grounding_queries, format_grounding_query
from mga.models import AtomicClaim, GroundingEvidence, SampleRecord


@dataclass
class ExpandedHFGroundingDinoGrounder(HFGroundingDinoGrounder):
    query_expansion: str = "remote-sensing"

    @property
    def backend_id(self) -> str:
        return (
            f"hf-dino-box:{self.model_id}:box={self.box_threshold}:"
            f"text={self.text_threshold}:query-expansion={self.query_expansion}"
        )

    def ground(self, record: SampleRecord, claim: AtomicClaim) -> GroundingEvidence:
        queries = expand_grounding_queries(claim.entity, self.query_expansion)
        prompt = format_grounding_query(queries)
        pre_mask, pre_confidence, pre_count = self._ground_image(record.pre_image, prompt)
        post_mask, post_confidence, post_count = self._ground_image(record.post_image, prompt)
        return GroundingEvidence(
            pre_mask=pre_mask,
            post_mask=post_mask,
            pre_confidence=pre_confidence,
            post_confidence=post_confidence,
            backend=self.backend_id,
            metadata={
                "pre_boxes": pre_count,
                "post_boxes": post_count,
                "entity": claim.entity,
                "queries": list(queries),
                "prompt": prompt,
                "query_expansion": self.query_expansion,
            },
        )
