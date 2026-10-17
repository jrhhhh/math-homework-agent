#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 tools/data_*.py 里的案例写成 cases.jsonl 与 ground_truth.jsonl。

数据文件是交付物；本脚本是重建入口。改案例时改 data_*.py，再跑：

    python3 tools/build_dataset.py

只使用标准库。
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))

import data_evidence  # noqa: E402
import data_input  # noqa: E402
import data_layout  # noqa: E402
import data_partition  # noqa: E402

# 只评正面能力：boundary / adversarial 两套越界与拒绝案例不进入基准。
MODULES = (data_layout, data_evidence, data_partition, data_input)


def collect():
    cases, truth = [], []
    seen = set()
    for module in MODULES:
        for case_row, gt_row in module.CASES:
            case_id = case_row["case_id"]
            if case_id in seen:
                raise SystemExit("重复的 case_id：%s" % case_id)
            seen.add(case_id)
            cases.append(case_row)
            truth.append(gt_row)
    return cases, truth


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    cases, truth = collect()
    write_jsonl(BENCH / "cases.jsonl", cases)
    write_jsonl(BENCH / "ground_truth.jsonl", truth)
    print(json.dumps({
        "cases": len(cases),
        "ground_truth": len(truth),
        "subsets": {
            subset: sum(1 for row in cases if row["subset"] == subset)
            for subset in sorted({row["subset"] for row in cases})
        },
        "splits": {
            split: sum(1 for row in cases if row["split"] == split)
            for split in sorted({row["split"] for row in cases})
        },
        "outputs": [str(BENCH / "cases.jsonl"), str(BENCH / "ground_truth.jsonl")],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
