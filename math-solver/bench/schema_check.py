#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cases.jsonl / ground_truth.jsonl 的数据自洽检查。

退出码：0 = 通过；1 = 数据不合格；2 = 输入非法（文件缺失、JSON 坏）。
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

from engine.data import load_json, load_jsonl  # noqa: E402

ALLOWED_ACTIONS = {"solve", "route", "clarify"}
ALLOWED_STATUS = {"solved", "partially_solved", "needs_clarification", "failed"}
ALLOWED_ANSWER_KINDS = {"value_set", "interval_set", "text_forms", "piecewise",
                        "empty_set", "route", "clarify"}
REQUIRED_CASE = {"case_id", "subset", "split", "grade_level", "input",
                 "expected_action", "expected_status", "expected_route", "tags"}
REQUIRED_GT = {"case_id", "answer_check", "required_checks", "required_terms",
               "forbidden_terms", "must_include", "rationale"}
LEAK_KEYS = {"answer_check", "required_checks", "required_terms",
             "forbidden_terms", "must_include", "rationale"}


def err(code, path, message):
    return {"code": code, "path": path, "message": message}


def check_groups(value, path, errors):
    if not isinstance(value, list):
        errors.append(err("E_TYPE", path, "应为数组"))
        return
    for index, group in enumerate(value):
        if not isinstance(group, list) or not group:
            errors.append(err("E_TYPE", f"{path}[{index}]", "应为非空关键词数组"))
            continue
        for item in group:
            if not isinstance(item, str) or not item.strip():
                errors.append(err("E_TYPE", f"{path}[{index}]", "关键词应为非空字符串"))


