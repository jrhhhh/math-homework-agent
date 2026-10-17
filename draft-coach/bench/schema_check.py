#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 cases.jsonl / ground_truth.jsonl 的结构、对齐与防泄漏。

退出码：0 = 通过 · 1 = 有完整性问题 · 2 = 文件读不了或 JSON 非法。

它不验证数学，也不验证案例是否「像真实学生草稿」；只查数据自洽。
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import rules_bridge as rb  # noqa: E402
from engine.checks import CHECK_NAMES  # noqa: E402
from engine.data import (ACTIONS, SPLITS, load_config, read_jsonl,  # noqa: E402
                         CASES_FILE, GROUND_TRUTH_FILE)

CASE_FIELDS = {
    "case_id", "subset", "split", "difficulty", "category", "grade_level",
    "input", "expected_actions", "acceptable_refusal_reasons", "refuse_reason",
    "severity", "provenance",
}
INPUT_FIELDS = {
    "request", "draft", "draft_source", "has_problem_statement",
    "audit_draft", "image_note",
}
GT_FIELDS = {"case_id", "branches", "notes"}
ANALYZE_FIELDS = {
    "branch", "scope_groups", "scope_forbidden", "dimensions",
    "require_positive", "positive_groups", "positive_text", "habits",
    "next_step", "require_strength", "strength_terms", "forbidden",
    "draft_source", "grade_level", "structure_warnings_allowed",
    "audit_warnings_allowed", "ocr_check",
}
PARTITION_FIELDS = {
    "branch", "block_count_range", "true_problem_range", "max_range_width",
    "required_block_source", "uncertainty_groups", "limitations_must",
    "must_mention_groups", "require_non_high_confidence", "forbidden",
    "oracle",
}
REFUSE_FIELDS = {"branch", "refusal_reason", "message_groups", "forbidden"}
CLARIFY_FIELDS = {"branch", "ask_groups", "forbidden", "oracle_reply"}
ORACLE_FIELDS = {"blocks", "estimated", "count_range", "confidences",
                 "uncertainty", "confirmation_question", "limitations"}

SEVERITY = {"normal", "hard"}


def error(errors, code, case_id, detail):
    errors.append({"code": code, "case_id": case_id, "detail": detail})


