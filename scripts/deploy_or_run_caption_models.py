#!/usr/bin/env python3
"""Prepare and run official RSICCformer/Chg2Cap checkpoints on LEVIR test pairs.

The script deliberately keeps upstream repositories unmodified.  It builds the
two vocabularies from the official ``LevirCCcaptions.json`` file, loads trusted
official checkpoints in-place, and emits one auditable JSONL row per image pair:

    {"sample_id": "test_000001", "model_family": "rsiccformer", "caption": "..."}

The old repositories predate recent PyTorch releases.  All compatibility code
therefore lives here rather than being mixed into either upstream checkout.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
import zipfile
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any

MODEL_VARIANTS = {
    "rsiccformer": "resnet101_MCCFormers_diff_as_Q_trans_official",
    "chg2cap": "LEVIR_CC_batchsize_32_resnet101_official",
}
REQUIRED_OUTPUT_FIELDS = ("sample_id", "model_family", "caption")
SAMPLE_ID_PATTERN = re.compile(r"(?:train|val|test)_\d+", flags=re.IGNORECASE)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, newline="\n"
    ) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, newline="\n"
    ) as handle:
        for row in rows:
            handle.write(_json_dumps(row) + "\n")
            count += 1
        temp_path = Path(handle.name)
    temp_path.replace(path)
    return count


def _read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            yield value


def _canonical_sample_id(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    match = SAMPLE_ID_PATTERN.search(text)
    if match:
        return match.group(0).lower()
    return Path(text).stem.lower()


def _manifest_sample_ids(path: Path) -> set[str]:
    sample_ids: set[str] = set()
    for row in _read_jsonl(path):
        raw_id = row.get("sample_id", row.get("id", row.get("image_id")))
        if raw_id is None:
            raise ValueError(f"{path}: row lacks sample_id/id/image_id: {row}")
        sample_id = _canonical_sample_id(raw_id)
        if not sample_id:
            raise ValueError(f"{path}: empty sample id: {row}")
        sample_ids.add(sample_id)
    return sample_ids


def _sha256(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _load_caption_data(caption_json: Path) -> dict[str, Any]:
    with caption_json.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    images = data.get("images")
    if not isinstance(images, list) or not images:
        raise ValueError(f"Invalid LEVIR caption JSON: {caption_json}")
    return data


def build_rsiccformer_vocab(data: dict[str, Any], min_word_freq: int = 5) -> dict[str, int]:
    """Reproduce RSICC ``utils.create_input_files`` vocabulary ordering."""

    word_freq: Counter[str] = Counter()
    for image in data["images"]:
        for sentence in image["sentences"]:
            word_freq.update(sentence["tokens"])
    words = [word for word in word_freq if word_freq[word] > min_word_freq]
    word_map = {word: index + 1 for index, word in enumerate(words)}
    word_map["<unk>"] = len(word_map) + 1
    word_map["<start>"] = len(word_map) + 1
    word_map["<end>"] = len(word_map) + 1
    word_map["<pad>"] = 0
    return word_map


def _chg2cap_tokenize(text: str) -> list[str]:
    for punctuation in (";", ","):
        text = text.replace(punctuation, f" {punctuation}")
    for punctuation in ("?", "."):
        text = text.replace(punctuation, "")
    tokens = [token for token in text.split(" ") if token]
    return ["<START>", *tokens, "<END>"]


def build_chg2cap_vocab(data: dict[str, Any], min_token_count: int = 5) -> dict[str, int]:
    """Reproduce Chg2Cap ``preprocess_data.build_vocab`` ordering."""

    token_counts: Counter[str] = Counter()
    for image in data["images"]:
        for sentence in image["sentences"]:
            token_counts.update(_chg2cap_tokenize(sentence["raw"]))
    token_to_index = {"<NULL>": 0, "<UNK>": 1, "<START>": 2, "<END>": 3}
    for token, count in sorted(token_counts.items()):
        if token not in token_to_index and count >= min_token_count:
            token_to_index[token] = len(token_to_index)
    return token_to_index


def _paired_images(images_root: Path) -> list[tuple[str, Path, Path]]:
    root = images_root
    if (root / "A").is_dir() and (root / "B").is_dir():
        image_a_root, image_b_root = root / "A", root / "B"
    elif (root / "test" / "A").is_dir() and (root / "test" / "B").is_dir():
        image_a_root, image_b_root = root / "test" / "A", root / "test" / "B"
    else:
        raise FileNotFoundError(f"Expected A/ and B/ below {images_root}")

    a_by_stem = {path.stem.lower(): path for path in sorted(image_a_root.glob("*.png"))}
    b_by_stem = {path.stem.lower(): path for path in sorted(image_b_root.glob("*.png"))}
    if not a_by_stem or a_by_stem.keys() != b_by_stem.keys():
        missing_a = sorted(b_by_stem.keys() - a_by_stem.keys())[:10]
        missing_b = sorted(a_by_stem.keys() - b_by_stem.keys())[:10]
        raise ValueError(
            f"A/B mismatch under {images_root}; A={len(a_by_stem)}, B={len(b_by_stem)}, "
            f"missing_a={missing_a}, missing_b={missing_b}"
        )
    return [(stem, a_by_stem[stem], b_by_stem[stem]) for stem in sorted(a_by_stem)]


def _safe_extract_member(archive: zipfile.ZipFile, member: zipfile.ZipInfo, root: Path) -> None:
    relative = Path(member.filename)
    target = (root / relative).resolve()
    root_resolved = root.resolve()
    if root_resolved not in target.parents and target != root_resolved:
        raise ValueError(f"Unsafe ZIP member: {member.filename}")
    if member.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.stat().st_size != member.file_size:
            raise FileExistsError(
                f"Refusing to overwrite size-mismatched file: {target} "
                f"({target.stat().st_size} != {member.file_size})"
            )
        return
    with archive.open(member) as source, target.open("xb") as destination:
        shutil.copyfileobj(source, destination, length=8 * 1024 * 1024)


def command_prepare_test(args: argparse.Namespace) -> None:
    archive_path = Path(args.archive).resolve()
    output_root = Path(args.output_root).resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)
    output_root.mkdir(parents=True, exist_ok=True)

    selected = 0
    prefixes = (
        "LEVIR-MCI-dataset/images/test/A/",
        "LEVIR-MCI-dataset/images/test/B/",
    )
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if any(member.filename.startswith(prefix) for prefix in prefixes):
                _safe_extract_member(archive, member, output_root)
                if not member.is_dir():
                    selected += 1

    images_root = output_root / "LEVIR-MCI-dataset" / "images" / "test"
    pairs = _paired_images(images_root)
    if args.expected_pairs is not None and len(pairs) != args.expected_pairs:
        raise ValueError(f"Expected {args.expected_pairs} pairs, found {len(pairs)}")

    index_path = Path(args.index_output).resolve()
    index_rows = (
        {
            "sample_id": sample_id,
            "image_a": str(image_a),
            "image_b": str(image_b),
        }
        for sample_id, image_a, image_b in pairs
    )
    index_count = _write_jsonl(index_path, index_rows)

    vocab_summary: dict[str, Any] = {}
    if args.caption_json:
        caption_json = Path(args.caption_json).resolve()
        data = _load_caption_data(caption_json)
        vocab_root = Path(args.vocab_output_root).resolve()
        rsicc_vocab = build_rsiccformer_vocab(data, args.rsicc_min_word_freq)
        chg2cap_vocab = build_chg2cap_vocab(data, args.chg2cap_min_token_count)
        _write_json(vocab_root / "rsiccformer_wordmap.json", rsicc_vocab)
        _write_json(vocab_root / "chg2cap_vocab.json", chg2cap_vocab)
        vocab_summary = {
            "caption_json": str(caption_json),
            "rsiccformer_vocab_size": len(rsicc_vocab),
            "chg2cap_vocab_size": len(chg2cap_vocab),
            "vocab_output_root": str(vocab_root),
        }

    intersection_summary: dict[str, Any] = {}
    if args.intersection_manifest:
        manifest_path = Path(args.intersection_manifest).resolve()
        keep_ids = _manifest_sample_ids(manifest_path)
        pair_ids = {sample_id for sample_id, _, _ in pairs}
        intersection_ids = pair_ids & keep_ids
        intersection_path = Path(args.intersection_output).resolve()
        _write_jsonl(
            intersection_path,
            (
                {"sample_id": sample_id, "image_a": str(image_a), "image_b": str(image_b)}
                for sample_id, image_a, image_b in pairs
                if sample_id in intersection_ids
            ),
        )
        intersection_summary = {
            "intersection_manifest": str(manifest_path),
            "manifest_unique_ids": len(keep_ids),
            "intersection_count": len(intersection_ids),
            "intersection_output": str(intersection_path),
        }

    summary = {
        "archive": str(archive_path),
        "selected_zip_files": selected,
        "pair_count": len(pairs),
        "index_count": index_count,
        "images_root": str(images_root),
        "index_output": str(index_path),
        **vocab_summary,
        **intersection_summary,
    }
    if args.summary_output:
        _write_json(Path(args.summary_output).resolve(), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _batched(values: Sequence[Any], batch_size: int) -> Iterator[Sequence[Any]]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    for start in range(0, len(values), batch_size):
        yield values[start : start + batch_size]


def _load_image_tensor(path: Path, *, mean: Sequence[float], std: Sequence[float], scale: float):
    import numpy as np
    import torch
    from PIL import Image

    with Image.open(path) as image:
        array = np.asarray(image.convert("RGB"), dtype=np.float32)
    if array.shape[:2] != (256, 256):
        with Image.open(path) as image:
            array = np.asarray(image.convert("RGB").resize((256, 256)), dtype=np.float32)
    array /= scale
    array = (array - np.asarray(mean, dtype=np.float32)) / np.asarray(std, dtype=np.float32)
    return torch.from_numpy(array.transpose(2, 0, 1).copy())


def _load_batch(
    batch: Sequence[tuple[str, Path, Path]],
    *,
    mean: Sequence[float],
    std: Sequence[float],
    scale: float,
    device: str,
):
    import torch

    images_a = torch.stack(
        [_load_image_tensor(image_a, mean=mean, std=std, scale=scale) for _, image_a, _ in batch]
    ).to(device, non_blocking=True)
    images_b = torch.stack(
        [_load_image_tensor(image_b, mean=mean, std=std, scale=scale) for _, _, image_b in batch]
    ).to(device, non_blocking=True)
    return images_a, images_b


def _verify_checkpoint(checkpoint: Path, expected_sha256: str | None) -> dict[str, Any]:
    if not checkpoint.is_file() or checkpoint.stat().st_size == 0:
        raise FileNotFoundError(f"Missing or empty checkpoint: {checkpoint}")
    digest = _sha256(checkpoint)
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        raise ValueError(f"SHA-256 mismatch for {checkpoint}: {digest} != {expected_sha256}")
    return {
        "checkpoint": str(checkpoint.resolve()),
        "checkpoint_size": checkpoint.stat().st_size,
        "checkpoint_sha256": digest,
    }


def _require_trusted_pickle(args: argparse.Namespace) -> None:
    if not args.trust_official_pickle:
        raise ValueError(
            "The legacy checkpoint requires Python pickle. Re-run with "
            "--trust-official-pickle only after verifying it came from the official release."
        )


def _torch_load_legacy(path: Path, *, map_location: str):
    import torch

    # PyTorch >=2.6 defaults weights_only=True.  Both official legacy releases
    # contain objects not covered by the restricted weights-only unpickler.
    return torch.load(path, map_location=map_location, weights_only=False)


def _decode_tokens(
    token_ids: Sequence[int], reverse_vocab: dict[int, str], ignored_ids: set[int]
) -> str:
    words = [
        reverse_vocab.get(int(token_id), "<unk>")
        for token_id in token_ids
        if int(token_id) not in ignored_ids
    ]
    return " ".join(words).strip()


def _write_model_outputs(
    output_path: Path,
    *,
    model_family: str,
    captions: Iterable[tuple[str, str]],
    checkpoint_info: dict[str, Any],
    repository: Path,
    repository_commit: str | None,
    elapsed_seconds: float,
) -> dict[str, Any]:
    provenance = {
        "repository": str(repository.resolve()),
        "repository_commit": repository_commit,
        **checkpoint_info,
    }
    rows = [
        {
            "sample_id": sample_id,
            "model_family": model_family,
            "model_variant": MODEL_VARIANTS[model_family],
            "caption": caption,
            "provenance": provenance,
        }
        for sample_id, caption in captions
    ]
    count = _write_jsonl(output_path, rows)
    empty_count = sum(not row["caption"] for row in rows)
    summary = {
        "model_family": model_family,
        "model_variant": MODEL_VARIANTS[model_family],
        "output": str(output_path.resolve()),
        "count": count,
        "empty_caption_count": empty_count,
        "elapsed_seconds": elapsed_seconds,
        "seconds_per_sample": elapsed_seconds / count if count else None,
        **checkpoint_info,
        "repository": str(repository.resolve()),
        "repository_commit": repository_commit,
    }
    _write_json(output_path.with_suffix(output_path.suffix + ".summary.json"), summary)
    return summary


def _git_commit(repository: Path) -> str | None:
    head = repository / ".git" / "HEAD"
    if not head.is_file():
        return None
    text = head.read_text(encoding="utf-8").strip()
    if text.startswith("ref: "):
        ref_path = repository / ".git" / text[5:]
        if ref_path.is_file():
            return ref_path.read_text(encoding="utf-8").strip()
        packed_refs = repository / ".git" / "packed-refs"
        if packed_refs.is_file():
            for line in packed_refs.read_text(encoding="utf-8").splitlines():
                if line and not line.startswith(("#", "^")):
                    digest, ref = line.split(" ", 1)
                    if ref == text[5:]:
                        return digest
        return None
    return text


def _rsiccformer_greedy_decode(encoder_image, encoder_feat, decoder, images_a, images_b, word_map):
    import torch

    memory_a = encoder_image(images_a)
    memory_b = encoder_image(images_b)
    memory = encoder_feat(memory_a, memory_b)
    batch_size = images_a.shape[0]
    max_length = 52
    pad_id = int(word_map["<pad>"])
    start_id = int(word_map["<start>"])
    end_id = int(word_map["<end>"])
    target = torch.full((max_length, batch_size), pad_id, dtype=torch.long, device=images_a.device)
    target[0] = start_id
    mask = torch.triu(
        torch.full((max_length, max_length), float("-inf"), device=images_a.device), diagonal=1
    )
    sequences = torch.full(
        (batch_size, max_length), pad_id, dtype=torch.long, device=images_a.device
    )
    sequences[:, 0] = start_id
    finished = torch.zeros(batch_size, dtype=torch.bool, device=images_a.device)

    for step in range(1, max_length):
        embeddings = decoder.position_encoding(decoder.vocab_embedding(target))
        predictions = decoder.transformer(embeddings, memory, tgt_mask=mask)
        logits = decoder.wdc(predictions[step - 1])
        next_ids = logits.argmax(dim=-1)
        next_ids = torch.where(finished, torch.full_like(next_ids, pad_id), next_ids)
        target[step] = next_ids
        sequences[:, step] = next_ids
        finished |= next_ids.eq(end_id)
        if bool(finished.all()):
            break
    return sequences.detach().cpu().tolist()


def command_run_rsiccformer(args: argparse.Namespace) -> None:
    _require_trusted_pickle(args)
    import torch

    repository = Path(args.repository).resolve()
    checkpoint = Path(args.checkpoint).resolve()
    images_root = Path(args.images_root).resolve()
    output_path = Path(args.output).resolve()
    checkpoint_info = _verify_checkpoint(checkpoint, args.expected_sha256)
    if str(repository) not in sys.path:
        sys.path.insert(0, str(repository))

    # Imports make the class names referenced by the legacy pickle resolvable.
    __import__("models")
    __import__("models_RSICCformerDfusion")
    rsicc_models = sys.modules['models_RSICCformerDfusion']
    legacy_forward = rsicc_models.Mesh_TransformerDecoderLayer.forward

    def compatible_forward(self, *values, **options):
        options.pop('tgt_is_causal', None)
        options.pop('memory_is_causal', None)
        return legacy_forward(self, *values, **options)

    rsicc_models.Mesh_TransformerDecoderLayer.forward = compatible_forward
    word_map = build_rsiccformer_vocab(_load_caption_data(Path(args.caption_json).resolve()))
    reverse_vocab = {index: token for token, index in word_map.items()}
    pairs = _paired_images(images_root)
    if args.max_samples is not None:
        pairs = pairs[: args.max_samples]

    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    checkpoint_value = _torch_load_legacy(checkpoint, map_location="cpu")
    required = {"encoder_image", "encoder_feat", "decoder"}
    if not isinstance(checkpoint_value, dict) or not required.issubset(checkpoint_value):
        raise ValueError(
            f"Unexpected RSICCformer checkpoint keys: {getattr(checkpoint_value, 'keys', lambda: [])()}"  # noqa: E501
        )
    encoder_image = checkpoint_value["encoder_image"].to(device).eval()
    encoder_feat = checkpoint_value["encoder_feat"].to(device).eval()
    decoder = checkpoint_value["decoder"].to(device).eval()
    model_vocab_size = int(decoder.vocab_embedding.num_embeddings)
    if len(word_map) != model_vocab_size:
        raise ValueError(
            f"RSICCformer vocabulary mismatch: generated={len(word_map)}, checkpoint={model_vocab_size}"  # noqa: E501
        )

    captions: list[tuple[str, str]] = []
    ignored_ids = {word_map["<pad>"], word_map["<start>"], word_map["<end>"]}
    started = time.perf_counter()
    with torch.inference_mode():
        for batch_number, batch in enumerate(_batched(pairs, args.batch_size), start=1):
            images_a, images_b = _load_batch(
                batch,
                mean=(0.485, 0.456, 0.406),
                std=(0.229, 0.224, 0.225),
                scale=255.0,
                device=device,
            )
            sequences = _rsiccformer_greedy_decode(
                encoder_image, encoder_feat, decoder, images_a, images_b, word_map
            )
            captions.extend(
                (sample_id, _decode_tokens(sequence, reverse_vocab, ignored_ids))
                for (sample_id, _, _), sequence in zip(batch, sequences, strict=False)
            )
            if batch_number % args.log_every == 0 or len(captions) == len(pairs):
                print(f"rsiccformer: {len(captions)}/{len(pairs)}", flush=True)
    elapsed = time.perf_counter() - started
    summary = _write_model_outputs(
        output_path,
        model_family="rsiccformer",
        captions=captions,
        checkpoint_info=checkpoint_info,
        repository=repository,
        repository_commit=_git_commit(repository),
        elapsed_seconds=elapsed,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


@contextlib.contextmanager
def _torchvision_without_pretrained_download():
    import torchvision.models as vision_models

    original = vision_models.resnet101

    def resnet101_without_download(*unused_args, **unused_kwargs):
        return original(weights=None)

    vision_models.resnet101 = resnet101_without_download
    try:
        yield
    finally:
        vision_models.resnet101 = original


def _chg2cap_greedy_decode(encoder, encoder_trans, decoder, images_a, images_b, word_map):
    import torch

    features_a, features_b = encoder(images_a, images_b)
    features_a, features_b = encoder_trans(features_a, features_b)
    cosine = decoder.cos(features_a, features_b)
    fused = torch.cat([features_a, features_b], dim=1) + cosine.unsqueeze(1)
    fused = decoder.LN(decoder.Conv1(fused))
    batch_size, channels = fused.shape[:2]
    memory = fused.view(batch_size, channels, -1).permute(2, 0, 1)

    max_length = int(decoder.max_lengths)
    null_id = int(word_map["<NULL>"])
    start_id = int(word_map["<START>"])
    end_id = int(word_map["<END>"])
    target = torch.full((batch_size, max_length), null_id, dtype=torch.long, device=images_a.device)
    target[:, 0] = start_id
    sequences = torch.full(
        (batch_size, max_length + 1), null_id, dtype=torch.long, device=images_a.device
    )
    sequences[:, 0] = start_id
    mask = torch.triu(
        torch.full((max_length, max_length), float("-inf"), device=images_a.device), diagonal=1
    )
    finished = torch.zeros(batch_size, dtype=torch.bool, device=images_a.device)

    for step in range(max_length):
        padding_mask = target.eq(null_id)
        embeddings = decoder.position_encoding(decoder.vocab_embedding(target).transpose(1, 0))
        predictions = decoder.transformer(
            embeddings, memory, tgt_mask=mask, tgt_key_padding_mask=padding_mask
        )
        logits = decoder.wdc(decoder.dropout(predictions))[step]
        next_ids = logits.argmax(dim=-1)
        next_ids = torch.where(finished, torch.full_like(next_ids, null_id), next_ids)
        sequences[:, step + 1] = next_ids
        finished |= next_ids.eq(end_id)
        if step < max_length - 1:
            target[:, step + 1] = next_ids
        if bool(finished.all()):
            break
    return sequences.detach().cpu().tolist()


def command_run_chg2cap(args: argparse.Namespace) -> None:
    _require_trusted_pickle(args)
    import torch

    repository = Path(args.repository).resolve()
    checkpoint = Path(args.checkpoint).resolve()
    images_root = Path(args.images_root).resolve()
    output_path = Path(args.output).resolve()
    checkpoint_info = _verify_checkpoint(checkpoint, args.expected_sha256)
    if str(repository) not in sys.path:
        sys.path.insert(0, str(repository))

    from model.model_decoder import DecoderTransformer
    from model.model_encoder import AttentiveEncoder, Encoder

    word_map = build_chg2cap_vocab(_load_caption_data(Path(args.caption_json).resolve()))
    reverse_vocab = {index: token for token, index in word_map.items()}
    pairs = _paired_images(images_root)
    if args.max_samples is not None:
        pairs = pairs[: args.max_samples]

    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable")
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    checkpoint_value = _torch_load_legacy(checkpoint, map_location="cpu")
    required = {"encoder_dict", "encoder_trans_dict", "decoder_dict"}
    if not isinstance(checkpoint_value, dict) or not required.issubset(checkpoint_value):
        raise ValueError(
            f"Unexpected Chg2Cap checkpoint keys: {getattr(checkpoint_value, 'keys', lambda: [])()}"
        )
    checkpoint_vocab_size = int(checkpoint_value["decoder_dict"]["vocab_embedding.weight"].shape[0])
    if len(word_map) != checkpoint_vocab_size:
        raise ValueError(
            f"Chg2Cap vocabulary mismatch: generated={len(word_map)}, checkpoint={checkpoint_vocab_size}"  # noqa: E501
        )

    with _torchvision_without_pretrained_download():
        encoder = Encoder("resnet101")
    encoder_trans = AttentiveEncoder(
        n_layers=3,
        feature_size=[16, 16, 2048],
        heads=8,
        hidden_dim=512,
        attention_dim=2048,
        dropout=0.1,
    )
    decoder = DecoderTransformer(
        encoder_dim=2048,
        feature_dim=2048,
        vocab_size=len(word_map),
        max_lengths=41,
        word_vocab=word_map,
        n_head=8,
        n_layers=1,
        dropout=0.1,
    )
    encoder.load_state_dict(checkpoint_value["encoder_dict"], strict=True)
    encoder_trans.load_state_dict(checkpoint_value["encoder_trans_dict"], strict=True)
    decoder.load_state_dict(checkpoint_value["decoder_dict"], strict=True)
    encoder = encoder.to(device).eval()
    encoder_trans = encoder_trans.to(device).eval()
    decoder = decoder.to(device).eval()

    captions: list[tuple[str, str]] = []
    ignored_ids = {
        word_map["<NULL>"],
        word_map["<START>"],
        word_map["<END>"],
    }
    started = time.perf_counter()
    with torch.inference_mode():
        for batch_number, batch in enumerate(_batched(pairs, args.batch_size), start=1):
            images_a, images_b = _load_batch(
                batch,
                mean=(100.6790, 99.5023, 84.9932),
                std=(50.9820, 48.4838, 44.7057),
                scale=1.0,
                device=device,
            )
            sequences = _chg2cap_greedy_decode(
                encoder, encoder_trans, decoder, images_a, images_b, word_map
            )
            captions.extend(
                (sample_id, _decode_tokens(sequence, reverse_vocab, ignored_ids))
                for (sample_id, _, _), sequence in zip(batch, sequences, strict=False)
            )
            if batch_number % args.log_every == 0 or len(captions) == len(pairs):
                print(f"chg2cap: {len(captions)}/{len(pairs)}", flush=True)
    elapsed = time.perf_counter() - started
    summary = _write_model_outputs(
        output_path,
        model_family="chg2cap",
        captions=captions,
        checkpoint_info=checkpoint_info,
        repository=repository,
        repository_commit=_git_commit(repository),
        elapsed_seconds=elapsed,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def command_filter_output(args: argparse.Namespace) -> None:
    input_path = Path(args.input).resolve()
    manifest_path = Path(args.manifest).resolve()
    output_path = Path(args.output).resolve()
    keep_ids = _manifest_sample_ids(manifest_path)
    rows = [
        row
        for row in _read_jsonl(input_path)
        if _canonical_sample_id(row.get("sample_id")) in keep_ids
    ]
    count = _write_jsonl(output_path, rows)
    if args.expected_count is not None and count != args.expected_count:
        raise ValueError(f"Expected {args.expected_count} rows after filtering, wrote {count}")
    print(
        json.dumps(
            {
                "input": str(input_path),
                "manifest": str(manifest_path),
                "output": str(output_path),
                "manifest_unique_ids": len(keep_ids),
                "output_count": count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def command_validate_output(args: argparse.Namespace) -> None:
    input_path = Path(args.input).resolve()
    rows = list(_read_jsonl(input_path))
    duplicate_keys: list[str] = []
    seen: set[tuple[str, str]] = set()
    empty_caption_ids: list[str] = []
    counts: Counter[str] = Counter()
    for index, row in enumerate(rows, start=1):
        missing = [field for field in REQUIRED_OUTPUT_FIELDS if field not in row]
        if missing:
            raise ValueError(f"{input_path}:{index}: missing fields {missing}")
        sample_id = _canonical_sample_id(row["sample_id"])
        family = str(row["model_family"]).strip().lower()
        key = (sample_id, family)
        if key in seen:
            duplicate_keys.append(f"{family}:{sample_id}")
        seen.add(key)
        counts[family] += 1
        if not str(row["caption"]).strip():
            empty_caption_ids.append(f"{family}:{sample_id}")

    missing_ids: list[str] = []
    unexpected_ids: list[str] = []
    if args.expected_manifest:
        expected = _manifest_sample_ids(Path(args.expected_manifest).resolve())
        actual = {_canonical_sample_id(row["sample_id"]) for row in rows}
        missing_ids = sorted(expected - actual)
        unexpected_ids = sorted(actual - expected)
    summary = {
        "input": str(input_path),
        "row_count": len(rows),
        "counts_by_model": dict(sorted(counts.items())),
        "duplicate_count": len(duplicate_keys),
        "duplicates": duplicate_keys[:50],
        "empty_caption_count": len(empty_caption_ids),
        "empty_caption_ids": empty_caption_ids[:50],
        "missing_expected_count": len(missing_ids),
        "missing_expected_ids": missing_ids[:50],
        "unexpected_count": len(unexpected_ids),
        "unexpected_ids": unexpected_ids[:50],
        "valid": not duplicate_keys
        and not empty_caption_ids
        and not missing_ids
        and not unexpected_ids,
    }
    if args.summary_output:
        _write_json(Path(args.summary_output).resolve(), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["valid"]:
        raise SystemExit(2)


def _add_inference_arguments(parser: argparse.ArgumentParser, *, default_batch_size: int) -> None:
    parser.add_argument("--repository", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--caption-json", required=True)
    parser.add_argument("--images-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=default_batch_size)
    parser.add_argument("--max-samples", type=int)
    parser.add_argument("--seed", type=int, default=123)
    parser.add_argument("--log-every", type=int, default=10)
    parser.add_argument("--expected-sha256")
    parser.add_argument(
        "--trust-official-pickle",
        action="store_true",
        help="Allow legacy pickle loading after independently verifying official provenance.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare-test", help="Extract only LEVIR-MCI test A/B pairs.")
    prepare.add_argument("--archive", required=True)
    prepare.add_argument("--output-root", required=True)
    prepare.add_argument("--index-output", required=True)
    prepare.add_argument("--expected-pairs", type=int, default=1929)
    prepare.add_argument("--caption-json")
    prepare.add_argument("--vocab-output-root")
    prepare.add_argument("--rsicc-min-word-freq", type=int, default=5)
    prepare.add_argument("--chg2cap-min-token-count", type=int, default=5)
    prepare.add_argument("--intersection-manifest")
    prepare.add_argument("--intersection-output")
    prepare.add_argument("--summary-output")
    prepare.set_defaults(func=command_prepare_test)

    run_rsicc = subparsers.add_parser(
        "run-rsiccformer", help="Run official RSICCformer checkpoint."
    )
    _add_inference_arguments(run_rsicc, default_batch_size=8)
    run_rsicc.set_defaults(func=command_run_rsiccformer)

    run_chg = subparsers.add_parser("run-chg2cap", help="Run official Chg2Cap checkpoint.")
    _add_inference_arguments(run_chg, default_batch_size=2)
    run_chg.set_defaults(func=command_run_chg2cap)

    filter_output = subparsers.add_parser(
        "filter-output", help="Keep outputs present in a manifest."
    )
    filter_output.add_argument("--input", required=True)
    filter_output.add_argument("--manifest", required=True)
    filter_output.add_argument("--output", required=True)
    filter_output.add_argument("--expected-count", type=int)
    filter_output.set_defaults(func=command_filter_output)

    validate = subparsers.add_parser("validate-output", help="Audit a unified output JSONL.")
    validate.add_argument("--input", required=True)
    validate.add_argument("--expected-manifest")
    validate.add_argument("--summary-output")
    validate.set_defaults(func=command_validate_output)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "prepare-test":
        if args.caption_json and not args.vocab_output_root:
            parser.error("--vocab-output-root is required with --caption-json")
        if args.intersection_manifest and not args.intersection_output:
            parser.error("--intersection-output is required with --intersection-manifest")
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
