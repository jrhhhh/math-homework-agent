#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RSI 四份 split 的自洽与防泄漏检查。

目录约定（plan.md §3.3）：

    rsi/splits/
      selection/cases.jsonl + ground_truth.jsonl + manifest.json
      sealed_id/...
      ood/...
      probes/...

检查内容：
- 四份 split 都存在，且每份的 case / ground truth 一一对应；
- case 字段、动作/状态/路由、答案规格与 bench 的 schema 一致；
- 每份 split 内的 `split` 字段与目录名一致；
- 跨 split 的 case_id 与题目输入不重复；
- sealed_id / ood / probes 不得复用现有 bench 的 case_id 或题目；
- 这三份的 manifest 若标 `contaminated: true`，直接判不合格；
- 缺 manifest 只给 warning。

它不验数学，也不判断新题是否真的“未被开发污染”；那需要来源记录与人工复核。

退出码：0 = 通过；1 = 不合格；2 = 输入非法。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCH = REPO_ROOT / "math-solver" / "bench"
sys.path.insert(0, str(BENCH))

from engine.data import load_json, load_jsonl  # noqa: E402
from schema_check import (  # noqa: E402
    ALLOWED_ACTIONS, ALLOWED_STATUS, LEAK_KEYS, REQUIRED_CASE, REQUIRED_GT,
    check_answer_spec, check_groups, err,
)

SPLITS = ("selection", "sealed_id", "ood", "probes")
FRESH_SPLITS = {"sealed_id", "ood", "probes"}


class SplitError(RuntimeError):
    """输入无法读取。"""


def _normalized_input(case: dict[str, Any]) -> str:
    return json.dumps(case.get("input") or {}, ensure_ascii=False, sort_keys=True)


def _load_bench(bench_dir: Path) -> tuple[set[str], set[str], dict[str, Any]]:
    cases = load_jsonl(bench_dir / "cases.jsonl")
    config = load_json(bench_dir / "config.json")
    return ({case["case_id"] for case in cases},
            {_normalized_input(case) for case in cases},
            config)


def _check_manifest(split_dir: Path, name: str,
                    errors: list[dict[str, Any]],
                    warnings: list[dict[str, Any]]) -> None:
    path = split_dir / "manifest.json"
    if not path.is_file():
        warnings.append(err("W_NO_MANIFEST", str(path), "缺少 manifest.json"))
        return
    try:
        manifest = load_json(path)
    except Exception as exc:  # noqa: BLE001
        errors.append(err("E_BAD_MANIFEST", str(path), str(exc)))
        return
    if not isinstance(manifest, dict):
        errors.append(err("E_BAD_MANIFEST", str(path), "manifest 应为对象"))
        return
    if manifest.get("name") != name:
        errors.append(err("E_MANIFEST_NAME", f"{path}.name",
                          f"应写着 {name}"))
    if name in FRESH_SPLITS and manifest.get("contaminated") is True:
        errors.append(err("E_CONTAMINATED", f"{path}.contaminated",
                          f"{name} 必须是未被开发污染的题目"))
    if not str(manifest.get("source") or "").strip():
        warnings.append(err("W_NO_SOURCE", f"{path}.source",
                            "建议写明题目来源"))


def _check_case(case: dict[str, Any], name: str,
                subset_weights: dict[str, Any],
                errors: list[dict[str, Any]]) -> None:
    if not isinstance(case, dict):
        errors.append(err("E_TYPE", f"{name}.cases", "应为对象"))
        return
    path = f"{name}.cases[{case.get('case_id', '?')}]"
    for key in sorted(REQUIRED_CASE - set(case)):
        errors.append(err("E_MISSING_FIELD", f"{path}.{key}", "缺少字段"))
    for key in sorted(set(case) & LEAK_KEYS):
        errors.append(err("E_LEAK", f"{path}.{key}", "cases 不应包含标准答案字段"))

    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not case_id:
        errors.append(err("E_TYPE", f"{path}.case_id", "应为非空字符串"))
    if case.get("split") != name:
        errors.append(err("E_BAD_SPLIT", f"{path}.split",
                          f"应为 {name}，实际 {case.get('split')}"))
    if case.get("subset") not in subset_weights:
        errors.append(err("E_BAD_SUBSET", f"{path}.subset",
                          "不在 bench config.subset_weights 内"))
    if not isinstance(case.get("tags"), list):
        errors.append(err("E_TYPE", f"{path}.tags", "应为数组"))

    action = case.get("expected_action")
    status = case.get("expected_status")
    route = case.get("expected_route")
    if action not in ALLOWED_ACTIONS:
        errors.append(err("E_BAD_ACTION", f"{path}.expected_action", "非法动作"))
    if action == "solve":
        if status not in ALLOWED_STATUS:
            errors.append(err("E_BAD_STATUS", f"{path}.expected_status", "非法状态"))
        if route is not None:
            errors.append(err("E_ROUTE_NOT_NULL", f"{path}.expected_route",
                              "solve 不应有 route"))
    elif action == "route":
        if not isinstance(route, str) or not route:
            errors.append(err("E_MISSING_ROUTE", f"{path}.expected_route",
                              "route 必须指定目标"))
        if status is not None:
            errors.append(err("E_STATUS_NOT_NULL", f"{path}.expected_status",
                              "route 不应有 status"))
    elif action == "clarify":
        if status is not None:
            errors.append(err("E_STATUS_NOT_NULL", f"{path}.expected_status",
                              "clarify 不应有 status"))

    inp = case.get("input")
    if not isinstance(inp, dict) or not str(inp.get("problem", "")).strip():
        errors.append(err("E_BAD_INPUT", f"{path}.input.problem", "题目不能为空"))


