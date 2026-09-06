"""Download an aligned semantic-change subset without cloning a full Hub repository."""

from __future__ import annotations

import argparse
import concurrent.futures
import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--folders",
        nargs="+",
        default=["T1", "T2", "GT_T1", "GT_T2", "GT_CD"],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tasks = [
        (folder, index, f"{args.split}/{folder}/{index:05d}.png")
        for index in range(args.start, args.start + args.limit)
        for folder in args.folders
    ]
    args.output_root.mkdir(parents=True, exist_ok=True)

    def download(task: tuple[str, int, str]) -> str:
        folder, index, repo_path = task
        cached = hf_hub_download(
            repo_id=args.repo_id,
            repo_type="dataset",
            filename=repo_path,
        )
        destination = (
            args.output_root / args.split / folder / f"{index:05d}.png"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.is_file():
            shutil.copy2(cached, destination)
        return str(destination)

    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        for _ in executor.map(download, tasks):
            completed += 1
            if completed % 100 == 0:
                print(f"downloaded {completed}/{len(tasks)} files", flush=True)
    print(f"downloaded {completed}/{len(tasks)} files into {args.output_root}")


if __name__ == "__main__":
    main()
