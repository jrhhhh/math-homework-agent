#!/usr/bin/env python3
"""元信息和内容版本检查；不作数学判定或用户授权认证。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def version(problem, solution, grade_level="高中"):
    data = dict(grade_level=grade_level, problem=problem, student_solution=solution)
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def route(packet, problem, solution, grade_level="高中"):
    if not isinstance(packet, dict):
        raise ValueError("handoff必须为JSON对象")
    strings = ("problem_id", "grade_level", "problem", "student_solution", "solution_version")
    for key in strings:
        if not isinstance(packet.get(key), str):
            raise ValueError(key + "必须为字符串")
    if not packet["problem_id"].strip() or not packet["grade_level"].strip():
        raise ValueError("题号和学段不能为空")
    if type(packet.get("protocol_version")) is not int or packet["protocol_version"] != 1:
        raise ValueError("protocol_version必须为整数1")
    if type(packet.get("review_complete")) is not bool:
        raise ValueError("review_complete必须为布尔值")
    enums = {
        "solution_source": ("student", "assistant_repair"),
        "result_status": ("correct", "incorrect", "unknown"),
        "process_status": ("valid", "invalid", "gap", "unknown", "not_provided"),
        "requested_action": ("check", "refine"),
        "feedback_mode": ("process_check", "full_correction", "answer_check", "hint"),
    }
    for key, allowed in enums.items():
        if packet.get(key) not in allowed:
            raise ValueError(key + "的取值非法")
    verification = packet.get("verification")
    if not isinstance(verification, dict):
        raise ValueError("verification必须为对象")
    if verification.get("method") not in ("assistant_review", "independent_review",
                                         "tool_assisted_review", "numeric_only", "none"):
        raise ValueError("verification.method非法")
    unresolved = verification.get("unresolved_items")
    if not isinstance(unresolved, list) or any(not isinstance(x, str) for x in unresolved):
        raise ValueError("unresolved_items必须为字符串数组")
    if not isinstance(verification.get("scope"), str):
        raise ValueError("verification.scope必须为字符串")
    checks = [
        (bool(problem.strip() and solution.strip()), "缺少完整题目或学生过程"),
        (packet["problem"] == problem and packet["student_solution"] == solution
         and packet["grade_level"] == grade_level, "交接原文或学段与当前输入不一致"),
        (packet["solution_version"] == version(problem, solution, grade_level), "解答版本过期"),
        (packet["solution_source"] == "student", "助手修补稿不能冒充学生解答"),
        (packet["result_status"] == "correct", "结论尚未确认为正确"),
        (packet["process_status"] == "valid", "过程未成立或缺少过程"),
        (packet["review_complete"], "尚未完成全部过程核验"),
        (verification["method"] not in ("numeric_only", "none"), "核验方式不足以支持完整过程"),
        (bool(verification["scope"].strip()) and not unresolved, "核验范围为空或仍有待解决事项"),
        (packet["requested_action"] == "refine", "用户未要求优化"),
        (packet["feedback_mode"] != "hint", "保持提示模式，不进入优化"),
    ]
    reasons = [reason for passed, reason in checks if not passed]
    return {"eligible": not reasons, "next_skill": "solution-refiner" if not reasons else None,
            "reasons": reasons,
            "limitation": "仅检查元信息与当前内容版本，不验证数学或真实用户授权"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("version", "route"):
        sub = subs.add_parser(command)
        sub.add_argument("--problem-file", required=True)
        sub.add_argument("--solution-file", required=True)
        sub.add_argument("--grade-level", default="高中")
        if command == "route":
            sub.add_argument("--handoff", required=True)
    args = parser.parse_args()
    try:
        problem = Path(args.problem_file).read_text(encoding="utf-8")
        solution = Path(args.solution_file).read_text(encoding="utf-8")
        if args.command == "version":
            result = {"solution_version": version(problem, solution, args.grade_level)}
            code = 0
        else:
            packet = json.loads(Path(args.handoff).read_text(encoding="utf-8"))
            result = route(packet, problem, solution, args.grade_level)
            code = 0 if result["eligible"] else 1
    except (OSError, UnicodeError, ValueError) as exc:
        result, code = {"error": str(exc)}, 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
