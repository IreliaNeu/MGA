"""Resumable parallel HTTP range downloader with an optional MD5 check."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=32)
    parser.add_argument("--chunk-mib", type=int, default=4)
    parser.add_argument("--retries", type=int, default=8)
    parser.add_argument("--expected-md5")
    args = parser.parse_args()

    with httpx.Client(follow_redirects=True, timeout=60) as client:
        response = client.head(args.url)
        response.raise_for_status()
        total = int(response.headers["content-length"])
        etag = response.headers.get("etag")

    chunk_size = args.chunk_mib * 1024 * 1024
    ranges = [
        (start, min(start + chunk_size, total) - 1)
        for start in range(0, total, chunk_size)
    ]
    state_path = args.output.with_suffix(args.output.suffix + ".parts.json")
    state = load_state(state_path)
    expected_state = {
        "url": args.url,
        "total": total,
        "chunk_size": chunk_size,
        "etag": etag,
    }
    if any(state.get(key) != value for key, value in expected_state.items()):
        state = {**expected_state, "completed": []}
    completed = {int(item) for item in state.get("completed", [])}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor = os.open(args.output, os.O_RDWR | os.O_CREAT)
    os.ftruncate(file_descriptor, total)
    lock = threading.Lock()
    started = time.perf_counter()

    def download(index: int, start: int, end: int) -> int:
        if index in completed:
            return index
        last_error = None
        for attempt in range(args.retries):
            try:
                with httpx.Client(follow_redirects=True, timeout=120) as client:
                    response = client.get(
                        args.url,
                        headers={"Range": f"bytes={start}-{end}"},
                    )
                    if response.status_code != 206:
                        raise RuntimeError(
                            f"expected HTTP 206, got {response.status_code}"
                        )
                    content = response.content
                    expected_length = end - start + 1
                    if len(content) != expected_length:
                        raise RuntimeError(
                            f"expected {expected_length} bytes, got {len(content)}"
                        )
                    os.pwrite(file_descriptor, content, start)
                with lock:
                    completed.add(index)
                    save_state(
                        state_path,
                        {**expected_state, "completed": sorted(completed)},
                    )
                return index
            except Exception as exc:
                last_error = exc
                if attempt + 1 < args.retries:
                    time.sleep(min(2 ** attempt, 20))
        raise RuntimeError(
            f"range {index} ({start}-{end}) failed after retries: {last_error}"
        )

    pending = [
        (index, start, end)
        for index, (start, end) in enumerate(ranges)
        if index not in completed
    ]
    print(
        f"total={total} chunks={len(ranges)} completed={len(completed)} "
        f"pending={len(pending)}",
        flush=True,
    )
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(download, index, start, end): index
            for index, start, end in pending
        }
        for count, future in enumerate(as_completed(futures), start=1):
            future.result()
            if count % 10 == 0 or count == len(futures):
                done_bytes = min(len(completed) * chunk_size, total)
                elapsed = max(time.perf_counter() - started, 1e-6)
                rate = done_bytes / elapsed / (1024 * 1024)
                print(
                    f"completed={len(completed)}/{len(ranges)} "
                    f"bytes={done_bytes}/{total} rate={rate:.2f}MiB/s",
                    flush=True,
                )
    os.close(file_descriptor)

    digest = None
    if args.expected_md5:
        digest = md5(args.output)
        if digest.lower() != args.expected_md5.lower():
            raise RuntimeError(
                f"MD5 mismatch: expected {args.expected_md5}, got {digest}"
            )
    state_path.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "size": total,
                "md5": digest,
                "verified": bool(args.expected_md5),
            }
        )
    )


def load_state(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(path)


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
