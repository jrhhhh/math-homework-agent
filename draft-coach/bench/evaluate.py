#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Draft Coach 版面习惯基准的评分入口。

用法：
  python3 evaluate.py --predictions predictions/run.json \
      [--out reports/run.json] [--markdown reports/run.md] \
      [--split development validation] [--subset layout_core] \
      [--fail-under 80] [--strict]

输入是**已保存的模型输出**；本脚本不调用任何模型 API。
它会把卡片/分块单重新喂给技能自己的门脚本，并核对 tool_log 声称的退出码。

退出码：
  0 = 报告已生成（未设 --fail-under，或分数达标且未触发 --strict）
  1 = 分数低于 --fail-under，或 --strict 下存在严重失败
  2 = 输入非法
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine.checks import evaluate_case  # noqa: E402
from engine.data import ACTIONS, SPLITS, load_cases, load_config, load_predictions  # noqa: E402
from engine.gates import GateRunner  # noqa: E402
from engine.report import render_markdown  # noqa: E402
from engine.scoring import aggregate  # noqa: E402
from engine.rules_bridge import rules  # noqa: E402


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Score saved draft-coach outputs against the layout benchmark.")
    parser.add_argument("--predictions", required=True,
                        help="predictions JSON file")
    parser.add_argument("--out", help="write the JSON report here")
    parser.add_argument("--markdown", help="write a Markdown report here")
    parser.add_argument("--split", nargs="+", choices=SPLITS,
                        help="only evaluate these splits")
    parser.add_argument("--subset", nargs="+", choices=sorted({
        "layout_core", "evidence_discipline", "partition", "input_modes"}),
        help="only evaluate these subsets")
    parser.add_argument("--fail-under", type=float, default=None,
                        help="exit 1 if the weighted score is below this value")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 if any severe failure is present")
    parser.add_argument("--quiet", action="store_true", help="do not print the summary")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        config = load_config(HERE)
        all_cases = load_cases(HERE)
        cases = load_cases(HERE, splits=args.split, subsets=args.subset)
        payload, predictions = load_predictions(args.predictions)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    if not cases:
        print(json.dumps({"error": "筛选后没有案例"}, ensure_ascii=False),
              file=sys.stderr)
        return 2

    known = {case["case_id"] for case in all_cases}
    orphans = sorted(set(predictions) - known)
    if orphans:
        print(json.dumps({"error": "预测里有未知 case_id", "orphans": orphans},
                         ensure_ascii=False), file=sys.stderr)
        return 2

    runner = GateRunner(config, HERE)
    arm = payload.get("arm")
    results = [evaluate_case(case, predictions.get(case["case_id"]), config, runner,
                             arm=arm)
               for case in cases]

    run_meta = {
        "arm": payload.get("arm"),
        "model": payload.get("model"),
        "run_id": payload.get("run_id"),
        "generated_at": payload.get("generated_at"),
        "predictions_file": str(Path(args.predictions).resolve()),
        "skill_rules": str((HERE.parent / "scripts" / "_rules.py").resolve()),
        "rules_import_ok": bool(rules.DIM_KEYS),
        "splits": args.split or list(SPLITS),
        "subsets": args.subset or sorted(config["subset_weights"]),
    }
    report = aggregate(results, config, run_meta)
    report["results"] = results
    report["benchmark"] = {
        "name": config.get("benchmark"),
        "version": config.get("version"),
        "date": config.get("benchmark_date"),
    }

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    if args.markdown:
        md = Path(args.markdown)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(render_markdown(report, config.get("version", "1.0.0")),
                      encoding="utf-8")

    summary = {
        "score": (report.get("total") or {}).get("score"),
        "hard_pass": report.get("hard_pass"),
        "severe_failure_count": report.get("severe_failure_count"),
        "cases_evaluated": report.get("cases_evaluated"),
        "subsets": {name: data.get("score")
                    for name, data in report.get("subsets", {}).items()},
        "out": str(Path(args.out).resolve()) if args.out else None,
        "markdown": str(Path(args.markdown).resolve()) if args.markdown else None,
    }
    if not args.quiet:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    score = (report.get("total") or {}).get("score")
    if args.fail_under is not None and (score is None or score < args.fail_under):
        return 1
    if args.strict and report.get("severe_failure_count"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
