#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""人工评审表导出 / 回读接口。

自动层不判断推导是否优雅、方法是否最优、教学备注是否真的有用。
这里只提供模板与回读；人工分单独统计，不并入自动分。

用法：
  python3 engine/human_review.py export --predictions predictions/fixtures/oracle.json \
      --out reviews/human.template.json
  python3 engine/human_review.py merge --reviews reviews/human.template.json
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

BENCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH))

from engine.data import index_by_id, load_json, load_jsonl  # noqa: E402

SCORE_FIELDS = ("answer_quality", "derivation_quality",
                "method_appropriateness", "teaching_notes_quality")


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def export(args):
    cases = load_jsonl(BENCH / "cases.jsonl")
    payload = load_json(args.predictions)
    predictions = index_by_id(payload.get("predictions") or [])
    reviews = []
    for case in cases:
        prediction = predictions.get(case["case_id"], {})
        output = prediction.get("output")
        reviews.append({
            "case_id": case["case_id"],
            "subset": case["subset"],
            "problem": case["input"]["problem"],
            "model_action": prediction.get("action"),
            "model_answer": ((output or {}).get("solution") or {}).get("answer")
                            if isinstance(output, dict) else prediction.get("reply"),
            **{field: None for field in SCORE_FIELDS},
            "notes": "",
            "reviewer": "",
        })
    write_json(args.out, {
        "benchmark": "math-solver-core",
        "instruction": "四项均填 1–5 分；人工层单独统计，不并入自动分。",
        "run": {"predictions": str(args.predictions),
                "arm": payload.get("arm"), "model": payload.get("model"),
                "run_id": payload.get("run_id")},
        "reviews": reviews,
    })
    print(f"exported {len(reviews)} review rows to {args.out}")


def merge(args):
    payload = load_json(args.reviews)
    reviews = payload.get("reviews") or []
    if not reviews:
        print(json.dumps({"error": "reviews 为空"}, ensure_ascii=False))
        return 2

    incomplete = []
    scores = defaultdict(list)
    for review in reviews:
        case_id = review.get("case_id")
        for field in SCORE_FIELDS:
            value = review.get(field)
            if not isinstance(value, int) or not 1 <= value <= 5:
                incomplete.append(f"{case_id}.{field}")
            else:
                scores[field].append(value)
    if incomplete:
        print(json.dumps({"ok": False, "incomplete": incomplete}, ensure_ascii=False, indent=2))
        return 1

    summary = {field: round(sum(values) / len(values), 2)
               for field, values in scores.items()}
    print(json.dumps({"ok": True, "reviewed": len(reviews), "means": summary},
                     ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="math-solver 人工评审接口")
    sub = parser.add_subparsers(dest="command", required=True)
    export_parser = sub.add_parser("export")
    export_parser.add_argument("--predictions", required=True)
    export_parser.add_argument("--out", required=True)
    merge_parser = sub.add_parser("merge")
    merge_parser.add_argument("--reviews", required=True)
    args = parser.parse_args(argv)

    if args.command == "export":
        export(args)
        return 0
    return merge(args)


if __name__ == "__main__":
    sys.exit(main())
