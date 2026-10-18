#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""math-solver 基准评分入口。

用法：
  evaluate.py --predictions predictions/fixtures/oracle.json \
      --out reports/fixtures/oracle.report.json \
      --markdown reports/fixtures/oracle.report.md

退出码：0 = 达标；1 = 低于 --fail-under 或 --strict 下有严重失败；2 = 输入非法。
"""

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))

from engine.checks import evaluate_case  # noqa: E402
from engine.data import load_dataset_paths, load_predictions  # noqa: E402
from engine.report import render_markdown  # noqa: E402
from engine.scoring import aggregate  # noqa: E402


def emit_error(message):
    print(json.dumps({"error": message}, ensure_ascii=False, indent=2))
    sys.exit(2)


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="math-solver 基准评分（不调用模型）")
    parser.add_argument("--predictions", required=True, help="预测 JSON 文件")
    parser.add_argument("--cases", default=str(BENCH / "cases.jsonl"))
    parser.add_argument("--ground-truth", default=str(BENCH / "ground_truth.jsonl"))
    parser.add_argument("--config", default=str(BENCH / "config.json"))
    parser.add_argument("--out", help="JSON 报告路径")
    parser.add_argument("--markdown", help="Markdown 报告路径")
    parser.add_argument("--fail-under", type=float, default=None,
                        help="总分低于此值退出 1；默认取 config.default_fail_under")
    parser.add_argument("--strict", action="store_true",
                        help="存在任何严重失败时退出 1")
    args = parser.parse_args(argv)

    try:
        cases, truths, config = load_dataset_paths(args.cases, args.ground_truth, args.config)
        payload, predictions = load_predictions(args.predictions)
    except Exception as exc:  # noqa: BLE001
        emit_error(f"无法读取输入：{exc}")

    arm = payload.get("arm") or "skill_gates"
    case_ids = {case["case_id"] for case in cases}
    unmatched_predictions = sorted(set(predictions) - case_ids)
    results = []
    for case in cases:
        truth = truths.get(case["case_id"])
        if truth is None:
            emit_error(f"缺少 ground truth：{case['case_id']}")
        results.append(evaluate_case(case, truth, predictions.get(case["case_id"]),
                                     config, arm))

    report = aggregate(results, config)
    fail_under = (args.fail_under if args.fail_under is not None
                  else float(config.get("default_fail_under", 70)))

    meta = {
        "predictions": str(args.predictions),
        "arm": arm,
        "model": payload.get("model"),
        "run_id": payload.get("run_id"),
    }
    report_payload = {
        "benchmark": config.get("benchmark"),
        "version": config.get("version"),
        "run": meta,
        "unmatched_predictions": unmatched_predictions,
        "summary": report,
    }
    if unmatched_predictions:
        print(json.dumps({"warning": "存在未匹配的 case_id",
                          "unmatched": unmatched_predictions}, ensure_ascii=False),
              file=sys.stderr)

    if args.out:
        write_text(args.out, json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n")
    if args.markdown:
        write_text(args.markdown, render_markdown(report, meta) + "\n")

    print(json.dumps({
        "total": report["total"],
        "answer_accuracy": report["answer_accuracy"],
        "status_accuracy": report["status_accuracy"],
        "boundary_accuracy": report["boundary_accuracy"],
        "severe_count": report["severe_count"],
        "case_count": report["case_count"],
    }, ensure_ascii=False))

    passed = report["total"] >= fail_under and (not args.strict or report["severe_count"] == 0)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
