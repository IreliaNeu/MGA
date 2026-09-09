"""Native SegEarth-OV3/SAM 3 pixel-mask grounding backend.

The backend deliberately uses the official SegEarth-OV3 implementation from a
separate checkout.  Heavy dependencies are imported lazily so the regular MGA
CPU environment remains usable.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from mga.grounding.query_expansion import expand_grounding_queries
from mga.models import AtomicClaim, GroundingEvidence, SampleRecord


@dataclass(frozen=True)
class EntitySegmentation:
    """Pixel mask and diagnostics for one entity query."""

    mask: np.ndarray
    confidence: float
    queries: tuple[str, ...]
    presence_scores: tuple[float, ...]
    instance_count: int


@dataclass
class SegEarthOV3Grounder:
    """Ground entities with the native SegEarth-OV3 dual-head fusion pipeline."""

    vendor_root: str = "/root/autodl-tmp/third_party/SegEarth-OV-3"
    checkpoint_path: str | None = None
    device: str = "cuda"
    confidence_threshold: float = 0.10
    logit_threshold: float = 0.10
    query_expansion: str = "remote-sensing"
    background_prompt: str = "background"
    use_semantic_head: bool = True
    use_instance_head: bool = True
    use_presence_score: bool = True
    _torch: Any = field(init=False, repr=False)
    _functional: Any = field(init=False, repr=False)
    _processor: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        vendor_root = Path(self.vendor_root).expanduser().resolve()
        checkpoint = (
            Path(self.checkpoint_path).expanduser().resolve()
            if self.checkpoint_path
            else vendor_root / "weights" / "sam3" / "sam3.pt"
        )
        bpe_path = vendor_root / "sam3" / "assets" / "bpe_simple_vocab_16e6.txt.gz"
        for path, label in (
            (vendor_root, "SegEarth-OV3 checkout"),
            (checkpoint, "SAM 3 checkpoint"),
            (bpe_path, "SAM 3 tokenizer vocabulary"),
        ):
            if not path.exists():
                raise FileNotFoundError(f"Missing {label}: {path}")

        try:
            import torch
            import torch.nn.functional as functional
        except ImportError as exc:
            raise RuntimeError("Activate the dedicated segearth-ov3 environment") from exc

        vendor_text = str(vendor_root)
        if vendor_text not in sys.path:
            sys.path.insert(0, vendor_text)
        try:
            from sam3 import build_sam3_image_model
            from sam3.model.sam3_image_processor import Sam3Processor
        except ImportError as exc:
            raise RuntimeError(f"Cannot import SegEarth-OV3 from {vendor_root}") from exc

        self._torch = torch
        self._functional = functional
        model = build_sam3_image_model(
            bpe_path=str(bpe_path),
            checkpoint_path=str(checkpoint),
            device=self.device,
        )
        model.eval()
        self._processor = Sam3Processor(
            model,
            confidence_threshold=self.confidence_threshold,
            device=self.device,
        )
        self.vendor_root = str(vendor_root)
        self.checkpoint_path = str(checkpoint)

    @property
    def backend_id(self) -> str:
        checkpoint = Path(self.checkpoint_path or "sam3.pt").name
        return (
            f"segearth-ov3-native:{checkpoint}:confidence={self.confidence_threshold}:"
            f"logit={self.logit_threshold}:expansion={self.query_expansion}"
        )

    def ground(self, record: SampleRecord, claim: AtomicClaim) -> GroundingEvidence:
        pre = self.segment_queries(record.pre_image, (claim.entity,))[claim.entity]
        post = self.segment_queries(record.post_image, (claim.entity,))[claim.entity]
        return GroundingEvidence(
            pre_mask=pre.mask,
            post_mask=post.mask,
            pre_confidence=pre.confidence,
            post_confidence=post.confidence,
            backend=self.backend_id,
            metadata={
                "query": claim.entity,
                "expanded_queries": list(pre.queries),
                "pre_instances": pre.instance_count,
                "post_instances": post.instance_count,
                "pre_presence_scores": list(pre.presence_scores),
                "post_presence_scores": list(post.presence_scores),
            },
        )

    def segment_queries(
        self, image_path: str | Path, entities: Sequence[str]
    ) -> dict[str, EntitySegmentation]:
        """Encode one image once and segment all requested entities."""

        normalized_entities = tuple(
            dict.fromkeys(item.strip() for item in entities if item.strip())
        )
        if not normalized_entities:
            raise ValueError("At least one non-empty entity is required")

        path = Path(image_path).expanduser().resolve()
        with Image.open(path) as source:
            image = source.convert("RGB")
        width, height = image.size

        entity_queries = {
            entity: expand_grounding_queries(entity, self.query_expansion)
            for entity in normalized_entities
        }
        prompts = tuple(
            dict.fromkeys(
                (self.background_prompt,)
                + tuple(query for queries in entity_queries.values() for query in queries)
            )
        )

        prompt_outputs: dict[str, tuple[Any, float, int]] = {}
        torch = self._torch
        with torch.inference_mode(), torch.autocast(
            device_type="cuda", dtype=torch.bfloat16, enabled=self.device.startswith("cuda")
        ):
            state = self._processor.set_image(image)
            for prompt in prompts:
                self._processor.reset_all_prompts(state)
                state = self._processor.set_text_prompt(state=state, prompt=prompt)
                prompt_outputs[prompt] = self._fuse_prompt_outputs(state, height, width)

        background_logits = prompt_outputs[self.background_prompt][0]
        results: dict[str, EntitySegmentation] = {}
        for entity, queries in entity_queries.items():
            logits = torch.stack([prompt_outputs[query][0] for query in queries]).amax(0)
            mask = torch.logical_and(
                logits > background_logits,
                logits >= self.logit_threshold,
            )
            presence_scores = tuple(prompt_outputs[query][1] for query in queries)
            results[entity] = EntitySegmentation(
                mask=mask.detach().cpu().numpy().astype(bool, copy=False),
                confidence=max(presence_scores, default=0.0),
                queries=queries,
                presence_scores=presence_scores,
                instance_count=sum(prompt_outputs[query][2] for query in queries),
            )
        return results

    def _fuse_prompt_outputs(
        self, state: dict[str, Any], height: int, width: int
    ) -> tuple[Any, float, int]:
        torch = self._torch
        logits = torch.zeros((height, width), device=self.device, dtype=torch.float32)
        instance_count = 0

        if self.use_instance_head:
            instance_logits = state.get("masks_logits")
            object_scores = state.get("object_score")
            if instance_logits is not None and object_scores is not None:
                instance_count = int(instance_logits.shape[0])
                for item, score in zip(instance_logits, object_scores, strict=False):
                    resized = self._resize_logits(item, height, width)
                    logits = torch.maximum(logits, resized.float() * score.float())

        if self.use_semantic_head and state.get("semantic_mask_logits") is not None:
            semantic = self._resize_logits(state["semantic_mask_logits"], height, width)
            logits = torch.maximum(logits, semantic.float())

        presence = self._scalar(state.get("presence_score"), default=1.0)
        if self.use_presence_score:
            logits = logits * presence
        return logits, presence, instance_count

    def _resize_logits(self, value: Any, height: int, width: int) -> Any:
        tensor = value.squeeze()
        if tensor.ndim != 2:
            shape = tuple(tensor.shape)
            raise ValueError(f"Expected two-dimensional mask logits, got shape {shape}")
        if tuple(tensor.shape) == (height, width):
            return tensor
        return self._functional.interpolate(
            tensor[None, None].float(),
            size=(height, width),
            mode="bilinear",
            align_corners=False,
        )[0, 0]

    @staticmethod
    def _scalar(value: Any, default: float) -> float:
        if value is None:
            return default
        if hasattr(value, "detach"):
            value = value.detach().float().max().cpu().item()
        return float(value)
