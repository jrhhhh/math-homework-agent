#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_output.py — math-solver 输出的结构门。

用法：
  validate --card OUTPUT.json [--strict]

约定：
  - 结果以 JSON 打到 stdout；
  - 退出码：0 = 通过；1 = 结构不合格（--strict 下告警也算不合格）；2 = 输入非法。
  - 仅使用 Python 标准库，无第三方依赖。

能力边界（诚实声明）：
  - 本门只查 JSON 的形状、类型与状态一致性；
  - 它不判断推导在数学上是否正确，也不验证答案是否成立；
  - 它不检查题目是否被正确理解，也不替代宿主的人工复核。
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:  # Windows 控制台默认编码可能是 GBK，统一成 UTF-8
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------- 常量

TOP_FIELDS = ("status", "problem", "plan", "solution", "verification", "teaching_notes")
STATUSES = ("solved", "partially_solved", "needs_clarification", "failed")
VERIFY_STATUSES = ("passed", "failed", "needs_review", "not_fully_verified")
CHECK_STATUSES = ("passed", "failed", "not_applicable", "not_completed")

PROBLEM_FIELDS = ("statement", "topic", "subtopics", "givens", "variables",
                  "constraints", "goal", "requested_method", "ambiguities", "assumptions")
PLAN_FIELDS = ("main_idea", "method", "prerequisites", "steps")
SOLUTION_FIELDS = ("derivation", "answer", "conditions")
DERIVATION_FIELDS = ("step", "expression", "justification")
VERIFICATION_FIELDS = ("status", "checks", "issues")
CHECK_FIELDS = ("name", "status", "details")
TEACHING_FIELDS = ("key_insight", "difficult_steps", "common_mistakes",
                   "prerequisite_explanations", "alternative_method",
                   "follow_up_exercise_suggestion")

CONFIDENCE_RE = re.compile(r"confidence|probab|accuracy|置信|准确率", re.IGNORECASE)


# ---------------------------------------------------------------- 小工具

def err(code, path, message):
    return {"code": code, "path": path, "message": message}


def warn(code, path, message):
    return {"code": code, "path": path, "message": message}


