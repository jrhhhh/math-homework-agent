#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计算 RSI 的私有成绩 g(a)。

对应 plan.md §2.2：

    r_priv_t = score_private(x̂_t)
    g(a)     = mean_t mean_r r_priv_t

本脚本复用 math-solver/bench/engine 的逐案例检查与聚合逻辑，不重新实现评分。
它只做三件事：

1. 读一份或多份 predictions（多份视为多个种子），也支持内存中的 payload；
2. 用 bench 的 evaluate_case / aggregate 算每次运行的报告；
3. 输出 g（0–1）、严重失败数、子集分、脱敏失败摘要与逐运行明细。

“脱敏失败摘要”只含案例 ID、子集、失败检查项与严重码，不含标准答案；
外层智能体可以据此提改写，但看不到私有评分规格。

退出码：0 = 评分完成且满足阈值（若有）；1 = 低于 --min-g 或 --strict-severe；
2 = 输入非法。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCH = REPO_ROOT / "math-solver" / "bench"
sys.path.insert(0, str(BENCH))

from engine.checks import evaluate_case  # noqa: E402
from engine.data import load_dataset_paths, load_predictions  # noqa: E402
from engine.scoring import aggregate  # noqa: E402


class GradeError(RuntimeError):
    """输入或评分过程无法完成。"""


def _mean_or_none(values):
    values = [value for value in values if value is not None]
    return round(mean(values), 4) if values else None


