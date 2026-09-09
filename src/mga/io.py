"""Manifest and result I/O with strict, line-addressable validation."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

from mga.models import SampleRecord


def read_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}: {exc}") from exc


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_manifest(path: str | Path, resolve_paths: bool = True) -> list[SampleRecord]:
    path = Path(path)
    base = path.resolve().parent
    records: list[SampleRecord] = []
    seen: set[tuple[str, str]] = set()

    for line_number, item in enumerate(read_jsonl(path), start=1):
        try:
            record = SampleRecord.from_dict(item)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid sample at {path}:{line_number}: {exc}") from exc

        key = (record.sample_id, record.model)
        if key in seen:
            raise ValueError(f"Duplicate sample/model pair at {path}:{line_number}: {key}")
        seen.add(key)

        if resolve_paths:
            record = replace(
                record,
                pre_image=str(_resolve(base, record.pre_image)),
                post_image=str(_resolve(base, record.post_image)),
                change_mask=str(_resolve(base, record.change_mask)),
            )
        records.append(record)

    if not records:
        raise ValueError(f"Manifest is empty: {path}")
    return records


def validate_files(records: Iterable[SampleRecord]) -> list[str]:
    errors: list[str] = []
    for record in records:
        for field_name in ("pre_image", "post_image", "change_mask"):
            value = Path(getattr(record, field_name))
            if not value.is_file():
                errors.append(f"{record.sample_id}/{record.model}: missing {field_name}: {value}")
    return errors


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()
