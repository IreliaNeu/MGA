"""Resumable aligned semantic-change subset downloader with per-file retries."""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--split", default="train")
    parser.add_argument("--limit", type=int, default=600)
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--retries", type=int, default=6)
    parser.add_argument(
        "--subdirs",
        default="T1,T2,GT_T1,GT_T2,GT_CD",
    )
    args = parser.parse_args()

    subdirs = tuple(item.strip() for item in args.subdirs.split(",") if item.strip())
    repo_files = HfApi().list_repo_files(args.repo_id, repo_type="dataset")
    names = sorted(
        Path(path).name
        for path in repo_files
        if path.startswith(f"{args.split}/{subdirs[0]}/") and path.endswith(".png")
    )[: args.limit]
    requested = [
        f"{args.split}/{subdir}/{name}" for name in names for subdir in subdirs
    ]
    args.output_root.mkdir(parents=True, exist_ok=True)

    def download(path: str) -> tuple[str, str | None]:
        last_error = None
        for attempt in range(args.retries):
            try:
                hf_hub_download(
                    repo_id=args.repo_id,
                    filename=path,
                    repo_type="dataset",
                    local_dir=args.output_root,
                )
                return path, None
            except Exception as exc:  # network backends expose several error types
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt + 1 < args.retries:
                    time.sleep(min(2 ** attempt, 20))
        return path, last_error

    failed = {}
    completed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download, path): path for path in requested}
        for future in as_completed(futures):
            path, error = future.result()
            completed += 1
            if error:
                failed[path] = error
            if completed % 100 == 0 or completed == len(requested):
                print(
                    f"completed {completed}/{len(requested)} files; "
                    f"failed={len(failed)}",
                    flush=True,
                )

    report = {
        "repo_id": args.repo_id,
        "scene_count": len(names),
        "requested_file_count": len(requested),
        "failed_file_count": len(failed),
        "failed": failed,
        "output_root": str(args.output_root),
    }
    report_path = args.output_root / "download_manifest.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in report.items() if key != "failed"}))
    if failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
