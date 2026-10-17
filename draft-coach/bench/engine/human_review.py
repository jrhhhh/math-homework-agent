# -*- coding: utf-8 -*-
"""人工 / 模型辅助评审层的导出与回读。单独统计，不混入自动分。

自动层只能检查「卡片有没有越线、锚点有没有出现、评分是否落在参考集合里」。
它不能回答「这条观察是不是真的」「这条习惯是不是适合这个学生」。
本模块把这些问题显式交给人或独立上下文的评审者。

命令行：
  python3 engine/human_review.py export --predictions RUN.json --out reviews/template.json
  python3 engine/human_review.py merge  --reviews reviews/filled.json --out reviews/summary.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCH_DIR))

from engine.data import load_cases, load_predictions  # noqa: E402
from engine.scoring import rate  # noqa: E402

QUESTIONS = ("observation_faithful", "habit_appropriate", "next_step_usable")


def export_reviews(predictions_path, splits=None, subsets=None):
    _payload, predictions = load_predictions(predictions_path)
    cases = load_cases(BENCH_DIR, splits=splits, subsets=subsets)
    items = []
    for case in cases:
        prediction = predictions.get(case["case_id"])
        if prediction is None:
            continue
        data = case.get("input") or {}
        items.append({
            "case_id": case["case_id"],
            "subset": case["subset"],
            "split": case.get("split"),
            "request": data.get("request"),
            "draft": data.get("draft"),
            "image_note": data.get("image_note"),
            "expected_actions": case.get("expected_actions"),
            "prediction": prediction,
            "automatic_score": None,
            "review": {
                "reviewer": None,
                "reviewed_at": None,
                "observation_faithful": None,
                "habit_appropriate": None,
                "next_step_usable": None,
                "reviewer_note": "",
            },
        })
    return {
        "benchmark": "draft-coach-layout",
        "predictions_file": str(Path(predictions_path).resolve()),
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "instructions": {
            "observation_faithful": "卡片里的观察与证据是否对得上草稿/版面描述？"
                                    "证据只有引用不够，要看观察本身是否属实。",
            "habit_appropriate": "1–3 条习惯是否真的是这个学生下一道题最该改的？"
                                 "不要求面面俱到，但不能抓错重点。",
            "next_step_usable": "next_step 是否只做一件事、下一道题就能执行？",
            "values": "true / false / null；null = 无法判断，不进分母。",
        },
        "items": items,
    }


def merge_reviews(reviews_path):
    payload = json.loads(Path(reviews_path).read_text(encoding="utf-8"))
    items = payload.get("items") or []
    values = {question: [] for question in QUESTIONS}
    by_subset = {}
    disagreements = []
    for item in items:
        review = item.get("review") or {}
        subset = item.get("subset") or "unknown"
        bucket = by_subset.setdefault(subset, {question: [] for question in QUESTIONS})
        for question in QUESTIONS:
            value = review.get(question)
            if value is None:
                continue
            if not isinstance(value, bool):
                raise ValueError("%s 的 %s 必须是布尔值或 null，实为 %r"
                                 % (item.get("case_id"), question, value))
            values[question].append(int(value))
            bucket[question].append(int(value))
        if review.get("reviewer_note"):
            disagreements.append({
                "case_id": item.get("case_id"),
                "note": review.get("reviewer_note"),
            })

    def pack(values_by_question):
        return {question: rate(values_by_question[question])
                for question in QUESTIONS}

    return {
        "action": "human_review_merge",
        "reviews_file": str(Path(reviews_path).resolve()),
        "items": len(items),
        "overall": pack(values),
        "by_subset": {subset: pack(bucket) for subset, bucket in sorted(by_subset.items())},
        "notes": disagreements,
        "capability_note": "人工层单独统计，不并入自动分；"
                           "评审者身份与独立性需由运行者自行记录。",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser("export", help="export a review template")
    p_export.add_argument("--predictions", required=True)
    p_export.add_argument("--out", required=True)
    p_export.add_argument("--split", nargs="+", choices=("development", "validation", "test"))
    p_export.add_argument("--subset", nargs="+",
                          choices=("layout_core", "evidence_discipline", "partition",
                                   "input_modes"))
    p_export.set_defaults(func=cmd_export)

    p_merge = sub.add_parser("merge", help="merge filled reviews")
    p_merge.add_argument("--reviews", required=True)
    p_merge.add_argument("--out", required=True)
    p_merge.set_defaults(func=cmd_merge)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


def cmd_export(args):
    payload = export_reviews(args.predictions, splits=args.split, subsets=args.subset)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"items": len(payload["items"]), "out": str(out)},
                     ensure_ascii=False, indent=2))


def cmd_merge(args):
    summary = merge_reviews(args.reviews)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"items": summary["items"], "out": str(out),
                      "overall": summary["overall"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
