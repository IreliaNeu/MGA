"""Apply the final evidence-scope wording to the bilingual paper draft."""

from __future__ import annotations

import argparse
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    text = args.document.read_text(encoding="utf-8")
    replacements = {
        (
            "**MGA-OV** 是开放视觉证据压力测试：用于衡量在缺少可靠语义标签时，"
            "开放词汇后端的能力下界及失败模式。"
        ): (
            "**MGA-OV** 是开放实体证据压力测试：受控实验固定变化 ROI 以隔离实体 "
            "Grounder 的误差，因此当前结果不等同于完全无标注部署。"
        ),
        "明显高于 MGA-OV 的 0.580": (
            "明显高于 MGA-OV 实体证据基线的 0.580"
        ),
        "显著高于 MGA-OV 的 0.580 ROC-AUC": (
            "显著高于 MGA-OV 实体证据基线的 0.580 ROC-AUC"
        ),
        (
            "MGA-OV 使用开放词汇实体证据，作为缺少可靠类别标签时的压力测试；"
            "主方法 MGA-Hybrid"
        ): (
            "MGA-OV 使用开放词汇实体证据，作为视觉后端压力测试；主方法 "
            "MGA-Hybrid"
        ),
        (
            "标签外类别使用开放词汇掩膜。三种模式共享同一验证器"
        ): (
            "标签外类别使用开放词汇掩膜。为隔离实体 Grounder 的影响，当前受控 "
            "MGA-OV 实验固定使用语义变化 ROI，因此它不是完全无标注的部署配置。"
            "三种模式共享同一验证器"
        ),
        "substantially outperforming MGA-OV at 0.580": (
            "substantially outperforming the MGA-OV entity-evidence baseline at 0.580"
        ),
        (
            "MGA-OV uses open-vocabulary entity evidence as a stress test when "
            "reliable class labels are unavailable; and the proposed MGA-Hybrid"
        ): (
            "MGA-OV uses open-vocabulary entity evidence as a visual-backend stress "
            "test; and the proposed MGA-Hybrid"
        ),
        (
            "open-vocabulary masks for unannotated entities. Rather than forcing"
        ): (
            "open-vocabulary masks for unannotated entities. To isolate entity "
            "grounding, the current controlled MGA-OV experiment holds the semantic "
            "change ROI fixed and is not a fully annotation-free deployment setting. "
            "Rather than forcing"
        ),
    }
    for old, new in replacements.items():
        count = text.count(old)
        if count == 0:
            raise RuntimeError(f"Expected text not found: {old[:80]}")
        text = text.replace(old, new)
    args.document.write_text(text, encoding="utf-8", newline="\n")
    print(args.document)


if __name__ == "__main__":
    main()