def check_case(case, errors):
    case_id = case.get("case_id")
    if set(case) - CASE_FIELDS:
        error(errors, "E_EXTRA_CASE_FIELD", case_id,
              "多余字段：%s" % sorted(set(case) - CASE_FIELDS))
    for field in ("case_id", "subset", "split", "difficulty", "category",
                  "grade_level", "input", "expected_actions", "severity",
                  "provenance"):
        if field not in case:
            error(errors, "E_MISSING_CASE_FIELD", case_id, "缺少 %s" % field)
    if not isinstance(case.get("case_id"), str):
        error(errors, "E_BAD_CASE_ID", case_id, "case_id 必须是字符串")
    elif case_id and case_id != case_id.upper():
        error(errors, "E_BAD_CASE_ID", case_id, "case_id 建议使用大写")
    if case.get("split") not in SPLITS:
        error(errors, "E_BAD_SPLIT", case_id, "split=%r" % case.get("split"))
    if case.get("severity") not in SEVERITY:
        error(errors, "E_BAD_SEVERITY", case_id, "severity=%r" % case.get("severity"))

    data = case.get("input")
    if not isinstance(data, dict):
        error(errors, "E_BAD_INPUT", case_id, "input 必须是对象")
        return
    if set(data) - INPUT_FIELDS:
        error(errors, "E_EXTRA_INPUT_FIELD", case_id,
              "多余字段：%s" % sorted(set(data) - INPUT_FIELDS))
    if data.get("draft_source") not in rb.rules.SOURCES:
        error(errors, "E_BAD_DRAFT_SOURCE", case_id,
              "draft_source=%r" % data.get("draft_source"))
    if not isinstance(data.get("draft"), str):
        error(errors, "E_BAD_DRAFT", case_id, "draft 必须是字符串")
    if not isinstance(data.get("request"), str) or not data.get("request").strip():
        error(errors, "E_BAD_REQUEST", case_id, "request 必须非空")

    actions = case.get("expected_actions")
    if not isinstance(actions, list) or not actions:
        error(errors, "E_BAD_ACTIONS", case_id, "expected_actions 必须是非空数组")
    elif any(action not in ACTIONS for action in actions):
        error(errors, "E_BAD_ACTION", case_id, "未知动作：%s" % actions)
    if "analyze" in (actions or []):
        if not (data.get("draft") or "").strip() and not (data.get("image_note") or "").strip():
            error(errors, "E_ANALYZE_WITHOUT_INPUT", case_id,
                  "analyze 案例既没有草稿文字也没有版面描述")
    if case.get("refuse_reason") is not None \
            and case.get("refuse_reason") not in rb.REFUSALS:
        error(errors, "E_BAD_REFUSE_REASON", case_id,
              "refuse_reason=%r" % case.get("refuse_reason"))
    if "refuse" not in (actions or []) and case.get("refuse_reason") is not None:
        error(errors, "E_REFUSE_REASON_WITHOUT_REFUSE", case_id,
              "非 refuse 案例不应有 refuse_reason")
    accepted = case.get("acceptable_refusal_reasons") or []
    if any(reason not in rb.REFUSALS for reason in accepted):
        error(errors, "E_BAD_ACCEPTED_REASON", case_id,
              "acceptable_refusal_reasons=%s" % accepted)
    if "refuse" in (actions or []) and not accepted \
            and case.get("refuse_reason") not in rb.REFUSALS:
        error(errors, "E_NO_ACCEPTED_REASON", case_id,
              "refuse 案例必须给 refuse_reason，或列出 acceptable_refusal_reasons")


