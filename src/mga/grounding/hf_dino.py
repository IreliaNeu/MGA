"""Lazy Hugging Face Grounding DINO box-mask backend.

This first GPU backend intentionally rasterizes detected boxes. A SAM refinement
adapter can be added without changing the scorer or manifest contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from mga.models import AtomicClaim, GroundingEvidence, SampleRecord


@dataclass
class HFGroundingDinoGrounder:
    model_id: str = "IDEA-Research/grounding-dino-tiny"
    device: str = "cuda"
    box_threshold: float = 0.30
    text_threshold: float = 0.25
    _processor: Any = field(init=False, repr=False)
    _model: Any = field(init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            import torch
            from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
        except ImportError as exc:
            raise RuntimeError("Install GPU dependencies with: pip install -e '.[gpu]'") from exc
        self._torch = torch
        self._processor = AutoProcessor.from_pretrained(self.model_id)
        self._model = AutoModelForZeroShotObjectDetection.from_pretrained(self.model_id)
        self._model.to(self.device).eval()

    @property
    def backend_id(self) -> str:
        return f"hf-dino-box:{self.model_id}:box={self.box_threshold}:text={self.text_threshold}"

    def ground(self, record: SampleRecord, claim: AtomicClaim) -> GroundingEvidence:
        pre_mask, pre_confidence, pre_count = self._ground_image(record.pre_image, claim.entity)
        post_mask, post_confidence, post_count = self._ground_image(record.post_image, claim.entity)
        return GroundingEvidence(
            pre_mask=pre_mask,
            post_mask=post_mask,
            pre_confidence=pre_confidence,
            post_confidence=post_confidence,
            backend=self.backend_id,
            metadata={"pre_boxes": pre_count, "post_boxes": post_count, "query": claim.entity},
        )

    def _ground_image(self, image_path: str, query: str) -> tuple[np.ndarray, float, int]:
        with Image.open(Path(image_path)) as source:
            image = source.convert("RGB")
        inputs = self._processor(images=image, text=query, return_tensors="pt")
        inputs = {key: value.to(self.device) for key, value in inputs.items()}
        with self._torch.no_grad():
            outputs = self._model(**inputs)

        kwargs = {
            "target_sizes": [image.size[::-1]],
            "box_threshold": self.box_threshold,
            "text_threshold": self.text_threshold,
        }
        try:
            results = self._processor.post_process_grounded_object_detection(
                outputs, inputs.get("input_ids"), **kwargs
            )
        except TypeError:
            # Compatibility path for transformers releases using a single threshold.
            results = self._processor.post_process_grounded_object_detection(
                outputs,
                inputs.get("input_ids"),
                target_sizes=kwargs["target_sizes"],
                threshold=self.box_threshold,
            )

        result = results[0]
        height, width = image.size[1], image.size[0]
        mask = np.zeros((height, width), dtype=bool)
        boxes = result.get("boxes", [])
        scores = result.get("scores", [])
        for box in boxes:
            x_min, y_min, x_max, y_max = [int(round(float(value))) for value in box]
            x_min, x_max = sorted((max(0, x_min), min(width, x_max)))
            y_min, y_max = sorted((max(0, y_min), min(height, y_max)))
            mask[y_min:y_max, x_min:x_max] = True
        confidence = max((float(score) for score in scores), default=0.0)
        return mask, confidence, len(boxes)
