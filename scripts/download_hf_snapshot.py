"""Download a Hugging Face repository snapshot to a deterministic local path."""

from __future__ import annotations

import argparse

from huggingface_hub import snapshot_download


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--local-dir", required=True)
    args = parser.parse_args()
    print(snapshot_download(repo_id=args.repo, local_dir=args.local_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