def check_analyze(case_id, gold, errors):
    if set(gold) - ANALYZE_FIELDS:
        error(errors, "E_EXTRA_ANALYZE_FIELD", case_id,
              "多余字段：%s" % sorted(set(gold) - ANALYZE_FIELDS))
    if not gold.get("scope_groups"):
        error(errors, "E_NO_SCOPE_GROUPS", case_id, "scope_groups 不能为空")
    dimensions = gold.get("dimensions")
    if not isinstance(dimensions, dict) or set(dimensions) != set(rb.DIM_KEYS):
        error(errors, "E_BAD_DIMENSIONS", case_id,
              "dimensions 必须恰好包含六个固定键")
    else:
        for key, dim in dimensions.items():
            if not isinstance(dim, dict):
                error(errors, "E_BAD_DIM", case_id, "%s 不是对象" % key)
                continue
            scores = dim.get("acceptable_scores")
            if not isinstance(scores, list) or not scores:
                error(errors, "E_BAD_SCORES", case_id, "%s 缺少可接受评分" % key)
            elif any(score not in rb.SCORES_ANY for score in scores):
                error(errors, "E_BAD_SCORE", case_id, "%s 评分越界：%s" % (key, scores))
            groups = dim.get("evidence_groups")
            if not isinstance(groups, list) or not groups:
                error(errors, "E_NO_EVIDENCE_GROUPS", case_id,
                      "%s 没有证据锚点组" % key)
            else:
                for group in groups:
                    if not isinstance(group, list) or not group \
                            or any(not isinstance(alt, str) or not alt.strip()
                                   for alt in group):
                        error(errors, "E_BAD_EVIDENCE_GROUP", case_id,
                              "%s 的锚点组必须是非空字符串数组" % key)
            if scores == [rb.UNAVAILABLE] and not dim.get("unavailable_reason"):
                error(errors, "E_NO_UNAVAILABLE_REASON", case_id,
                      "%s 只允许不适用，必须写 unavailable_reason" % key)
    habits = gold.get("habits")
    if not isinstance(habits, list) or not 1 <= len(habits) <= 3:
        error(errors, "E_BAD_HABITS", case_id, "habits 必须是 1–3 条")
    else:
        for index, habit in enumerate(habits, 1):
            if not isinstance(habit, dict):
                error(errors, "E_BAD_HABIT", case_id, "第 %d 条习惯不是对象" % index)
                continue
            for field in ("name", "any", "habit", "impact", "training"):
                if field not in habit:
                    error(errors, "E_MISSING_HABIT_FIELD", case_id,
                          "第 %d 条习惯缺少 %s" % (index, field))
            if not habit.get("any"):
                error(errors, "E_EMPTY_HABIT_ANY", case_id,
                      "第 %d 条习惯没有覆盖关键词" % index)
    if gold.get("require_positive") and not gold.get("positive_groups"):
        error(errors, "E_NO_POSITIVE_GROUPS", case_id,
              "require_positive=True 但没有 positive_groups")
    if gold.get("require_strength") and not gold.get("strength_terms"):
        error(errors, "E_NO_STRENGTH_TERMS", case_id,
              "require_strength=True 但没有 strength_terms")
    for field in ("scope_forbidden", "strength_terms", "forbidden"):
        value = gold.get(field) or []
        if not isinstance(value, list) or any(not isinstance(item, str)
                                              for item in value):
            error(errors, "E_BAD_TERM_LIST", case_id, "%s 必须是字符串数组" % field)
    if gold.get("draft_source") not in rb.rules.SOURCES:
        error(errors, "E_BAD_DRAFT_SOURCE", case_id,
              "gold draft_source=%r" % gold.get("draft_source"))
    if gold.get("grade_level") not in rb.rules.GRADES:
        error(errors, "E_BAD_GRADE", case_id, "gold grade_level=%r"
              % gold.get("grade_level"))
    for code in gold.get("audit_warnings_allowed") or []:
        if not str(code).startswith("W_"):
            error(errors, "E_BAD_ALLOWED_WARNING", case_id,
                  "audit_warnings_allowed 只能放 W_*：%s" % code)


