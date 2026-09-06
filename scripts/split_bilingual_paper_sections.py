"""Split the MGA bilingual writing draft into clean Chinese and English files."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--zh-output", type=Path, required=True)
    parser.add_argument("--en-output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    text = args.source.read_text(encoding="utf-8")
    zh_marker = "# 中文稿\n"
    en_marker = "# English Draft\n"
    review_marker = "\n---\n\n## 3 反向提纲"

    if zh_marker not in text or en_marker not in text or review_marker not in text:
        raise RuntimeError("Expected bilingual section markers were not found")

    zh_body = text.split(zh_marker, 1)[1].split("\n---\n\n# English Draft", 1)[0]
    en_body = text.split(en_marker, 1)[1].split(review_marker, 1)[0]

    zh_text = (
        "# MGA：面向开放式遥感变化描述的混合证据关联评价框架\n\n"
        "> 中文写作稿 v2；包含七句式摘要、引言与相关工作。\n\n"
        f"{zh_body.strip()}\n"
    )
    en_text = (
        "# MGA: A Hybrid Evidence-Grounded Evaluation Framework for "
        "Open-Ended Remote Sensing Change Descriptions\n\n"
        "> English writing draft v2 with the seven-sentence abstract, "
        "Introduction, and Related Work.\n\n"
        f"{en_body.strip()}\n"
    )

    args.zh_output.parent.mkdir(parents=True, exist_ok=True)
    args.en_output.parent.mkdir(parents=True, exist_ok=True)
    args.zh_output.write_text(zh_text, encoding="utf-8", newline="\n")
    args.en_output.write_text(en_text, encoding="utf-8", newline="\n")
    print(args.zh_output)
    print(args.en_output)


if __name__ == "__main__":
    main()
