#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 tools/data.py 重建 cases.jsonl 与 ground_truth.jsonl。

改案例或标准答案后运行本脚本，再跑 schema_check.py。
"""

import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))

from tools.data import CASES, GROUND_TRUTH  # noqa: E402


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n")


def main():
    cases = []
    for case in CASES:
        clean = {key: value for key, value in case.items() if not key.startswith("_")}
        cases.append(clean)

    truths = []
    for case in CASES:
        case_id = case["case_id"]
        truth = {
            "case_id": case_id,
            "required_checks": [],
            "required_terms": [],
            "forbidden_terms": [],
            "must_include": [],
        }
        truth.update(GROUND_TRUTH[case_id])
        truths.append(truth)

    write_jsonl(BENCH / "cases.jsonl", cases)
    write_jsonl(BENCH / "ground_truth.jsonl", truths)
    print(f"wrote {len(cases)} cases and {len(truths)} ground-truth rows")


if __name__ == "__main__":
    main()