def _failure_summary(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for case in report["cases"]:
        failed = [name for name, check in case["checks"].items()
                  if not check["value"]]
        if failed or case["severe"]:
            rows.append({
                "case_id": case["case_id"],
                "subset": case["subset"],
                "score": case["score"],
                "failed_checks": failed,
                "severe": list(case["severe"]),
            })
    return rows


def evaluate_predictions(predictions: dict[str, dict[str, Any]],
                         payload: dict[str, Any],
                         cases: list[dict[str, Any]],
                         truths: dict[str, dict[str, Any]],
                         config: dict[str, Any],
                         label: str = "") -> dict[str, Any]:
    """对一组内存中的预测评分；不写文件。"""
    arm = payload.get("arm") or "skill_gates"
    case_ids = {case["case_id"] for case in cases}

    results = []
    for case in cases:
        truth = truths.get(case["case_id"])
        if truth is None:
            raise GradeError(f"缺少 ground truth：{case['case_id']}")
        results.append(evaluate_case(case, truth, predictions.get(case["case_id"]),
                                     config, arm))

    report = aggregate(results, config)
    over_budget = sorted(case_id for case_id, item in predictions.items()
                         if item.get("over_budget"))
    cost_total = sum(float((item.get("usage") or {}).get("cost_usd") or 0)
                     for item in predictions.values())
    tokens_total = sum(int((item.get("usage") or {}).get("total_tokens") or 0)
                       for item in predictions.values())
    return {
        "path": label,
        "run_id": payload.get("run_id"),
        "model": payload.get("model"),
        "arm": arm,
        "unmatched_predictions": sorted(set(predictions) - case_ids),
        "over_budget_cases": over_budget,
        "cost_usd_total": round(cost_total, 4),
        "tokens_total": tokens_total,
        "failure_summary": _failure_summary(report),
        "report": report,
    }


def evaluate_run(predictions_path: Path | str,
                 cases: list[dict[str, Any]],
                 truths: dict[str, dict[str, Any]],
                 config: dict[str, Any]) -> dict[str, Any]:
    payload, predictions = load_predictions(predictions_path)
    return evaluate_predictions(predictions, payload, cases, truths, config,
                                label=str(predictions_path))


def _merge_failure_summaries(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for run in runs:
        for row in run["failure_summary"]:
            entry = merged.setdefault(row["case_id"], {
                "case_id": row["case_id"],
                "subset": row["subset"],
                "scores": [],
                "failed_checks": set(),
                "severe": set(),
            })
            entry["scores"].append(row["score"])
            entry["failed_checks"].update(row["failed_checks"])
            entry["severe"].update(row["severe"])
    rows = []
    for case_id in sorted(merged):
        entry = merged[case_id]
        rows.append({
            "case_id": case_id,
            "subset": entry["subset"],
            "score_mean": round(mean(entry["scores"]), 4),
            "failed_checks": sorted(entry["failed_checks"]),
            "severe": sorted(entry["severe"]),
        })
    return rows


def _aggregate_runs(runs: list[dict[str, Any]],
                    case_count: int) -> dict[str, Any]:
    if not runs:
        raise GradeError("至少需要一份 predictions")

    totals = [run["report"]["total"] for run in runs]
    subset_names = sorted({name for run in runs
                           for name in run["report"]["subset_scores"]})
    subset_scores_mean = {
        name: round(mean(run["report"]["subset_scores"][name]
                         for run in runs
                         if name in run["report"]["subset_scores"]), 2)
        for name in subset_names
    }

    severe_failures = [
        {"run_id": run["run_id"], "case_id": item["case_id"], "codes": item["codes"]}
        for run in runs
        for item in run["report"]["severe_failures"]
    ]
    over_budget_cases = sorted({case_id for run in runs
                                for case_id in run["over_budget_cases"]})

    return {
        "g": round(mean(totals) / 100.0, 4),
        "total_mean": round(mean(totals), 2),
        "total_min": round(min(totals), 2),
        "total_max": round(max(totals), 2),
        "case_count": case_count,
        "run_count": len(runs),
        "severe_count_max": max(run["report"]["severe_count"] for run in runs),
        "severe_count_total": sum(run["report"]["severe_count"] for run in runs),
        "severe_failures": severe_failures,
        "over_budget_cases": over_budget_cases,
        "over_budget_count_total": sum(len(run["over_budget_cases"]) for run in runs),
        "cost_usd_total": round(sum(run["cost_usd_total"] for run in runs), 4),
        "tokens_total": sum(run["tokens_total"] for run in runs),
        "answer_accuracy_mean": _mean_or_none(
            run["report"]["answer_accuracy"] for run in runs),
        "status_accuracy_mean": _mean_or_none(
            run["report"]["status_accuracy"] for run in runs),
        "verification_honesty_mean": _mean_or_none(
            run["report"]["verification_honesty"] for run in runs),
        "boundary_accuracy_mean": _mean_or_none(
            run["report"]["boundary_accuracy"] for run in runs),
        "subset_scores_mean": subset_scores_mean,
        "failure_summary": _merge_failure_summaries(runs),
        "runs": [{
            "path": run["path"],
            "run_id": run["run_id"],
            "model": run["model"],
            "arm": run["arm"],
            "total": run["report"]["total"],
            "severe_count": run["report"]["severe_count"],
            "answer_accuracy": run["report"]["answer_accuracy"],
            "status_accuracy": run["report"]["status_accuracy"],
            "verification_honesty": run["report"]["verification_honesty"],
            "boundary_accuracy": run["report"]["boundary_accuracy"],
            "subset_scores": run["report"]["subset_scores"],
            "unmatched_predictions": run["unmatched_predictions"],
            "over_budget_cases": run["over_budget_cases"],
            "cost_usd_total": run["cost_usd_total"],
            "tokens_total": run["tokens_total"],
        } for run in runs],
    }


def grade_payloads(payloads: list[dict[str, Any]],
                   cases_path: Path | str | None = None,
                   truth_path: Path | str | None = None,
                   config_path: Path | str | None = None) -> dict[str, Any]:
    """对内存中的 predictions payload 评分；loop.py 用这个入口。"""
    cases_path = Path(cases_path or BENCH / "cases.jsonl")
    truth_path = Path(truth_path or BENCH / "ground_truth.jsonl")
    config_path = Path(config_path or BENCH / "config.json")

    cases, truths, config = load_dataset_paths(cases_path, truth_path, config_path)
    runs = []
    for payload in payloads:
        if not isinstance(payload.get("predictions"), list):
            raise GradeError("payload 缺少 predictions 数组")
        index = {item["case_id"]: item for item in payload["predictions"]
                 if isinstance(item, dict) and "case_id" in item}
        runs.append(evaluate_predictions(
            index, payload, cases, truths, config,
            label=str(payload.get("run_id") or "")))
    return _aggregate_runs(runs, len(cases))


def grade_paths(predictions_paths: list[Path | str],
                cases_path: Path | str | None = None,
                truth_path: Path | str | None = None,
                config_path: Path | str | None = None) -> dict[str, Any]:
    """对一份或多份 predictions 文件评分。

    多份文件视为同一条轨迹的多个种子：g 取各次总分均值，严重失败取最坏值。
    不在这里做接受判定；接受规则由 loop.py 按预注册的 delta 执行。
    """
    payloads = []
    for path in predictions_paths:
        payload, _ = load_predictions(path)
        payloads.append(payload)
    return grade_payloads(payloads, cases_path, truth_path, config_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="计算 math-solver RSI 的私有成绩 g(a)")
    parser.add_argument("--predictions", nargs="+", required=True,
                        help="一份或多份 predictions JSON（多份视为多个种子）")
    parser.add_argument("--cases", default=str(BENCH / "cases.jsonl"))
    parser.add_argument("--ground-truth", default=str(BENCH / "ground_truth.jsonl"))
    parser.add_argument("--config", default=str(BENCH / "config.json"))
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--min-g", type=float, default=None,
                        help="g 低于此值时退出 1")
    parser.add_argument("--strict-severe", action="store_true",
                        help="存在任何严重失败时退出 1")
    args = parser.parse_args(argv)

    try:
        result = grade_paths(args.predictions, args.cases,
                             args.ground_truth, args.config)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    print(json.dumps({
        "g": result["g"],
        "total_mean": result["total_mean"],
        "total_min": result["total_min"],
        "total_max": result["total_max"],
        "severe_count_max": result["severe_count_max"],
        "over_budget_count_total": result["over_budget_count_total"],
        "cost_usd_total": result["cost_usd_total"],
        "tokens_total": result["tokens_total"],
        "answer_accuracy_mean": result["answer_accuracy_mean"],
        "case_count": result["case_count"],
        "run_count": result["run_count"],
    }, ensure_ascii=False))

    passed = True
    if args.min_g is not None and result["g"] < args.min_g:
        passed = False
    if args.strict_severe and result["severe_count_max"] > 0:
        passed = False
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
