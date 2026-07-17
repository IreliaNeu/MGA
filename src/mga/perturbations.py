"""Controlled caption perturbations for metric monotonicity tests."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import replace

from mga.models import SampleRecord

DIRECTION_SWAPS = (
    ("appears", "disappears"),
    ("added", "removed"),
    ("built", "demolished"),
    ("constructed", "removed"),
    ("new", "removed"),
)

LOCATION_SWAPS = (
    ("left", "right"),
    ("upper", "lower"),
    ("top", "bottom"),
)


def make_perturbations(
    records: Iterable[SampleRecord],
    injected_entity: str = "a new building appears in the center",
) -> list[SampleRecord]:
    variants: list[SampleRecord] = []
    for record in records:
        variants.append(
            _variant(record, "entity_injection", f"{record.caption} {injected_entity}.")
        )
        direction = _swap_first(record.caption, DIRECTION_SWAPS)
        if direction != record.caption:
            variants.append(_variant(record, "direction_swap", direction))
        location = _swap_first(record.caption, LOCATION_SWAPS)
        if location != record.caption:
            variants.append(_variant(record, "location_swap", location))
    return variants


def _variant(record: SampleRecord, name: str, caption: str) -> SampleRecord:
    metadata = {**record.metadata, "source_sample_id": record.sample_id, "perturbation": name}
    return replace(
        record,
        sample_id=f"{record.sample_id}::{name}",
        model=f"{record.model}+{name}",
        caption=caption,
        claims=(),
        metadata=metadata,
    )


def _swap_first(text: str, swaps: tuple[tuple[str, str], ...]) -> str:
    for left, right in swaps:
        pattern_left = re.compile(rf"\b{re.escape(left)}\b", re.IGNORECASE)
        if pattern_left.search(text):
            return pattern_left.sub(right, text, count=1)
        pattern_right = re.compile(rf"\b{re.escape(right)}\b", re.IGNORECASE)
        if pattern_right.search(text):
            return pattern_right.sub(left, text, count=1)
    return text
