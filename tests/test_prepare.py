from __future__ import annotations

import json
from pathlib import Path

from mga.io import read_jsonl
from mga.prepare import attach_change_agent_texts, convert_feedback_jsonl


def test_convert_feedback_and_attach_change_agent(tmp_path: Path) -> None:
    source = tmp_path / "feedback.jsonl"
    source.write_text(
        json.dumps(
            {
                "id": "levir-cc_test_000001",
                "gt": "there is no difference .",
                "draft": "the two scenes seem identical .",
                "feedback": "A new structure is visible.",
                "refined": "a house appears in the lower-right corner .",
                "status": "Refined (corrective)",
                "Win_caption": "Draft",
                "reason_draft": "The images appear identical.",
                "image_A_path": "images/test/A/test_000001.png",
                "image_B_path": "images/test/B/test_000001.png",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.jsonl"
    count = convert_feedback_jsonl(source, manifest, tmp_path / "masks")
    rows = list(read_jsonl(manifest))

    assert count == 2
    assert [row["model"] for row in rows] == ["Draft", "Guided"]
    assert rows[0]["metadata"]["llm_judge_winner"] == "Draft"
    assert Path(rows[0]["change_mask"]).name == "test_000001.png"

    results = tmp_path / "change_agent"
    results.mkdir()
    (results / "test_000001.txt").write_text("there is no change .", encoding="utf-8")
    combined = tmp_path / "combined.jsonl"
    appended, missing = attach_change_agent_texts(rows, results, combined)
    combined_rows = list(read_jsonl(combined))

    assert appended == 1
    assert missing == []
    assert len(combined_rows) == 3
    assert combined_rows[-1]["model"] == "Change-Agent"