def check_partition(case_id, gold, errors):
    if set(gold) - PARTITION_FIELDS:
        error(errors, "E_EXTRA_PARTITION_FIELD", case_id,
              "多余字段：%s" % sorted(set(gold) - PARTITION_FIELDS))
    block_range = gold.get("block_count_range")
    if not isinstance(block_range, list) or len(block_range) != 2 \
            or not all(isinstance(value, int) for value in block_range) \
            or not 1 <= block_range[0] <= block_range[1] <= 12:
        error(errors, "E_BAD_BLOCK_RANGE", case_id, "block_count_range=%r" % block_range)
    true_range = gold.get("true_problem_range")
    if not isinstance(true_range, list) or len(true_range) != 2 \
            or not all(isinstance(value, int) for value in true_range) \
            or not 1 <= true_range[0] <= true_range[1]:
        error(errors, "E_BAD_TRUE_RANGE", case_id, "true_problem_range=%r" % true_range)
    if not isinstance(gold.get("max_range_width"), int) \
            or gold.get("max_range_width") < 0:
        error(errors, "E_BAD_MAX_WIDTH", case_id, "max_range_width 必须是非负整数")
    if gold.get("required_block_source") not in rb.rules.PARTITION_SOURCES:
        error(errors, "E_BAD_BLOCK_SOURCE", case_id,
              "required_block_source=%r" % gold.get("required_block_source"))
    oracle = gold.get("oracle")
    if not isinstance(oracle, dict):
        error(errors, "E_NO_ORACLE", case_id, "partition 缺少 oracle")
    else:
        if set(oracle) - ORACLE_FIELDS:
            error(errors, "E_EXTRA_ORACLE_FIELD", case_id,
                  "oracle 多余字段：%s" % sorted(set(oracle) - ORACLE_FIELDS))
        blocks = oracle.get("blocks")
        estimated = oracle.get("estimated")
        count_range = oracle.get("count_range")
        confidences = oracle.get("confidences")
        if not isinstance(blocks, int) or not 1 <= blocks <= 12:
            error(errors, "E_BAD_ORACLE_BLOCKS", case_id, "oracle.blocks=%r" % blocks)
        if not isinstance(estimated, int) or not 1 <= estimated <= (blocks or 12):
            error(errors, "E_BAD_ORACLE_ESTIMATE", case_id,
                  "oracle.estimated=%r" % estimated)
        if not isinstance(count_range, list) or len(count_range) != 2 \
                or not all(isinstance(value, int) for value in count_range):
            error(errors, "E_BAD_ORACLE_RANGE", case_id,
                  "oracle.count_range=%r" % count_range)
        elif not (1 <= count_range[0] <= estimated <= count_range[1] <= (blocks or 12)):
            error(errors, "E_ORACLE_RANGE_MISMATCH", case_id,
                  "oracle 范围与估计值/块数不自洽：%r / %r / %r"
                  % (count_range, estimated, blocks))
        if not isinstance(confidences, list) or len(confidences) != (blocks or 0) \
                or any(value not in ("高", "中", "低") for value in confidences):
            error(errors, "E_BAD_ORACLE_CONFIDENCES", case_id,
                  "oracle.confidences=%r" % confidences)
        for field in ("uncertainty", "confirmation_question"):
            if not isinstance(oracle.get(field), str) or not oracle.get(field).strip():
                error(errors, "E_EMPTY_ORACLE_FIELD", case_id,
                      "oracle.%s 必须非空" % field)
        limitations = oracle.get("limitations")
        if not isinstance(limitations, list) or not limitations:
            error(errors, "E_EMPTY_ORACLE_FIELD", case_id,
                  "oracle.limitations 必须非空")


def check_refuse(case_id, gold, errors):
    if set(gold) - REFUSE_FIELDS:
        error(errors, "E_EXTRA_REFUSE_FIELD", case_id,
              "多余字段：%s" % sorted(set(gold) - REFUSE_FIELDS))
    if gold.get("refusal_reason") not in rb.REFUSALS:
        error(errors, "E_BAD_REFUSE_REASON", case_id,
              "refusal_reason=%r" % gold.get("refusal_reason"))
    if not gold.get("message_groups"):
        error(errors, "E_NO_MESSAGE_GROUPS", case_id, "message_groups 不能为空")


def check_clarify(case_id, gold, errors):
    if set(gold) - CLARIFY_FIELDS:
        error(errors, "E_EXTRA_CLARIFY_FIELD", case_id,
              "多余字段：%s" % sorted(set(gold) - CLARIFY_FIELDS))
    if not gold.get("ask_groups"):
        error(errors, "E_NO_ASK_GROUPS", case_id, "ask_groups 不能为空")
    if not isinstance(gold.get("oracle_reply"), str) or not gold.get("oracle_reply").strip():
        error(errors, "E_EMPTY_ORACLE_REPLY", case_id, "oracle_reply 必须非空")