def type_name(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def as_object(value, path, errors):
    if not isinstance(value, dict):
        errors.append(err("E_TYPE", path, f"应为对象，实际为 {type_name(value)}"))
        return None
    return value


def check_exact_fields(obj, expected, path, errors):
    for key in expected:
        if key not in obj:
            errors.append(err("E_MISSING_FIELD", f"{path}.{key}", "缺少必需字段"))
    for key in obj:
        if key not in expected:
            errors.append(err("E_EXTRA_FIELD", f"{path}.{key}", "未声明的字段"))


def check_string(value, path, errors, nullable=False):
    if value is None:
        if not nullable:
            errors.append(err("E_TYPE", path, "不能为 null"))
        return
    if not isinstance(value, str):
        errors.append(err("E_TYPE", path, f"应为字符串，实际为 {type_name(value)}"))
        return
    if not value.strip():
        errors.append(err("E_EMPTY", path, "不能为空字符串"))


def check_string_list(value, path, errors):
    if not isinstance(value, list):
        errors.append(err("E_TYPE", path, f"应为字符串数组，实际为 {type_name(value)}"))
        return
    for index, item in enumerate(value):
        check_string(item, f"{path}[{index}]", errors)


def scan_confidence_keys(value, path, errors):
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str) and CONFIDENCE_RE.search(key):
                errors.append(err("E_CONFIDENCE_FIELD", f"{path}.{key}",
                                  "不添加置信度或概率校准字段"))
            scan_confidence_keys(child, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_confidence_keys(child, f"{path}[{index}]", errors)


# ---------------------------------------------------------------- 分块校验

def validate_problem(value, errors):
    obj = as_object(value, "problem", errors)
    if obj is None:
        return None
    check_exact_fields(obj, PROBLEM_FIELDS, "problem", errors)

    for field in ("statement", "topic", "goal"):
        if field in obj:
            check_string(obj[field], f"problem.{field}", errors)
    for field in ("subtopics", "givens", "variables", "constraints",
                  "ambiguities", "assumptions"):
        if field in obj:
            check_string_list(obj[field], f"problem.{field}", errors)
    if "requested_method" in obj:
        check_string(obj["requested_method"], "problem.requested_method", errors, nullable=True)
    return obj


def validate_plan(value, errors):
    obj = as_object(value, "plan", errors)
    if obj is None:
        return None
    check_exact_fields(obj, PLAN_FIELDS, "plan", errors)

    for field in ("main_idea", "method"):
        if field in obj:
            check_string(obj[field], f"plan.{field}", errors)
    for field in ("prerequisites", "steps"):
        if field in obj:
            check_string_list(obj[field], f"plan.{field}", errors)
    return obj


def validate_derivation(value, errors, warnings):
    if not isinstance(value, list):
        errors.append(err("E_TYPE", "solution.derivation",
                          f"应为对象数组，实际为 {type_name(value)}"))
        return

    steps = []
    all_steps_valid = True
    for index, item in enumerate(value):
        path = f"solution.derivation[{index}]"
        obj = as_object(item, path, errors)
        if obj is None:
            all_steps_valid = False
            continue
        check_exact_fields(obj, DERIVATION_FIELDS, path, errors)

        if "step" in obj:
            step = obj["step"]
            if isinstance(step, bool) or not isinstance(step, int):
                errors.append(err("E_TYPE", f"{path}.step", f"应为整数，实际为 {type_name(step)}"))
                all_steps_valid = False
            elif step < 1:
                errors.append(err("E_BAD_STEP", f"{path}.step", "应为从 1 开始的正整数"))
                all_steps_valid = False
            else:
                steps.append(step)
        else:
            all_steps_valid = False

        for field in ("expression", "justification"):
            if field in obj:
                check_string(obj[field], f"{path}.{field}", errors)

    if all_steps_valid and steps and steps != list(range(1, len(steps) + 1)):
        warnings.append(warn("W_STEP_SEQUENCE", "solution.derivation",
                             "step 建议从 1 开始连续递增，便于下游引用"))


def validate_solution(value, errors, warnings):
    obj = as_object(value, "solution", errors)
    if obj is None:
        return None
    check_exact_fields(obj, SOLUTION_FIELDS, "solution", errors)

    if "derivation" in obj:
        validate_derivation(obj["derivation"], errors, warnings)
    if "answer" in obj:
        check_string(obj["answer"], "solution.answer", errors, nullable=True)
    if "conditions" in obj:
        check_string_list(obj["conditions"], "solution.conditions", errors)
    return obj


def validate_verification(value, errors, warnings):
    obj = as_object(value, "verification", errors)
    if obj is None:
        return None
    check_exact_fields(obj, VERIFICATION_FIELDS, "verification", errors)

    status = obj.get("status")
    if "status" in obj:
        if not isinstance(status, str):
            errors.append(err("E_TYPE", "verification.status",
                              f"应为字符串，实际为 {type_name(status)}"))
        elif status not in VERIFY_STATUSES:
            errors.append(err("E_BAD_VERIFY_STATUS", "verification.status",
                              f"不在允许值内：{', '.join(VERIFY_STATUSES)}"))

    checks = obj.get("checks")
    checks_list = checks if isinstance(checks, list) else []
    if "checks" in obj and not isinstance(checks, list):
        errors.append(err("E_TYPE", "verification.checks",
                          f"应为对象数组，实际为 {type_name(checks)}"))
    for index, item in enumerate(checks_list):
        path = f"verification.checks[{index}]"
        check = as_object(item, path, errors)
        if check is None:
            continue
        check_exact_fields(check, CHECK_FIELDS, path, errors)
        for field in ("name", "details"):
            if field in check:
                check_string(check[field], f"{path}.{field}", errors)
        if "status" in check:
            check_status = check["status"]
            if not isinstance(check_status, str):
                errors.append(err("E_TYPE", f"{path}.status",
                                  f"应为字符串，实际为 {type_name(check_status)}"))
            elif check_status not in CHECK_STATUSES:
                errors.append(err("E_BAD_CHECK_STATUS", f"{path}.status",
                                  f"不在允许值内：{', '.join(CHECK_STATUSES)}"))

    issues = obj.get("issues")
    if "issues" in obj and not isinstance(issues, list):
        errors.append(err("E_TYPE", "verification.issues",
                          f"应为字符串数组，实际为 {type_name(issues)}"))
    elif isinstance(issues, list):
        check_string_list(issues, "verification.issues", errors)

    check_statuses = [c.get("status") for c in checks_list if isinstance(c, dict)]

    if status == "passed":
        if not checks_list:
            errors.append(err("E_PASSED_WITHOUT_CHECKS", "verification.checks",
                              "报 passed 时至少要有实际执行的检查"))
        if "failed" in check_statuses:
            errors.append(err("E_PASSED_WITH_FAILED_CHECK", "verification.checks",
                              "存在 failed 检查时不能报 passed"))
        if "not_completed" in check_statuses:
            errors.append(err("E_PASSED_WITH_INCOMPLETE_CHECK", "verification.checks",
                              "存在 not_completed 检查时不能报 passed"))
        if isinstance(issues, list) and issues:
            errors.append(err("E_PASSED_WITH_ISSUES", "verification.issues",
                              "报 passed 时 issues 必须为空"))
    elif status == "failed" and isinstance(issues, list) and not issues:
        warnings.append(warn("W_FAILED_NO_ISSUES", "verification.issues",
                             "整体报 failed 时，建议在 issues 写清未解决的错误或反例"))

    return obj


def validate_teaching_notes(value, errors):
    obj = as_object(value, "teaching_notes", errors)
    if obj is None:
        return None
    check_exact_fields(obj, TEACHING_FIELDS, "teaching_notes", errors)

    if "key_insight" in obj:
        check_string(obj["key_insight"], "teaching_notes.key_insight", errors)
    for field in ("difficult_steps", "common_mistakes", "prerequisite_explanations"):
        if field in obj:
            check_string_list(obj[field], f"teaching_notes.{field}", errors)
    for field in ("alternative_method", "follow_up_exercise_suggestion"):
        if field in obj:
            check_string(obj[field], f"teaching_notes.{field}", errors, nullable=True)
    return obj


# ---------------------------------------------------------------- 顶层校验

def validate_payload(data):
    errors = []
    warnings = []

    if not isinstance(data, dict):
        errors.append(err("E_ROOT_TYPE", "$", f"顶层应为对象，实际为 {type_name(data)}"))
        return errors, warnings

    check_exact_fields(data, TOP_FIELDS, "$", errors)
    scan_confidence_keys(data, "$", errors)

    status = data.get("status")
    if "status" in data:
        if not isinstance(status, str):
            errors.append(err("E_TYPE", "status", f"应为字符串，实际为 {type_name(status)}"))
        elif status not in STATUSES:
            errors.append(err("E_BAD_STATUS", "status",
                              f"不在允许值内：{', '.join(STATUSES)}"))

    problem = validate_problem(data["problem"], errors) if "problem" in data else None
    if "plan" in data:
        validate_plan(data["plan"], errors)
    solution = validate_solution(data["solution"], errors, warnings) if "solution" in data else None
    verification = validate_verification(data["verification"], errors, warnings) if "verification" in data else None
    if "teaching_notes" in data:
        validate_teaching_notes(data["teaching_notes"], errors)

    # 顶层状态与核验状态的一致性
    verify_status = verification.get("status") if isinstance(verification, dict) else None
    issues = verification.get("issues") if isinstance(verification, dict) else None
    issues = issues if isinstance(issues, list) else []
    ambiguities = problem.get("ambiguities") if isinstance(problem, dict) else None
    ambiguities = ambiguities if isinstance(ambiguities, list) else []
    answer = solution.get("answer") if isinstance(solution, dict) else None
    derivation = solution.get("derivation") if isinstance(solution, dict) else None
    derivation = derivation if isinstance(derivation, list) else []

    if status == "solved":
        if verify_status != "passed":
            errors.append(err("E_STATUS_VERIFY_CONFLICT", "verification.status",
                              "status=solved 要求 verification.status=passed"))
        if issues:
            errors.append(err("E_SOLVED_WITH_ISSUES", "verification.issues",
                              "status=solved 时 issues 必须为空"))
        if not isinstance(answer, str) or not answer.strip():
            errors.append(err("E_SOLVED_WITHOUT_ANSWER", "solution.answer",
                              "status=solved 时 answer 不能为空"))
        if not derivation:
            errors.append(err("E_SOLVED_WITHOUT_DERIVATION", "solution.derivation",
                              "status=solved 时 derivation 不能为空"))
        if ambiguities:
            warnings.append(warn("W_SOLVED_WITH_AMBIGUITIES", "problem.ambiguities",
                                 "存在未解决歧义却报 solved，请确认歧义不影响答案"))
    elif status == "failed":
        if verify_status != "failed":
            errors.append(err("E_STATUS_VERIFY_CONFLICT", "verification.status",
                              "status=failed 要求 verification.status=failed"))
        if not issues:
            warnings.append(warn("W_FAILED_NO_ISSUES", "verification.issues",
                                 "status=failed 时建议写清未解决的错误或反例"))
    elif status == "needs_clarification":
        if verify_status != "needs_review":
            errors.append(err("E_STATUS_VERIFY_CONFLICT", "verification.status",
                              "status=needs_clarification 要求 verification.status=needs_review"))
        if not ambiguities and not issues:
            errors.append(err("E_CLARIFY_WITHOUT_REASON", "problem.ambiguities",
                              "needs_clarification 时 ambiguities 或 issues 不能都为空"))
    elif status == "partially_solved":
        if verify_status == "passed":
            warnings.append(warn("W_PARTIAL_PASSED", "verification.status",
                                 "partially_solved 配 passed 时，请在 conditions 或 issues 写清剩余部分"))

    return errors, warnings


# ---------------------------------------------------------------- CLI

def emit(payload, code):
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(code)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="validate_output.py",
        description="math-solver 输出结构门：只查 JSON 形状与状态一致性，不判断数学正确性。",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="校验一个 math-solver 输出 JSON")
    validate.add_argument("--card", required=True, help="JSON 文件路径；用 - 从 stdin 读取")
    validate.add_argument("--strict", action="store_true", help="告警也视为不合格")
    args = parser.parse_args(argv)

    try:
        if args.card == "-":
            text = sys.stdin.read()
        else:
            text = Path(args.card).read_text(encoding="utf-8")
    except OSError as exc:
        emit({"passed": False, "strict": args.strict, "warnings": [],
              "errors": [err("E_INPUT", args.card, f"无法读取文件：{exc}")],
              "summary": "输入非法"}, 2)
    except UnicodeDecodeError as exc:
        emit({"passed": False, "strict": args.strict, "warnings": [],
              "errors": [err("E_INPUT", args.card, f"不是有效的 UTF-8 文本：{exc}")],
              "summary": "输入非法"}, 2)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        emit({"passed": False, "strict": args.strict, "warnings": [],
              "errors": [err("E_INPUT", args.card,
                             f"JSON 解析失败（第 {exc.lineno} 行第 {exc.colno} 列）：{exc.msg}")],
              "summary": "输入非法"}, 2)

    if not isinstance(data, dict):
        emit({"passed": False, "strict": args.strict, "warnings": [],
              "errors": [err("E_INPUT", args.card,
                             f"顶层必须是 JSON 对象，实际为 {type_name(data)}")],
              "summary": "输入非法"}, 2)

    errors, warnings = validate_payload(data)
    passed = not errors and not (args.strict and warnings)

    if passed:
        summary = "通过" if not warnings else f"通过（有 {len(warnings)} 条告警）"
    else:
        summary = f"未通过：{len(errors)} 个错误、{len(warnings)} 条告警"

    emit({
        "passed": passed,
        "strict": args.strict,
        "errors": errors,
        "warnings": warnings,
        "summary": summary,
    }, 0 if passed else 1)


if __name__ == "__main__":
    main()