def check_answer_spec(spec, path, errors):
    kind = spec.get("kind")
    if kind not in ALLOWED_ANSWER_KINDS:
        errors.append(err("E_BAD_ANSWER_KIND", f"{path}.kind", "未知答案类型"))
        return
    if kind == "value_set":
        values = spec.get("values")
        if not isinstance(values, list) or not values:
            errors.append(err("E_TYPE", f"{path}.values", "应为非空数组"))
    elif kind == "interval_set":
        intervals = spec.get("intervals")
        if not isinstance(intervals, list) or not intervals:
            errors.append(err("E_TYPE", f"{path}.intervals", "应为非空数组"))
            return
        for index, item in enumerate(intervals):
            if not isinstance(item, dict):
                errors.append(err("E_TYPE", f"{path}.intervals[{index}]", "应为对象"))
                continue
            if set(item) != {"lo", "hi", "lo_closed", "hi_closed"}:
                errors.append(err("E_FIELDS", f"{path}.intervals[{index}]",
                                  "应恰好含 lo/hi/lo_closed/hi_closed"))
            if not isinstance(item.get("lo_closed"), bool) or not isinstance(item.get("hi_closed"), bool):
                errors.append(err("E_TYPE", f"{path}.intervals[{index}]", "开闭标志应为布尔"))
    elif kind == "text_forms":
        check_groups(spec.get("groups"), f"{path}.groups", errors)
    elif kind == "piecewise":
        cases = spec.get("cases")
        if not isinstance(cases, list) or not cases:
            errors.append(err("E_TYPE", f"{path}.cases", "应为非空数组"))
            return
        for index, item in enumerate(cases):
            if not isinstance(item, dict) or not str(item.get("label", "")).strip():
                errors.append(err("E_TYPE", f"{path}.cases[{index}].label", "分支标签不能为空"))
                continue
            check_groups(item.get("tokens"), f"{path}.cases[{index}].tokens", errors)
    elif kind == "route":
        if not isinstance(spec.get("route_to"), str) or not spec["route_to"].strip():
            errors.append(err("E_TYPE", f"{path}.route_to", "转交目标不能为空"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="math-solver 基准数据自洽检查")
    parser.add_argument("--cases", default=str(BENCH / "cases.jsonl"))
    parser.add_argument("--ground-truth", default=str(BENCH / "ground_truth.jsonl"))
    parser.add_argument("--config", default=str(BENCH / "config.json"))
    args = parser.parse_args(argv)

    try:
        cases = load_jsonl(args.cases)
        truths = load_jsonl(args.ground_truth)
        config = load_json(args.config)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "errors": [err("E_INPUT", "$", str(exc))],
                          "warnings": []}, ensure_ascii=False, indent=2))
        sys.exit(2)

    errors = []
    warnings = []
    subset_weights = config.get("subset_weights") or {}

    if not isinstance(cases, list) or not cases:
        errors.append(err("E_EMPTY", "cases", "案例为空"))
    if not isinstance(truths, list) or not truths:
        errors.append(err("E_EMPTY", "ground_truth", "标准答案为空"))

    case_ids = []
    for index, case in enumerate(cases):
        path = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(err("E_TYPE", path, "应为对象"))
            continue
        missing = REQUIRED_CASE - set(case)
        for key in sorted(missing):
            errors.append(err("E_MISSING_FIELD", f"{path}.{key}", "缺少字段"))
        extra = set(case) & LEAK_KEYS
        for key in sorted(extra):
            errors.append(err("E_LEAK", f"{path}.{key}", "cases 不应包含标准答案字段"))
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(err("E_TYPE", f"{path}.case_id", "应为非空字符串"))
        else:
            case_ids.append(case_id)
        if case.get("subset") not in subset_weights:
            errors.append(err("E_BAD_SUBSET", f"{path}.subset", "不在 config.subset_weights 内"))
        if case.get("split") not in ("development", "test"):
            errors.append(err("E_BAD_SPLIT", f"{path}.split", "应为 development 或 test"))
        if not isinstance(case.get("tags"), list):
            errors.append(err("E_TYPE", f"{path}.tags", "应为数组"))
        action = case.get("expected_action")
        if action not in ALLOWED_ACTIONS:
            errors.append(err("E_BAD_ACTION", f"{path}.expected_action", "非法动作"))
        status = case.get("expected_status")
        route = case.get("expected_route")
        if action == "solve":
            if status not in ALLOWED_STATUS:
                errors.append(err("E_BAD_STATUS", f"{path}.expected_status", "非法状态"))
            if route is not None:
                errors.append(err("E_ROUTE_NOT_NULL", f"{path}.expected_route", "solve 不应有 route"))
        elif action == "route":
            if not isinstance(route, str) or not route:
                errors.append(err("E_MISSING_ROUTE", f"{path}.expected_route", "route 必须指定目标"))
            if status is not None:
                errors.append(err("E_STATUS_NOT_NULL", f"{path}.expected_status", "route 不应有 status"))
        elif action == "clarify":
            if status is not None:
                errors.append(err("E_STATUS_NOT_NULL", f"{path}.expected_status", "clarify 不应有 status"))
        inp = case.get("input")
        if not isinstance(inp, dict) or not str(inp.get("problem", "")).strip():
            errors.append(err("E_BAD_INPUT", f"{path}.input.problem", "题目不能为空"))

    if len(case_ids) != len(set(case_ids)):
        errors.append(err("E_DUP_CASE_ID", "cases", "case_id 重复"))

    truth_ids = []
    case_by_id = {case.get("case_id"): case for case in cases if isinstance(case, dict)}
    for index, truth in enumerate(truths):
        path = f"ground_truth[{index}]"
        if not isinstance(truth, dict):
            errors.append(err("E_TYPE", path, "应为对象"))
            continue
        missing = REQUIRED_GT - set(truth)
        for key in sorted(missing):
            errors.append(err("E_MISSING_FIELD", f"{path}.{key}", "缺少字段"))
        case_id = truth.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(err("E_TYPE", f"{path}.case_id", "应为非空字符串"))
            continue
        truth_ids.append(case_id)
        if case_id not in case_by_id:
            errors.append(err("E_UNKNOWN_CASE", f"{path}.case_id", "没有对应 case"))
            continue
        answer_check = truth.get("answer_check")
        if not isinstance(answer_check, dict):
            errors.append(err("E_TYPE", f"{path}.answer_check", "应为对象"))
        else:
            check_answer_spec(answer_check, f"{path}.answer_check", errors)
            if answer_check.get("kind") == "route":
                if answer_check.get("route_to") != case_by_id[case_id].get("expected_route"):
                    errors.append(err("E_ROUTE_MISMATCH", f"{path}.answer_check.route_to",
                                      "与 case.expected_route 不一致"))
        for key in ("required_checks", "required_terms", "must_include"):
            check_groups(truth.get(key), f"{path}.{key}", errors)
        if case_by_id[case_id].get("expected_action") in ("route", "clarify") and not truth.get("must_include"):
            errors.append(err("E_EMPTY_MUST_INCLUDE", f"{path}.must_include",
                              "转交/澄清案例必须给出必说说明"))
        forbidden = truth.get("forbidden_terms")
        if not isinstance(forbidden, list) or not all(isinstance(item, str) for item in forbidden):
            errors.append(err("E_TYPE", f"{path}.forbidden_terms", "应为字符串数组"))

    if len(truth_ids) != len(set(truth_ids)):
        errors.append(err("E_DUP_CASE_ID", "ground_truth", "case_id 重复"))
    missing_truth = [case_id for case_id in case_ids if case_id not in set(truth_ids)]
    for case_id in missing_truth:
        errors.append(err("E_MISSING_TRUTH", "ground_truth", f"缺少 {case_id}"))
    extra_truth = [case_id for case_id in truth_ids if case_id not in set(case_ids)]
    for case_id in extra_truth:
        errors.append(err("E_EXTRA_TRUTH", "ground_truth", f"多余的 {case_id}"))

    counts = {}
    for case in cases:
        if isinstance(case, dict):
            counts[case.get("subset")] = counts.get(case.get("subset"), 0) + 1

    payload = {
        "ok": not errors,
        "case_count": len(cases),
        "subset_counts": counts,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(0 if not errors else 1)


if __name__ == "__main__":
    main()
