"""End-to-end claim parsing, grounding, caching, and scoring orchestration."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import replace

from mga.grounding.base import Grounder
from mga.mask_ops import load_label_mask, select_change_mask
from mga.models import SampleRecord
from mga.parsing.base import ClaimParser
from mga.scoring import LegacyMGAScorer, MGAV2Scorer


def enrich_claims(
    records: Iterable[SampleRecord], parser: ClaimParser, force: bool = False
) -> Iterator[SampleRecord]:
    for record in records:
        if record.claims and not force:
            yield record
            continue
        claims = tuple(parser.parse(record.caption))
        if not claims:
            raise ValueError(
                f"No claims extracted for {record.sample_id}/{record.model}. "
                "Provide precomputed claims or use a stronger parser backend."
            )
        yield replace(record, claims=claims)


def score_records(
    records: Iterable[SampleRecord],
    grounder: Grounder,
    method: str = "v2",
) -> Iterator[dict]:
    scorer = MGAV2Scorer() if method == "v2" else LegacyMGAScorer()
    for record in records:
        label_mask = load_label_mask(record.change_mask)
        labels = tuple(int(value) for value in record.metadata.get("mask_labels", ()))
        change_mask = select_change_mask(label_mask, labels)
        evidence = {claim.claim_id: grounder.ground(record, claim) for claim in record.claims}
        score = scorer.score(record, change_mask, evidence)
        yield {
            "sample_id": record.sample_id,
            "model": record.model,
            "dataset": record.dataset,
            "caption": record.caption,
            "claims": [claim.to_dict() for claim in record.claims],
            "score": score.to_dict(),
        }