def _check_truth(case: dict[str, Any], truth: dict[str, Any],
                 name: str, errors: list[dict[str, Any]]) -> None:
    if not isinstance(truth, dict):
        errors.append(err("E_TYPE", f"{name}.ground_truth", "应为对象"))
        return
    path = f"{name}.ground_truth[{truth.get('case_id', '?')}]"
    for key in sorted(REQUIRED_GT - set(truth)):
        errors.append(err("E_MISSING_FIELD", f"{path}.{key}", "缺少字段"))
    answer_check = truth.get("answer_check")
    if not isinstance(answer_check, dict):
        errors.append(err("E_TYPE", f"{path}.answer_check", "应为对象"))
    else:
        check_answer_spec(answer_check, f"{path}.answer_check", errors)
        if answer_check.get("kind") == "route":
            if answer_check.get("route_to") != case.get("expected_route"):
                errors.append(err("E_ROUTE_MISMATCH",
                                  f"{path}.answer_check.route_to",
                                  "与 case.expected_route 不一致"))
    for key in ("required_checks", "required_terms", "must_include"):
        check_groups(truth.get(key), f"{path}.{key}", errors)
    if case.get("expected_action") in ("route", "clarify") and not truth.get("must_include"):
        errors.append(err("E_EMPTY_MUST_INCLUDE", f"{path}.must_include",
                          "转交/澄清案例必须给出必说说明"))
    forbidden = truth.get("forbidden_terms")
    if not isinstance(forbidden, list) or not all(isinstance(item, str)
                                                  for item in forbidden):
        errors.append(err("E_TYPE", f"{path}.forbidden_terms", "应为字符串数组"))


