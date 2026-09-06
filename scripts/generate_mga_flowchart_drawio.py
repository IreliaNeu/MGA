"""Generate the editable Draw.io source for the MGA three-mode workflow."""

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
        {"id": "mga-three-mode", "name": "MGA three-mode workflow"},
    )
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "dx": "1800",
            "dy": "1100",
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
            "pageHeight": "1100",
            "math": "0",
            "shadow": "0",
        },
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})

    styles = {
        "title": (
            "text;html=1;strokeColor=none;fillColor=none;align=center;"
            "verticalAlign=middle;whiteSpace=wrap;rounded=0;fontSize=26;"
            "fontStyle=1;fontFamily=Microsoft YaHei;fontColor=#111827;"
        ),
        "input": (
            "rounded=1;whiteSpace=wrap;html=1;arcSize=12;fillColor=#DBEAFE;"
            "strokeColor=#2563EB;strokeWidth=2;fontColor=#1E3A5F;"
            "fontSize=15;fontFamily=Microsoft YaHei;spacing=10;"
        ),
        "parser": (
            "rounded=1;whiteSpace=wrap;html=1;arcSize=12;fillColor=#E0F2FE;"
            "strokeColor=#0284C7;strokeWidth=2;fontColor=#0C4A6E;"
            "fontSize=15;fontFamily=Microsoft YaHei;spacing=10;"
        ),
        "ov": (
            "rounded=1;whiteSpace=wrap;html=1;arcSize=12;fillColor=#FEF3C7;"
            "strokeColor=#D97706;strokeWidth=2;fontColor=#78350F;"
            "fontSize=15;fontFamily=Microsoft YaHei;spacing=10;"
        ),
        "gt": (
            "rounded=1;whiteSpace=wrap;html=1;arcSize=12;fillColor=#DCFCE7;"
            "strokeColor=#16A34A;strokeWidth=2;fontColor=#14532D;"
            "fontSize=15;fontFamily=Microsoft YaHei;spacing=10;"
        ),
        "hybrid": (
            "rounded=1;whiteSpace=wrap;html=1;arcSize=12;fillColor=#EDE9FE;"
            "strokeColor=#7C3AED;strokeWidth=2;fontColor=#3B0764;"
            "fontSize=15;fontFamily=Microsoft YaHei;spacing=10;"
        ),
        "process": (
            "rounded=1;whiteSpace=wrap;html=1;arcSize=12;fillColor=#F8FAFC;"
            "strokeColor=#475569;strokeWidth=2;fontColor=#0F172A;"
            "fontSize=15;fontFamily=Microsoft YaHei;spacing=10;"
        ),
        "score": (
            "rounded=1;whiteSpace=wrap;html=1;arcSize=12;fillColor=#FCE7F3;"
            "strokeColor=#DB2777;strokeWidth=2;fontColor=#831843;"
            "fontSize=15;fontFamily=Microsoft YaHei;spacing=10;"
        ),
        "output": (
            "rounded=1;whiteSpace=wrap;html=1;arcSize=12;fillColor=#ECFCCB;"
            "strokeColor=#65A30D;strokeWidth=2;fontColor=#365314;"
            "fontSize=15;fontFamily=Microsoft YaHei;spacing=10;"
        ),
        "note": (
            "shape=note;whiteSpace=wrap;html=1;size=18;fillColor=#FEE2E2;"
            "strokeColor=#DC2626;strokeWidth=2;fontColor=#7F1D1D;"
            "fontSize=13;fontFamily=Microsoft YaHei;spacing=8;"
        ),
    }

    def add_vertex(
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

    def add_edge(
        cell_id: str,
        source: str,
        target: str,
        value: str = "",
        *,
        dashed: bool = False,
    ) -> None:
        style = (
            "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;"
            "jettySize=auto;html=1;endArrow=block;endFill=1;"
            "strokeColor=#475569;strokeWidth=2;fontSize=13;"
            "fontFamily=Microsoft YaHei;fontColor=#334155;"
        )
        if dashed:
            style += "dashed=1;dashPattern=6 4;"
        cell = ET.SubElement(
            root,
            "mxCell",
            {
                "id": cell_id,
                "value": value,
                "style": style,
                "edge": "1",
                "parent": "1",
                "source": source,
                "target": target,
            },
        )
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})

    def block(title: str, *lines: str) -> str:
        body = "<br/>".join(html.escape(line) for line in lines)
        return (
            f'<div style="line-height:1.35"><b>{html.escape(title)}</b>'
            f"<br/>{body}</div>"
        )

    add_vertex(
        "title",
        "MGA三模式：双时相图像证据验证流程",
        "title",
        80,
        20,
        1640,
        55,
    )
    add_vertex(
        "caption",
        block("候选变化描述", "Candidate caption"),
        "input",
        60,
        105,
        330,
        80,
    )
    add_vertex(
        "images",
        block("双时相图像", "I₁：T1 image", "I₂：T2 image"),
        "input",
        520,
        105,
        330,
        80,
    )
    add_vertex(
        "labels",
        block("可选语义标注", "Y₁：T1 semantic GT", "Y₂：T2 semantic GT"),
        "input",
        980,
        105,
        350,
        80,
    )
    add_vertex(
        "parser",
        block(
            "Parser与同义词规范化",
            "Caption → atomic claims",
            "cᵢ=(entity, change, location, role)",
        ),
        "parser",
        60,
        235,
        440,
        100,
    )
    add_vertex(
        "claims",
        block(
            "Claim集合",
            "source / target entity",
            "Add / Remove / Modify",
            "location ROI Lℓ",
        ),
        "parser",
        610,
        235,
        420,
        100,
    )

    add_vertex(
        "ov",
        block(
            "MGA-OV",
            "全部实体使用开放词汇证据",
            "Mᵒᵛₑ,t = Grounder(Iₜ, qₑ)",
            "论文定义：变化ROI也应来自图像",
        ),
        "ov",
        40,
        400,
        490,
        155,
    )
    add_vertex(
        "gt",
        block(
            "MGA-GT",
            "全部实体使用语义GT证据",
            "Mᴳᵀₑ,t = 1[Yₜ = yₑ]",
            "作为理想证据上界",
        ),
        "gt",
        650,
        400,
        450,
        155,
    )
    add_vertex(
        "hybrid",
        block(
            "MGA-Hybrid",
            "逐实体选择证据来源",
            "e∈C_ann → GT",
            "e∉C_ann → OV",
        ),
        "hybrid",
        1220,
        400,
        500,
        155,
    )
    add_vertex(
        "masks",
        block(
            "统一实体掩膜接口",
            "{Mₑ,1, Mₑ,2, confidence, backend}",
            "三种模式从此进入同一验证器",
        ),
        "process",
        540,
        625,
        700,
        100,
    )
    add_vertex(
        "delta",
        block(
            "双时相变化掩膜",
            "Aₑ=Mₑ,2 ∩ ¬D₂(Mₑ,1)",
            "Rₑ=Mₑ,1 ∩ ¬D₂(Mₑ,2)",
            "Xₑ=Mₑ,1 ⊕ Mₑ,2",
        ),
        "process",
        60,
        790,
        500,
        155,
    )
    add_vertex(
        "relation",
        block(
            "实体变化关系",
            "Q=D₃(R_source) ∩ D₃(A_target) ∩ Lℓ",
            "S_rel=|Q ∩ G| / |Q|",
            "G：参考或图像变化ROI",
        ),
        "process",
        650,
        790,
        500,
        155,
    )
    add_vertex(
        "components",
        block(
            "Claim级分量",
            "Spatial Support",
            "Temporal Support",
            "Coverage / Context",
            "Verifiability",
        ),
        "score",
        1240,
        790,
        480,
        155,
    )
    add_vertex(
        "status",
        block(
            "三状态判定",
            "Supported：全部可用轴 ≥ 0.60",
            "Contradicted：任一轴 ≤ 0.25",
            "Unverifiable：证据缺失或模糊",
        ),
        "output",
        300,
        1000,
        550,
        120,
    )
    add_vertex(
        "aggregate",
        block(
            "Caption级输出",
            "Faithfulness / Temporal / Coverage",
            "Context Support / Unverifiable Rate",
            "Overall仅作可选汇总",
        ),
        "output",
        970,
        1000,
        550,
        120,
    )
    add_vertex(
        "warning",
        block(
            "当前实现注意",
            "open_vocab_only的实体掩膜来自OV，",
            "但变化ROI仍由Y₁≠Y₂生成，",
            "因此尚非完全annotation-free。",
        ),
        "note",
        40,
        590,
        410,
        130,
    )

    add_edge("e_caption_parser", "caption", "parser")
    add_edge("e_parser_claims", "parser", "claims")
    add_edge("e_claims_ov", "claims", "ov", "OV")
    add_edge("e_claims_gt", "claims", "gt", "GT")
    add_edge("e_claims_hybrid", "claims", "hybrid", "Hybrid")
    add_edge("e_images_ov", "images", "ov")
    add_edge("e_images_hybrid", "images", "hybrid")
    add_edge("e_labels_gt", "labels", "gt")
    add_edge("e_labels_hybrid", "labels", "hybrid")
    add_edge("e_ov_masks", "ov", "masks")
    add_edge("e_gt_masks", "gt", "masks")
    add_edge("e_hybrid_masks", "hybrid", "masks")
    add_edge("e_masks_delta", "masks", "delta")
    add_edge("e_delta_relation", "delta", "relation")
    add_edge("e_relation_components", "relation", "components")
    add_edge("e_components_status", "components", "status")
    add_edge("e_status_aggregate", "status", "aggregate")
    add_edge("e_warning_ov", "warning", "ov", dashed=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(mxfile)
    ET.indent(tree, space="  ")
    tree.write(args.output, encoding="utf-8", xml_declaration=True)
    print(args.output)


if __name__ == "__main__":
    main()
