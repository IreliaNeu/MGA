"""Generate the publication-oriented Draw.io source for MGA's three modes."""

from __future__ import annotations

import argparse
import html
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mxfile = ET.Element(
        "mxfile",
        {
            "host": "Electron",
            "agent": "Codex",
            "version": "27.0.9",
            "type": "device",
        },
    )
    diagram = ET.SubElement(
        mxfile,
        "diagram",
        {"id": "mga-three-mode-v2", "name": "MGA three-mode workflow"},
    )
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "dx": "1800",
            "dy": "1300",
            "grid": "1",
            "gridSize": "10",
            "guides": "1",
            "tooltips": "1",
            "connect": "1",
            "arrows": "1",
            "fold": "1",
            "page": "1",
            "pageScale": "1",
            "pageWidth": "1800",
            "pageHeight": "1320",
            "math": "0",
            "shadow": "0",
        },
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    base = (
        "rounded=1;whiteSpace=wrap;html=1;arcSize=12;strokeWidth=2;"
        "fontSize=15;fontFamily=Microsoft YaHei;spacing=10;"
    )
    styles = {
        "title": (
            "text;html=1;strokeColor=none;fillColor=none;align=center;"
            "verticalAlign=middle;whiteSpace=wrap;fontSize=26;fontStyle=1;"
            "fontFamily=Microsoft YaHei;fontColor=#111827;"
        ),
        "input": base
        + "fillColor=#DBEAFE;strokeColor=#2563EB;fontColor=#1E3A5F;",
        "parser": base
        + "fillColor=#E0F2FE;strokeColor=#0284C7;fontColor=#0C4A6E;",
        "ov": base + "fillColor=#FEF3C7;strokeColor=#D97706;fontColor=#78350F;",
        "gt": base + "fillColor=#DCFCE7;strokeColor=#16A34A;fontColor=#14532D;",
        "hybrid": base
        + "fillColor=#EDE9FE;strokeColor=#7C3AED;fontColor=#3B0764;",
        "process": base
        + "fillColor=#F8FAFC;strokeColor=#475569;fontColor=#0F172A;",
        "score": base + "fillColor=#FCE7F3;strokeColor=#DB2777;fontColor=#831843;",
        "output": base
        + "fillColor=#ECFCCB;strokeColor=#65A30D;fontColor=#365314;",
        "note": (
            "shape=note;whiteSpace=wrap;html=1;size=18;fillColor=#FEE2E2;"
            "strokeColor=#DC2626;strokeWidth=2;fontColor=#7F1D1D;"
            "fontSize=13;fontFamily=Microsoft YaHei;spacing=8;"
        ),
    }

    def block(title: str, *lines: str) -> str:
        body = "<br/>".join(html.escape(line) for line in lines)
        return (
            f'<div style="line-height:1.35"><b>{html.escape(title)}</b>'
            f"<br/>{body}</div>"
        )

    def vertex(
        cell_id: str,
        value: str,
        style: str,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> None:
        cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": cell_id,
                "value": value,
                "style": styles[style],
                "vertex": "1",
                "parent": "1",
            },
        )
        ET.SubElement(
            cell,
            "mxGeometry",
            {
                "x": str(x),
                "y": str(y),
                "width": str(width),
                "height": str(height),
                "as": "geometry",
            },
        )

    def edge(
        cell_id: str,
        source: str,
        target: str,
        *,
        dashed: bool = False,
        exit_point: tuple[float, float] | None = None,
        entry_point: tuple[float, float] | None = None,
    ) -> None:
        style = (
            "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"
            "jettySize=auto;html=1;endArrow=block;endFill=1;"
            "strokeColor=#475569;strokeWidth=2;"
        )
        if dashed:
            style += "dashed=1;dashPattern=6 4;"
        if exit_point:
            style += (
                f"exitX={exit_point[0]};exitY={exit_point[1]};"
                "exitDx=0;exitDy=0;"
            )
        if entry_point:
            style += (
                f"entryX={entry_point[0]};entryY={entry_point[1]};"
                "entryDx=0;entryDy=0;"
            )
        cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": cell_id,
                "style": style,
                "edge": "1",
                "parent": "1",
                "source": source,
                "target": target,
            },
        )
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})

    vertex(
        "title",
        "MGA三模式：双时相图像证据验证流程",
        "title",
        80,
        20,
        1640,
        55,
    )
    vertex(
        "caption",
        block("候选变化描述", "Candidate caption"),
        "input",
        70,
        105,
        480,
        80,
    )
    vertex(
        "images",
        block("双时相图像", "I₁：T1 image", "I₂：T2 image"),
        "input",
        660,
        105,
        480,
        80,
    )
    vertex(
        "labels",
        block("可选语义标注", "Y₁：T1 semantic GT", "Y₂：T2 semantic GT"),
        "input",
        1250,
        105,
        480,
        80,
    )
    vertex(
        "parser_claims",
        block(
            "Parser、同义词规范化与原子命题",
            "Caption → atomic claims",
            "cᵢ=(entity, change, location, role)",
        ),
        "parser",
        70,
        245,
        480,
        105,
    )
    vertex(
        "router",
        block(
            "证据路由",
            "按模式与实体是否属于标注类别集 C_ann，",
            "选择 T1/T2 实体掩膜来源，并确定变化 ROI G",
        ),
        "parser",
        660,
        245,
        1070,
        105,
    )
    vertex(
        "ov",
        block(
            "MGA-OV",
            "全部实体使用开放词汇证据",
            "Mᵒᵛₑ,t = Grounder(Iₜ, qₑ)",
            "Gᵒᵛ = ChangeDetector(I₁, I₂)",
        ),
        "ov",
        40,
        430,
        500,
        150,
    )
    vertex(
        "gt",
        block(
            "MGA-GT",
            "全部实体使用语义 GT 证据",
            "Mᴳᵀₑ,t = 1[Yₜ = yₑ]",
            "Gᴳᵀ = 1[Y₁ ≠ Y₂]（理想证据上界）",
        ),
        "gt",
        650,
        430,
        500,
        150,
    )
    vertex(
        "hybrid",
        block(
            "MGA-Hybrid",
            "逐实体选择证据来源",
            "e∈C_ann → Mᴳᵀ；e∉C_ann → Mᵒᵛ",
            "Gᴴ = 1[Y₁ ≠ Y₂]（当前主实现）",
        ),
        "hybrid",
        1260,
        430,
        500,
        150,
    )
    vertex(
        "masks",
        block(
            "统一证据接口",
            "{Mₑ,1, Mₑ,2, G, confidence, backend}",
            "三种模式进入相同的时序与空间验证逻辑",
        ),
        "process",
        650,
        670,
        500,
        110,
    )
    vertex(
        "delta",
        block(
            "双时相变化掩膜",
            "Aₑ=Mₑ,2 ∩ ¬D₂(Mₑ,1)",
            "Rₑ=Mₑ,1 ∩ ¬D₂(Mₑ,2)",
            "Xₑ=Mₑ,1 ⊕ Mₑ,2",
        ),
        "process",
        40,
        835,
        500,
        155,
    )
    vertex(
        "relation",
        block(
            "实体变化关系",
            "Q=D₃(R_source) ∩ D₃(A_target) ∩ Lℓ",
            "S_rel=|Q ∩ G| / |Q|",
            "G：GT 或图像推断的变化 ROI",
        ),
        "process",
        650,
        835,
        500,
        155,
    )
    vertex(
        "components",
        block(
            "Claim级分量",
            "Spatial Support",
            "Temporal Support",
            "Coverage / Context",
            "Verifiability",
        ),
        "score",
        1260,
        835,
        500,
        155,
    )
    vertex(
        "status",
        block(
            "Claim级判定",
            "Fᵢ=0.65·Spatialᵢ+0.35·Temporalᵢ",
            "Supported：全部可用轴 ≥ 0.60",
            "Contradicted：任一轴 ≤ 0.25",
            "其余/证据缺失：Unverifiable",
        ),
        "output",
        250,
        1050,
        600,
        135,
    )
    vertex(
        "aggregate",
        block(
            "Caption级输出",
            "Faithfulness=meanᵢ(Fᵢ)",
            "Temporal=meanᵢ(Tᵢ)；Coverage=被覆盖变化连通域比例",
            "Context / Unverifiable Rate；Overall仅作可选汇总",
        ),
        "output",
        950,
        1050,
        600,
        135,
    )
    vertex(
        "warning",
        block(
            "实现边界",
            "当前 open_vocab_only 的实体掩膜来自 OV，但 G 仍由 Y₁≠Y₂ 生成；",
            "若声称完全无标注 MGA-OV，须改用图像变化检测器生成 G，或取消 GT-ROI 门控。",
        ),
        "note",
        50,
        1215,
        1690,
        90,
    )

    edge(
        "e_caption_parser",
        "caption",
        "parser_claims",
        exit_point=(0.5, 1),
        entry_point=(0.5, 0),
    )
    edge(
        "e_parser_router",
        "parser_claims",
        "router",
        exit_point=(1, 0.5),
        entry_point=(0, 0.5),
    )
    edge(
        "e_images_router",
        "images",
        "router",
        exit_point=(0.5, 1),
        entry_point=(0.25, 0),
    )
    edge(
        "e_labels_router",
        "labels",
        "router",
        exit_point=(0.5, 1),
        entry_point=(0.8, 0),
    )
    edge(
        "e_router_ov",
        "router",
        "ov",
        exit_point=(0.15, 1),
        entry_point=(0.5, 0),
    )
    edge(
        "e_router_gt",
        "router",
        "gt",
        exit_point=(0.5, 1),
        entry_point=(0.5, 0),
    )
    edge(
        "e_router_hybrid",
        "router",
        "hybrid",
        exit_point=(0.85, 1),
        entry_point=(0.5, 0),
    )
    edge(
        "e_ov_masks",
        "ov",
        "masks",
        exit_point=(0.5, 1),
        entry_point=(0.15, 0),
    )
    edge(
        "e_gt_masks",
        "gt",
        "masks",
        exit_point=(0.5, 1),
        entry_point=(0.5, 0),
    )
    edge(
        "e_hybrid_masks",
        "hybrid",
        "masks",
        exit_point=(0.5, 1),
        entry_point=(0.85, 0),
    )
    edge(
        "e_masks_delta",
        "masks",
        "delta",
        exit_point=(0.15, 1),
        entry_point=(0.5, 0),
    )
    edge(
        "e_masks_relation",
        "masks",
        "relation",
        exit_point=(0.5, 1),
        entry_point=(0.5, 0),
    )
    edge(
        "e_masks_components",
        "masks",
        "components",
        exit_point=(0.85, 1),
        entry_point=(0.5, 0),
    )
    edge(
        "e_delta_components",
        "delta",
        "components",
        dashed=True,
        exit_point=(1, 0.3),
        entry_point=(0, 0.3),
    )
    edge(
        "e_relation_components",
        "relation",
        "components",
        exit_point=(1, 0.7),
        entry_point=(0, 0.7),
    )
    edge(
        "e_components_status",
        "components",
        "status",
        exit_point=(0.35, 1),
        entry_point=(0.7, 0),
    )
    edge(
        "e_components_aggregate",
        "components",
        "aggregate",
        exit_point=(0.65, 1),
        entry_point=(0.5, 0),
    )
    edge(
        "e_status_aggregate",
        "status",
        "aggregate",
        exit_point=(1, 0.5),
        entry_point=(0, 0.5),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(mxfile)
    ET.indent(tree, space="  ")
    tree.write(args.output, encoding="utf-8", xml_declaration=True)
    print(args.output)


if __name__ == "__main__":
    main()
