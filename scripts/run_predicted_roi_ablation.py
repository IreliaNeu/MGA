"""Compare oracle, predicted, feature-difference, and no-ROI MGA gating.

The experiment holds entity evidence fixed and only changes the spatial change
gate.  It is intended to expose the oracle gap created by the GT change ROI in
earlier OpenVocabOnly experiments.  ``predicted_cd_roi`` strictly requires an
independent external detector; RGB feature difference remains a separate weak
baseline and is never relabelled as a learned prediction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from mga.evidence_routing import balanced_accuracy, binary_auc
from mga.mask_ops import load_label_mask
from mga.predicted_roi import (
    ROI_MODES,
    ROIResult,
    build_roi,
    relation_mask,
    roi_quality,
    soft_relation_score,
)
from mga.semantic_change import load_label_ids

ENTITY_EVIDENCE_MODES = ("open_vocab", "hybrid", "gt")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=Path, required=True)
    cache_group = parser.add_mutually_exclusive_group(required=True)
    cache_group.add_argument(
        "--cache-dir",
        type=Path,
        help="Directory of per-scene SegEarth NPZ caches (SECOND protocol).",
    )
    cache_group.add_argument(
        "--entity-cache-jsonl",
        type=Path,
        help="SegEarth segmentations.jsonl with A/B mask_path entries (LEVIR protocol).",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--class-map",
        required=True,
        help="JSON string or path mapping class IDs to canonical entity names.",
    )
    parser.add_argument(
        "--entity-evidence-modes",
        default="open_vocab,hybrid",
        help="Comma-separated subset of open_vocab,hybrid,gt.",
    )
    parser.add_argument(
        "--hidden-entities",
        default="",
        help="Comma-separated classes routed to open vocabulary in Hybrid.",
    )
    parser.add_argument(
        "--roi-modes",
        default=",".join(ROI_MODES),
        help="Comma-separated ROI modes.",
    )
    parser.add_argument(
        "--external-roi-manifest",
        type=Path,
        help=(
            "Optional JSONL with sample_id and roi_path (or predicted_roi, "
            "change_probability, prediction, change_mask)."
        ),
    )
    parser.add_argument("--predicted-roi-field")
    parser.add_argument("--predicted-array-key")
    parser.add_argument(
        "--changeformer-root",
        type=Path,
        help="Official ChangeFormer checkout used to generate missing predicted ROIs.",
    )
    parser.add_argument(
        "--changeformer-checkpoint",
        type=Path,
        help="Official ChangeFormerV6 LEVIR best_ckpt.pt.",
    )
    parser.add_argument("--changeformer-device", default="cuda")
    parser.add_argument("--changeformer-image-size", type=int, default=256)
    parser.add_argument("--changeformer-embed-dim", type=int, default=256)
    parser.add_argument(
        "--mci-root",
        type=Path,
        help="Official Change-Agent checkout used for its MCI change head.",
    )
    parser.add_argument(
        "--mci-checkpoint",
        type=Path,
        help="Official Change-Agent MCI_model.pth.",
    )
    parser.add_argument("--mci-device", default="cuda")
    parser.add_argument(
        "--threshold-method",
        choices=("otsu", "quantile", "fixed"),
        default="otsu",
    )
    parser.add_argument("--threshold-quantile", type=float, default=0.90)
    parser.add_argument("--fixed-threshold", type=float, default=0.50)
    parser.add_argument("--gate-floor", type=float, default=0.10)
    parser.add_argument("--blur-radius", type=float, default=1.0)
    parser.add_argument("--min-ov-confidence", type=float, default=0.10)
    parser.add_argument("--max-scenes", type=int, default=0)
    parser.add_argument("--save-roi-maps", action="store_true")
    parser.add_argument("--overview-limit", type=int, default=16)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def parse_csv_subset(value: str, allowed: tuple[str, ...], label: str) -> tuple[str, ...]:
    selected = tuple(item.strip() for item in value.split(",") if item.strip())
    unknown = sorted(set(selected) - set(allowed))
    if unknown:
        raise ValueError(f"Unknown {label}: {', '.join(unknown)}")
    if not selected:
        raise ValueError(f"At least one {label} is required")
    return selected


def load_class_map(value: str) -> dict[int, str]:
    path = Path(value)
    if path.is_file():
        value = path.read_text(encoding="utf-8")
    return {int(key): str(name) for key, name in json.loads(value).items()}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ChangeFormerPredictor:
    """Minimal official ChangeFormerV6 inference adapter without dataset rewrites."""

    def __init__(
        self,
        *,
        root: Path,
        checkpoint: Path,
        device: str,
        image_size: int,
        embed_dim: int,
    ) -> None:
        if not root.is_dir():
            raise FileNotFoundError(f"Missing ChangeFormer checkout: {root}")
        if not checkpoint.is_file():
            raise FileNotFoundError(f"Missing ChangeFormer checkpoint: {checkpoint}")
        import torch

        root_value = str(root.resolve())
        if root_value not in sys.path:
            sys.path.insert(0, root_value)
        from models.ChangeFormer import ChangeFormerV6

        self.torch = torch
        self.device = torch.device(device)
        self.image_size = int(image_size)
        self.model = ChangeFormerV6(embed_dim=embed_dim)
        checkpoint_value = torch.load(
            checkpoint,
            map_location="cpu",
            weights_only=False,
        )
        state = checkpoint_value.get("model_G_state_dict", checkpoint_value)
        state = {
            key.removeprefix("module."): value for key, value in state.items()
        }
        self.model.load_state_dict(state, strict=True)
        self.model.to(self.device).eval()
        try:
            commit = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            commit = "unknown"
        self.metadata = {
            "backend": "ChangeFormerV6",
            "training_dataset": "LEVIR-CD",
            "repo": str(root),
            "repo_commit": commit,
            "checkpoint": str(checkpoint),
            "checkpoint_sha256": sha256_file(checkpoint),
            "image_size": self.image_size,
            "embed_dim": embed_dim,
            "device": str(self.device),
            "torch_version": torch.__version__,
        }

    def predict(
        self,
        pre_image: str | Path,
        post_image: str | Path,
        *,
        shape: tuple[int, int],
    ) -> np.ndarray:
        torch = self.torch

        def image_tensor(path: str | Path):
            with Image.open(path) as image:
                image = image.convert("RGB").resize(
                    (self.image_size, self.image_size),
                    resample=Image.Resampling.BILINEAR,
                )
                array = np.asarray(image, dtype=np.float32) / 127.5 - 1.0
            return torch.from_numpy(array.transpose(2, 0, 1)).unsqueeze(0)

        pre = image_tensor(pre_image).to(self.device)
        post = image_tensor(post_image).to(self.device)
        with torch.inference_mode():
            output = self.model(pre, post)
            logits = output[-1] if isinstance(output, (list, tuple)) else output
            probability = torch.softmax(logits.float(), dim=1)[:, 1:2]
            probability = torch.nn.functional.interpolate(
                probability,
                size=shape,
                mode="bilinear",
                align_corners=False,
            )
        return probability[0, 0].cpu().numpy().astype(np.float32, copy=False)


class MCIChangePredictor:
    """Minimal adapter for the road/building change head in Change-Agent MCI."""

    def __init__(self, *, root: Path, checkpoint: Path, device: str) -> None:
        if not root.is_dir():
            raise FileNotFoundError(f"Missing Change-Agent checkout: {root}")
        if not checkpoint.is_file():
            raise FileNotFoundError(f"Missing MCI checkpoint: {checkpoint}")
        import logging
        import types

        import torch

        if not str(device).startswith("cuda"):
            raise ValueError("The official MCI positional embedding uses CUDA explicitly")
        mmseg = types.ModuleType("mmseg")
        mmseg_utils = types.ModuleType("mmseg.utils")
        mmseg_utils.get_root_logger = lambda *args, **kwargs: logging.getLogger("mci")
        mmseg.utils = mmseg_utils
        sys.modules["mmseg"] = mmseg
        sys.modules["mmseg.utils"] = mmseg_utils
        mmcv_runner = types.ModuleType("mmcv.runner")
        mmcv_runner.load_checkpoint = lambda *args, **kwargs: None
        sys.modules["mmcv.runner"] = mmcv_runner

        multi_change_root = root / "Multi_change"
        root_value = str(multi_change_root.resolve())
        if root_value not in sys.path:
            sys.path.insert(0, root_value)
        from model.model_encoder_att import AttentiveEncoder, Encoder

        self.torch = torch
        self.device = torch.device(device)
        self.encoder = Encoder("segformer-mit_b1")
        self.encoder_trans = AttentiveEncoder(
            train_stage=None,
            n_layers=3,
            feature_size=[16, 16, 512],
            heads=8,
            dropout=0.1,
        )
        checkpoint_value = torch.load(
            checkpoint,
            map_location="cpu",
            weights_only=False,
        )
        self.encoder.load_state_dict(checkpoint_value["encoder_dict"], strict=True)
        self.encoder_trans.load_state_dict(
            checkpoint_value["encoder_trans_dict"],
            strict=False,
        )
        self.encoder.to(self.device).eval()
        self.encoder_trans.to(self.device).eval()
        self.mean = np.asarray([0.39073, 0.38623, 0.32989], dtype=np.float32)
        self.std = np.asarray([0.15329, 0.14628, 0.13648], dtype=np.float32)
        try:
            commit = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            commit = "unknown"
        self.metadata = {
            "backend": "Change-Agent-MCI",
            "training_dataset": "LEVIR-MCI",
            "classes": ["background", "road", "building"],
            "repo": str(root),
            "repo_commit": commit,
            "checkpoint": str(checkpoint),
            "checkpoint_sha256": sha256_file(checkpoint),
            "image_size": 256,
            "device": str(self.device),
            "torch_version": torch.__version__,
        }

    def predict(
        self,
        pre_image: str | Path,
        post_image: str | Path,
        *,
        shape: tuple[int, int],
    ) -> np.ndarray:
        torch = self.torch

        def image_tensor(path: str | Path):
            with Image.open(path) as image:
                image = image.convert("RGB").resize(
                    (256, 256),
                    resample=Image.Resampling.BILINEAR,
                )
                array = np.asarray(image, dtype=np.float32) / 255.0
            array = (array - self.mean) / self.std
            return torch.from_numpy(array.transpose(2, 0, 1)).unsqueeze(0)

        pre = image_tensor(pre_image).to(self.device)
        post = image_tensor(post_image).to(self.device)
        with torch.inference_mode():
            feat_pre, feat_post = self.encoder(pre, post)
            _feat_pre, _feat_post, logits = self.encoder_trans(feat_pre, feat_post)
            probability = 1.0 - torch.softmax(logits.float(), dim=1)[:, 0:1]
            probability = torch.nn.functional.interpolate(
                probability,
                size=shape,
                mode="bilinear",
                align_corners=False,
            )
        return probability[0, 0].cpu().numpy().astype(np.float32, copy=False)


def load_open_vocab(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing entity evidence cache: {path}")
    with np.load(path, allow_pickle=False) as values:
        entities = json.loads(str(values["entities_json"].item()))
        return {
            entity: {
                "pre_mask": values["pre_masks"][index].astype(bool),
                "post_mask": values["post_masks"][index].astype(bool),
                "pre_confidence": float(values["pre_confidences"][index]),
                "post_confidence": float(values["post_confidences"][index]),
            }
            for index, entity in enumerate(entities)
        }


def load_segmentation_index(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    return {str(row["sample_id"]): row for row in read_jsonl(path)}


def load_open_vocab_from_segmentation(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    phases = {}
    for phase in ("A", "B"):
        phases[phase] = {str(item["entity"]): item for item in row.get(phase, [])}
    entities = sorted(set(phases["A"]) | set(phases["B"]))
    result = {}
    for entity in entities:
        pre_item = phases["A"].get(entity)
        post_item = phases["B"].get(entity)
        if pre_item is None and post_item is None:
            continue
        exemplar = pre_item or post_item
        assert exemplar is not None
        exemplar_mask = load_label_mask(exemplar["mask_path"]) != 0
        pre_mask = (
            load_label_mask(pre_item["mask_path"]) != 0
            if pre_item is not None
            else np.zeros_like(exemplar_mask)
        )
        post_mask = (
            load_label_mask(post_item["mask_path"]) != 0
            if post_item is not None
            else np.zeros_like(exemplar_mask)
        )
        result[entity] = {
            "pre_mask": pre_mask,
            "post_mask": post_mask,
            "pre_confidence": float(pre_item.get("confidence", 0.0)) if pre_item else 0.0,
            "post_confidence": (
                float(post_item.get("confidence", 0.0)) if post_item else 0.0
            ),
        }
    return result


def load_external_roi_index(
    path: Path | None,
    *,
    field: str | None,
) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    candidates = tuple(
        item
        for item in (
            field,
            "roi_path",
            "predicted_roi",
            "change_probability",
            "prediction",
            "change_mask",
        )
        if item
    )
    result: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(path):
        sample_id = str(row["sample_id"])
        selected = next((key for key in candidates if row.get(key)), None)
        if selected is None:
            raise ValueError(
                f"No predicted ROI path in manifest row {sample_id}; checked "
                f"{', '.join(candidates)}"
            )
        roi_path = Path(str(row[selected]))
        if not roi_path.is_absolute():
            roi_path = (path.parent / roi_path).resolve()
        result[sample_id] = {
            "path": roi_path,
            "array_key": row.get("array_key"),
            "field": selected,
        }
    return result


def claim_pair(
    item: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    claims = item.get("claims") or []
    if len(claims) < 2:
        return None
    source = next(
        (claim for claim in claims if claim.get("change_type") == "remove"),
        claims[0],
    )
    target = next(
        (claim for claim in claims if claim.get("change_type") == "add"),
        claims[-1],
    )
    return source, target


def entity_masks(
    entity: str,
    *,
    evidence_mode: str,
    role: str,
    semantic_pre: np.ndarray | None,
    semantic_post: np.ndarray | None,
    class_ids: dict[str, int],
    visible_entities: set[str],
    open_vocab: dict[str, dict[str, Any]],
    min_ov_confidence: float,
) -> tuple[np.ndarray, np.ndarray] | None:
    use_gt = evidence_mode == "gt" or (
        evidence_mode == "hybrid" and entity in visible_entities
    )
    if use_gt:
        if semantic_pre is None or semantic_post is None or entity not in class_ids:
            return None
        class_id = class_ids[entity]
        return semantic_pre == class_id, semantic_post == class_id
    values = open_vocab.get(entity)
    if values is None:
        return None
    required_mask = values["pre_mask"] if role == "source" else values["post_mask"]
    required_confidence = (
        values["pre_confidence"] if role == "source" else values["post_confidence"]
    )
    if required_confidence < min_ov_confidence or not required_mask.any():
        return None
    return values["pre_mask"], values["post_mask"]


def build_scene_rois(
    *,
    modes: tuple[str, ...],
    representative: dict[str, Any],
    oracle_change: np.ndarray,
    external: dict[str, Any] | None,
    args: argparse.Namespace,
) -> dict[str, ROIResult]:
    result = {}
    for mode in modes:
        result[mode] = build_roi(
            mode,
            shape=oracle_change.shape,
            pre_image=representative["pre_image"],
            post_image=representative["post_image"],
            oracle_change=oracle_change,
            predicted_path=external["path"] if external else None,
            predicted_array_key=(
                args.predicted_array_key
                or (external.get("array_key") if external else None)
            ),
            threshold_method=args.threshold_method,
            threshold_quantile=args.threshold_quantile,
            fixed_threshold=args.fixed_threshold,
            gate_floor=args.gate_floor,
            blur_radius=args.blur_radius,
        )
    return result


def metrics(
    values: list[tuple[bool | None, float | None]],
) -> dict[str, float | int]:
    labeled = [(bool(label), score) for label, score in values if label is not None]
    available = [
        (label, float(score)) for label, score in labeled if score is not None
    ]
    neutral = [
        (label, 0.5 if score is None else float(score))
        for label, score in labeled
    ]
    positives = [score for label, score in available if label]
    negatives = [score for label, score in available if not label]
    predicted_supported = [(label, score) for label, score in available if score >= 0.5]
    coverage = len(available) / max(len(labeled), 1)
    return {
        "n": len(values),
        "n_labeled": len(labeled),
        "n_scored": len(available),
        "coverage": coverage,
        "conditional_auc": binary_auc(available),
        "neutral_auc": binary_auc(neutral),
        "balanced_accuracy": balanced_accuracy(available),
        "false_support_rate": (
            sum(score >= 0.5 for score in negatives) / len(negatives)
            if negatives
            else float("nan")
        ),
        "supported_precision": (
            sum(label for label, _score in predicted_supported) / len(predicted_supported)
            if predicted_supported
            else float("nan")
        ),
        "positive_mean": sum(positives) / len(positives) if positives else float("nan"),
        "negative_mean": sum(negatives) / len(negatives) if negatives else float("nan"),
        "unverifiable_rate": 1.0 - coverage,
    }


def mean_quality(rows: list[dict[str, float]]) -> dict[str, float | int]:
    result: dict[str, float | int] = {"scene_count": len(rows)}
    if not rows:
        return result
    for key in rows[0]:
        values = [float(row[key]) for row in rows if not math.isnan(float(row[key]))]
        result[f"macro_{key}"] = sum(values) / len(values) if values else float("nan")
    return result


def save_probability(path: Path, value: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.rint(np.clip(value, 0.0, 1.0) * 255).astype(np.uint8)).save(path)


def preview_panel(path: str, size: tuple[int, int]) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB").resize(size, resample=Image.Resampling.BILINEAR)


def heat_panel(value: np.ndarray, size: tuple[int, int]) -> Image.Image:
    gray = np.rint(np.clip(value, 0.0, 1.0) * 255).astype(np.uint8)
    red = gray
    blue = 255 - gray
    green = np.minimum(gray, 255 - gray) * 2
    image = Image.fromarray(np.stack((red, green, blue), axis=2).astype(np.uint8))
    return image.resize(size, resample=Image.Resampling.BILINEAR)


def render_overview(
    output_path: Path,
    previews: list[dict[str, Any]],
    roi_modes: tuple[str, ...],
) -> None:
    if not previews:
        return
    panel_size = (160, 160)
    label_height = 24
    columns = 2 + len(roi_modes)
    canvas = Image.new(
        "RGB",
        (columns * panel_size[0], len(previews) * (panel_size[1] + label_height)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    headers = ("T1", "T2", *roi_modes)
    for row_index, item in enumerate(previews):
        top = row_index * (panel_size[1] + label_height)
        panels = [
            preview_panel(item["pre_image"], panel_size),
            preview_panel(item["post_image"], panel_size),
            *(heat_panel(item["rois"][mode], panel_size) for mode in roi_modes),
        ]
        for column, (header, panel) in enumerate(zip(headers, panels, strict=True)):
            left = column * panel_size[0]
            canvas.paste(panel, (left, top + label_height))
            label = header if column else f"{item['sample_id']} | {header}"
            draw.text((left + 4, top + 5), label, fill="black")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=True) + "\n")


def main() -> None:
    args = parse_args()
    roi_modes = parse_csv_subset(args.roi_modes, ROI_MODES, "ROI modes")
    evidence_modes = parse_csv_subset(
        args.entity_evidence_modes,
        ENTITY_EVIDENCE_MODES,
        "entity evidence modes",
    )
    class_names = load_class_map(args.class_map)
    class_ids = {name: class_id for class_id, name in class_names.items()}
    hidden_entities = {
        item.strip() for item in args.hidden_entities.split(",") if item.strip()
    }
    visible_entities = set(class_ids) - hidden_entities
    external_index = load_external_roi_index(
        args.external_roi_manifest,
        field=args.predicted_roi_field,
    )
    segmentation_index = load_segmentation_index(args.entity_cache_jsonl)
    changeformer = None
    mci_predictor = None
    changeformer_requested = bool(
        args.changeformer_root or args.changeformer_checkpoint
    )
    mci_requested = bool(args.mci_root or args.mci_checkpoint)
    if changeformer_requested and mci_requested:
        raise ValueError("Select either ChangeFormer or MCI for one experiment run")
    if changeformer_requested:
        if args.changeformer_root is None or args.changeformer_checkpoint is None:
            raise ValueError(
                "Both --changeformer-root and --changeformer-checkpoint are required"
            )
        changeformer = ChangeFormerPredictor(
            root=args.changeformer_root,
            checkpoint=args.changeformer_checkpoint,
            device=args.changeformer_device,
            image_size=args.changeformer_image_size,
            embed_dim=args.changeformer_embed_dim,
        )
    if mci_requested:
        if args.mci_root is None or args.mci_checkpoint is None:
            raise ValueError("Both --mci-root and --mci-checkpoint are required")
        mci_predictor = MCIChangePredictor(
            root=args.mci_root,
            checkpoint=args.mci_checkpoint,
            device=args.mci_device,
        )
    learned_predictor = changeformer or mci_predictor
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in read_jsonl(args.samples):
        grouped[str(item["sample_id"])].append(item)
    if args.max_scenes > 0:
        selected = sorted(grouped)[: args.max_scenes]
        grouped = {sample_id: grouped[sample_id] for sample_id in selected}
    if "predicted_cd_roi" in roi_modes:
        missing_predictions = sorted(set(grouped) - set(external_index))
        if missing_predictions and learned_predictor is None:
            preview = ", ".join(missing_predictions[:5])
            raise ValueError(
                "predicted_cd_roi requires an external prediction for every scene or "
                "an explicit ChangeFormer backend; "
                f"missing {len(missing_predictions)} (first: {preview})"
            )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    score_rows: dict[str, list[dict[str, Any]]] = {
        evidence_mode: [] for evidence_mode in evidence_modes
    }
    quality_rows: dict[str, list[dict[str, float]]] = {
        mode: [] for mode in roi_modes
    }
    source_counts: dict[str, Counter[str]] = {
        mode: Counter() for mode in roi_modes
    }
    previews: list[dict[str, Any]] = []
    prediction_manifest_rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for scene_index, (sample_id, scene_items) in enumerate(sorted(grouped.items()), start=1):
        representative = scene_items[0]
        if representative.get("pre_label") and representative.get("post_label"):
            semantic_pre = load_label_ids(representative["pre_label"])
            semantic_post = load_label_ids(representative["post_label"])
            if semantic_pre.shape != semantic_post.shape:
                raise ValueError(f"Semantic label shape mismatch for {sample_id}")
            oracle_change = semantic_pre != semantic_post
            reference_source = "semantic_pre_not_equal_post"
        elif representative.get("change_mask"):
            semantic_pre = None
            semantic_post = None
            oracle_change = load_label_mask(representative["change_mask"]) != 0
            reference_source = "class_id_change_mask"
            unsupported_modes = set(evidence_modes) - {"open_vocab"}
            if unsupported_modes:
                raise ValueError(
                    "Hybrid/GT entity routing requires pre_label and post_label; "
                    "with a single LEVIR change mask use --entity-evidence-modes open_vocab"
                )
        else:
            raise ValueError(f"No reference change source for {sample_id}")
        if args.cache_dir is not None:
            open_vocab = load_open_vocab(args.cache_dir / f"{sample_id}.npz")
        else:
            if sample_id not in segmentation_index:
                raise FileNotFoundError(
                    f"Missing {sample_id} in {args.entity_cache_jsonl}"
                )
            open_vocab = load_open_vocab_from_segmentation(segmentation_index[sample_id])
        scene_external = external_index.get(sample_id)
        if "predicted_cd_roi" in roi_modes and scene_external is None:
            assert learned_predictor is not None
            probability = learned_predictor.predict(
                representative["pre_image"],
                representative["post_image"],
                shape=oracle_change.shape,
            )
            prediction_path = (
                args.output_dir / "predicted_cd_probabilities" / f"{sample_id}.npz"
            )
            prediction_path.parent.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(prediction_path, probability=probability)
            scene_external = {"path": prediction_path, "array_key": "probability"}
        if "predicted_cd_roi" in roi_modes and scene_external is not None:
            prediction_manifest_rows.append(
                {
                    "sample_id": sample_id,
                    "roi_path": str(scene_external["path"]),
                    "array_key": scene_external.get("array_key", "probability"),
                    "backend": (
                        learned_predictor.metadata["backend"]
                        if learned_predictor is not None and sample_id not in external_index
                        else "external_manifest"
                    ),
                }
            )
        rois = build_scene_rois(
            modes=roi_modes,
            representative=representative,
            oracle_change=oracle_change,
            external=scene_external,
            args=args,
        )
        for mode, result in rois.items():
            quality_rows[mode].append(roi_quality(result.probability, oracle_change))
            source_counts[mode][str(result.metadata["source"])] += 1
            if args.save_roi_maps:
                save_probability(
                    args.output_dir / "roi_maps" / sample_id / f"{mode}.png",
                    result.probability,
                )
        if len(previews) < args.overview_limit:
            previews.append(
                {
                    "sample_id": sample_id,
                    "pre_image": representative["pre_image"],
                    "post_image": representative["post_image"],
                    "rois": {
                        mode: result.probability.copy() for mode, result in rois.items()
                    },
                }
            )

        for item in scene_items:
            pair = claim_pair(item)
            if pair is None:
                continue
            source_claim, target_claim = pair
            source = str(source_claim["entity"])
            target = str(target_claim["entity"])
            location = str(
                source_claim.get("location") or target_claim.get("location") or ""
            )
            for evidence_mode in evidence_modes:
                relation = relation_mask(
                    source_masks=entity_masks(
                        source,
                        evidence_mode=evidence_mode,
                        role="source",
                        semantic_pre=semantic_pre,
                        semantic_post=semantic_post,
                        class_ids=class_ids,
                        visible_entities=visible_entities,
                        open_vocab=open_vocab,
                        min_ov_confidence=args.min_ov_confidence,
                    ),
                    target_masks=entity_masks(
                        target,
                        evidence_mode=evidence_mode,
                        role="target",
                        semantic_pre=semantic_pre,
                        semantic_post=semantic_post,
                        class_ids=class_ids,
                        visible_entities=visible_entities,
                        open_vocab=open_vocab,
                        min_ov_confidence=args.min_ov_confidence,
                    ),
                    location=location,
                )
                score_rows[evidence_mode].append(
                    {
                        "sample_id": sample_id,
                        "item_id": item.get("item_id", f"{sample_id}:{item.get('model', 'item')}"),
                        "sample_type": item.get("sample_type", item.get("model", "unknown")),
                        "is_factually_correct": (
                            bool(item["is_factually_correct"])
                            if "is_factually_correct" in item
                            else None
                        ),
                        "reference_source": reference_source,
                        "source": source,
                        "target": target,
                        "location": location,
                        "scores": {
                            mode: soft_relation_score(relation, rois[mode].probability)
                            for mode in roi_modes
                        },
                    }
                )
        if scene_index % 25 == 0 or scene_index == len(grouped):
            elapsed = time.perf_counter() - started
            print(
                f"processed {scene_index}/{len(grouped)} scenes in {elapsed:.1f}s",
                flush=True,
            )

    for evidence_mode, rows in score_rows.items():
        write_jsonl(args.output_dir / f"{evidence_mode}_scores.jsonl", rows)
    if prediction_manifest_rows:
        write_jsonl(
            args.output_dir / "predicted_cd_manifest.jsonl",
            prediction_manifest_rows,
        )
    render_overview(args.output_dir / "roi_overview.png", previews, roi_modes)
    score_summary = {
        evidence_mode: {
            mode: metrics(
                [
                    (row["is_factually_correct"], row["scores"][mode])
                    for row in rows
                ]
            )
            for mode in roi_modes
        }
        for evidence_mode, rows in score_rows.items()
    }
    summary = {
        "experiment": "predicted_roi_ablation",
        "scene_count": len(grouped),
        "item_count": sum(len(items) for items in grouped.values()),
        "relation_eligible_item_count": (
            len(score_rows[evidence_modes[0]]) if evidence_modes else 0
        ),
        "relation_skipped_item_count": (
            sum(len(items) for items in grouped.values())
            - (len(score_rows[evidence_modes[0]]) if evidence_modes else 0)
        ),
        "relation_eligibility": "at least two parsed claims",
        "class_map": class_names,
        "hidden_entities": sorted(hidden_entities),
        "visible_entities": sorted(visible_entities),
        "entity_evidence_modes": list(evidence_modes),
        "roi_modes": list(roi_modes),
        "roi_protocol": {
            "oracle_gt_roi": "semantic_pre != semantic_post",
            "predicted_cd_roi": "independent external change-detector manifest",
            "feature_difference_roi": "continuous robust RGB difference",
            "no_roi": "constant all-one gate",
            "score": "mean ROI gate value over source-remove/target-add relation",
            "gate_floor": args.gate_floor,
            "threshold_method": args.threshold_method,
            "threshold_quantile": args.threshold_quantile,
            "fixed_threshold": args.fixed_threshold,
            "blur_radius": args.blur_radius,
        },
        "entity_cache": (
            {"format": "per_scene_npz", "path": str(args.cache_dir)}
            if args.cache_dir is not None
            else {"format": "segmentations_jsonl", "path": str(args.entity_cache_jsonl)}
        ),
        "external_roi_manifest": (
            str(args.external_roi_manifest) if args.external_roi_manifest else None
        ),
        "external_prediction_matches": len(prediction_manifest_rows),
        "changeformer": changeformer.metadata if changeformer is not None else None,
        "mci": mci_predictor.metadata if mci_predictor is not None else None,
        "min_ov_confidence": args.min_ov_confidence,
        "scores": score_summary,
        "roi_quality_against_oracle": {
            mode: mean_quality(rows) for mode, rows in quality_rows.items()
        },
        "roi_source_counts": {
            mode: dict(counts) for mode, counts in source_counts.items()
        },
        "metric_definition": {
            "coverage": "fraction receiving a numeric score",
            "neutral_auc": "ROC-AUC with unverifiable assigned 0.5",
            "balanced_accuracy": "balanced accuracy at score threshold 0.5",
            "false_support_rate": "contradicted items scored at least 0.5",
            "supported_precision": "factual fraction among items scored at least 0.5",
            "unverifiable_rate": "one minus score coverage",
        },
        "runtime_seconds": time.perf_counter() - started,
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