def validate_split(split_dir: Path, name: str,
                   subset_weights: dict[str, Any],
                   bench_ids: set[str], bench_inputs: set[str]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not split_dir.is_dir():
        return {"name": name, "case_count": 0, "errors": [
            err("E_MISSING_SPLIT", str(split_dir), "缺少该 split 目录")],
            "warnings": warnings}

    cases_path = split_dir / "cases.jsonl"
    truth_path = split_dir / "ground_truth.jsonl"
    if not cases_path.is_file() or not truth_path.is_file():
        return {"name": name, "case_count": 0, "errors": [
            err("E_MISSING_FILE", str(split_dir),
                "需要 cases.jsonl 与 ground_truth.jsonl")], "warnings": warnings}

    try:
        cases = load_jsonl(cases_path)
        truths = load_jsonl(truth_path)
    except Exception as exc:  # noqa: BLE001
        return {"name": name, "case_count": 0, "errors": [
            err("E_INPUT", str(split_dir), str(exc))], "warnings": warnings}

    _check_manifest(split_dir, name, errors, warnings)

    case_by_id: dict[str, dict[str, Any]] = {}
    input_seen: dict[str, str] = {}
    for case in cases:
        _check_case(case, name, subset_weights, errors)
        if not isinstance(case, dict):
            continue
        case_id = case.get("case_id")
        if isinstance(case_id, str):
            if case_id in case_by_id:
                errors.append(err("E_DUP_CASE_ID", f"{name}.cases", case_id))
            case_by_id[case_id] = case
            if name in FRESH_SPLITS and case_id in bench_ids:
                errors.append(err("E_BENCH_OVERLAP", f"{name}.cases.{case_id}",
                                  "不得复用现有 bench 的 case_id"))
        fingerprint = _normalized_input(case)
        if fingerprint in input_seen:
            errors.append(err("E_DUP_INPUT", f"{name}.cases.{case_id}",
                              f"与 {input_seen[fingerprint]} 输入相同"))
        else:
            input_seen[fingerprint] = str(case_id)
        if name in FRESH_SPLITS and fingerprint in bench_inputs:
            errors.append(err("E_BENCH_INPUT_OVERLAP", f"{name}.cases.{case_id}",
                              "题目输入与现有 bench 重复"))

    truth_ids: set[str] = set()
    for truth in truths:
        if not isinstance(truth, dict):
            errors.append(err("E_TYPE", f"{name}.ground_truth", "应为对象"))
            continue
        case_id = truth.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            errors.append(err("E_TYPE", f"{name}.ground_truth.case_id",
                              "应为非空字符串"))
            continue
        if case_id in truth_ids:
            errors.append(err("E_DUP_CASE_ID", f"{name}.ground_truth", case_id))
        truth_ids.add(case_id)
        case = case_by_id.get(case_id)
        if case is None:
            errors.append(err("E_UNKNOWN_CASE", f"{name}.ground_truth.{case_id}",
                              "没有对应 case"))
            continue
        _check_truth(case, truth, name, errors)

    for case_id in sorted(set(case_by_id) - truth_ids):
        errors.append(err("E_MISSING_TRUTH", f"{name}.ground_truth",
                          f"缺少 {case_id}"))
    for case_id in sorted(truth_ids - set(case_by_id)):
        errors.append(err("E_EXTRA_TRUTH", f"{name}.ground_truth",
                          f"多余的 {case_id}"))

    return {
        "name": name,
        "case_count": len(cases),
        "errors": errors,
        "warnings": warnings,
        "case_ids": sorted(case_by_id),
        "inputs": input_seen,
    }


def validate_splits(root: Path | str, bench_dir: Path | str | None = None,
                    require_all: bool = True) -> dict[str, Any]:
    root = Path(root)
    if not root.is_dir():
        raise SplitError(f"split 根目录不存在：{root}")
    bench_dir = Path(bench_dir or BENCH)
    bench_ids, bench_inputs, bench_config = _load_bench(bench_dir)
    subset_weights = bench_config.get("subset_weights") or {}

    results = {}
    splits = {}
    all_errors: list[dict[str, Any]] = []
    all_warnings: list[dict[str, Any]] = []
    for name in SPLITS:
        result = validate_split(root / name, name, subset_weights,
                                bench_ids, bench_inputs)
        results[name] = result
        splits[name] = {key: result[key] for key in
                        ("name", "case_count", "errors", "warnings")}
        all_errors.extend(result["errors"])
        all_warnings.extend(result["warnings"])

    # 跨 split：case_id 与题目输入不得重复。
    seen_ids: dict[str, str] = {}
    seen_inputs: dict[str, str] = {}
    for name in SPLITS:
        result = results[name]
        for case_id in result.get("case_ids") or []:
            if case_id in seen_ids:
                all_errors.append(err("E_CROSS_SPLIT_ID", f"{name}.{case_id}",
                                      f"与 {seen_ids[case_id]} 重复"))
            else:
                seen_ids[case_id] = name
        for fingerprint, case_id in (result.get("inputs") or {}).items():
            if fingerprint in seen_inputs:
                all_errors.append(err("E_CROSS_SPLIT_INPUT", f"{name}.{case_id}",
                                      f"与 {seen_inputs[fingerprint]} 题目重复"))
            else:
                seen_inputs[fingerprint] = f"{name}.{case_id}"

    if require_all:
        for name in SPLITS:
            if splits[name]["case_count"] == 0:
                all_errors.append(err("E_EMPTY_SPLIT", name, "该 split 没有案例"))

    return {
        "ok": not all_errors,
        "root": str(root),
        "splits": splits,
        "errors": all_errors,
        "warnings": all_warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查 RSI 四份 split")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--root", default=str(REPO_ROOT / "rsi" / "splits"))
    validate.add_argument("--bench", default=str(BENCH))
    validate.add_argument("--json-out", default=None)
    args = parser.parse_args(argv)

    if args.command != "validate":
        return 2
    try:
        result = validate_splits(args.root, args.bench)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    print(json.dumps({
        "ok": result["ok"],
        "splits": {name: item["case_count"]
                   for name, item in result["splits"].items()},
        "error_count": len(result["errors"]),
        "warning_count": len(result["warnings"]),
        "errors": result["errors"][:20],
    }, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