def check_truth(case, truth, errors):
    case_id = case.get("case_id")
    branches = truth.get("branches")
    if not isinstance(branches, dict) or not branches:
        error(errors, "E_NO_BRANCHES", case_id, "branches 必须是非空对象")
        return
    if set(branches) != set(case.get("expected_actions") or []):
        error(errors, "E_BRANCH_MISMATCH", case_id,
              "branches=%s / expected_actions=%s"
              % (sorted(branches), sorted(case.get("expected_actions") or [])))
    for name, gold in branches.items():
        if not isinstance(gold, dict) or gold.get("branch") != name:
            error(errors, "E_BAD_BRANCH", case_id, "%s 分支不合法" % name)
            continue
        if name == "analyze":
            check_analyze(case_id, gold, errors)
            data = case.get("input") or {}
            if gold.get("draft_source") != data.get("draft_source"):
                error(errors, "E_GOLD_SOURCE_MISMATCH", case_id,
                      "gold draft_source=%r / 案例=%r"
                      % (gold.get("draft_source"), data.get("draft_source")))
            if gold.get("grade_level") != case.get("grade_level"):
                error(errors, "E_GOLD_GRADE_MISMATCH", case_id,
                      "gold grade_level=%r / 案例=%r"
                      % (gold.get("grade_level"), case.get("grade_level")))
        elif name == "partition":
            check_partition(case_id, gold, errors)
        elif name == "refuse":
            check_refuse(case_id, gold, errors)
        elif name == "clarify":
            check_clarify(case_id, gold, errors)
        else:
            error(errors, "E_UNKNOWN_BRANCH", case_id, name)


def main():
    try:
        config = load_config(HERE)
        cases = read_jsonl(HERE / CASES_FILE)
        truth = read_jsonl(HERE / GROUND_TRUTH_FILE)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

    errors = []
    if len(cases) != len(truth):
        error(errors, "E_LENGTH_MISMATCH", None,
              "cases=%d / ground_truth=%d" % (len(cases), len(truth)))
    if len(cases) < 20:
        error(errors, "E_TOO_FEW_CASES", None, "案例数少于 20：%d" % len(cases))

    ids = [case.get("case_id") for case in cases]
    if len(ids) != len(set(ids)):
        error(errors, "E_DUPLICATE_CASE_ID", None, "case_id 有重复")
    if [row.get("case_id") for row in truth] != ids:
        error(errors, "E_ORDER_MISMATCH", None,
              "ground_truth 的 case_id 必须与 cases 同集同序")

    weights = config.get("subset_weights") or {}
    if sum(weights.values()) != 100:
        error(errors, "E_WEIGHTS_NOT_100", None,
              "subset_weights 之和为 %s" % sum(weights.values()))
    missing_weights = [name for name in CHECK_NAMES
                       if name not in (config.get("check_weights") or {})]
    if missing_weights:
        error(errors, "E_MISSING_CHECK_WEIGHT", None,
              "缺少检查权重：%s" % missing_weights)

    for case, truth_row in zip(cases, truth):
        check_case(case, errors)
        if case.get("case_id") != truth_row.get("case_id"):
            error(errors, "E_ORDER_MISMATCH", case.get("case_id"), "两份文件不对齐")
            continue
        if set(truth_row) - GT_FIELDS:
            error(errors, "E_EXTRA_GT_FIELD", case.get("case_id"),
                  "多余字段：%s" % sorted(set(truth_row) - GT_FIELDS))
        check_truth(case, truth_row, errors)
        if case.get("subset") not in weights:
            error(errors, "E_UNKNOWN_SUBSET", case.get("case_id"),
                  "subset=%r 不在 config 权重里" % case.get("subset"))

    # 防泄漏：输入文件不能夹带答案字段
    leak_terms = {"gold", "branches", "acceptable_scores", "evidence_groups",
                  "positive_groups", "habits", "dimensions"}
    for case in cases:
        leaked = leak_terms & set(case)
        if leaked:
            error(errors, "E_LEAK", case.get("case_id"),
                  "cases.jsonl 夹带答案字段：%s" % sorted(leaked))

    passed = not errors
    print(json.dumps({
        "action": "schema_check",
        "cases": len(cases),
        "subsets": {name: sum(1 for case in cases if case.get("subset") == name)
                    for name in sorted(weights)},
        "splits": {name: sum(1 for case in cases if case.get("split") == name)
                   for name in SPLITS},
        "errors": errors,
        "passed": passed,
        "capability_note": "只查数据自洽与防泄漏；不验证数学，也不验证案例真实性。",
    }, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
