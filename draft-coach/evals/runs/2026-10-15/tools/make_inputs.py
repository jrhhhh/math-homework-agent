#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_inputs.py — 为一次真实产出生成「生产者可见」的输入文件。

关键：**只写输入，不写任何预期或答案**。cases.jsonl 里的 expected_action /
refuse_reason / subset / category / severity / metrics 一律剥掉；ground_truth.jsonl
整个不读。产出代理只看到学生会给的东西。

  python3 make_inputs.py <evals_dir> <run_dir>
"""

import json
import sys
from pathlib import Path

# 生产者可见的 input 字段（student-visible）
KEEP_INPUT = ("prompt", "problem", "draft", "final_solution", "draft_source",
              "grade_level", "audit_draft", "image_confirmed")


def main(argv):
    evals_dir = Path(argv[1]).resolve()
    run_dir = Path(argv[2]).resolve()
    rows = [json.loads(line) for line in
            (evals_dir / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    out_dir = run_dir / "inputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        payload = {"case_id": row["case_id"]}
        inp = row.get("input") or {}
        for key in KEEP_INPUT:
            if key in inp:
                payload[key] = inp[key]
        if "grade_level" in row and "grade_level" not in payload:
            payload["grade_level"] = row["grade_level"]
        (out_dir / (row["case_id"] + ".json")).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"wrote": len(rows), "dir": str(out_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
