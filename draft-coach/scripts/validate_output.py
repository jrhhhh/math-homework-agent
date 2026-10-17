#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_output.py — 草稿检查卡的**结构门**，外加出卡前的六维要点提示。

用法：
  validate_output.py validate --card CARD.json
  validate_output.py hint     --draft "草稿内容" [--grade-level 高中]

退出码：
  0 = 结构通过；1 = 结构不合格（缺错误清单、错误条目缺字段、缺维度、评分越界、
  习惯条数不合法、分析依据与评分/来源不符、多余字段）；2 = 输入非法（卡片文件读不了、
  草稿为空、学段非法）。
  `hint` 在输入合法时总是退出 0。

**它不判断你报的那处错误在数学上是否真的错**——那要人来算。越界与证据审计在
`audit_output.py`。共用常量与能力边界见 `_rules.py`。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rules import (  # noqa: E402
    ANALYSIS_BASES, ANALYSIS_BASIS_FIELD, DEFAULT_GRADE, DIMENSIONS_FIELD, DIM_FIELDS,
    DIM_KEYS, DIM_LABEL, DIM_RUBRIC, ERROR_FIELD, ERROR_ITEM_FIELDS,
    FIX_NON_ACTIONABLE_RE, GRADE_TABLE, GRADES, HABIT_COUNT, HABIT_COUNT_LAYOUT,
    HABIT_FIELD, HABIT_FIELDS, LAYOUT_ONLY, LAYOUT_ONLY_OPTIONAL_DIMS,
    LAYOUT_ONLY_REQUIRED_DIMS, LAYOUT_ONLY_UNAVAILABLE_DIMS, LAYOUT_SOURCES, POSITIVE_DIM,
    REQUIRED_FIELDS, SCORES, SCORES_LAST, SIGNAL_CUES, SOURCES, UNAVAILABLE,
    VAGUE_ACTION_RE, emit, load_card, norm,
)


# ---------------------------------------------------------------- validate

def cmd_validate(args):
    card = load_card(args.card)
    errors, warnings = [], []

    for field in REQUIRED_FIELDS:
        if field not in card:
            errors.append({"code": "E_MISSING_FIELD", "field": field,
                           "detail": "缺少必需字段"})
    for field in card:
        if field not in REQUIRED_FIELDS:
            errors.append({"code": "E_EXTRA_FIELD", "field": field,
                           "detail": "分析卡只能包含 %d 个标准字段；"
                                     "交接状态、诊断结论请放在卡片之外" % len(REQUIRED_FIELDS)})

    # -- 分析依据：完整卡（内容 + 版面）/ 版面卡（只有助手亲眼看的版面）
    basis = card.get(ANALYSIS_BASIS_FIELD)
    basis_value = basis.strip() if isinstance(basis, str) else ""
    if basis_value and basis_value not in ANALYSIS_BASES:
        errors.append({"code": "E_BAD_ANALYSIS_BASIS", "field": ANALYSIS_BASIS_FIELD,
                       "text": basis, "detail": "分析依据取值非法",
                       "allowed": list(ANALYSIS_BASES)})
    layout_only = basis_value == LAYOUT_ONLY

    # -- 错误清单（首要产出，排在六个维度前面）
    error_check = card.get(ERROR_FIELD)
    if ERROR_FIELD in card:
        if not isinstance(error_check, dict):
            errors.append({"code": "E_BAD_ERROR_CHECK", "field": ERROR_FIELD,
                           "detail": "必须是对象：scope 说明本次检查范围，errors 是错误数组"})
            error_check = None
        else:
            for field in error_check:
                if field not in ("scope", "errors"):
                    errors.append({"code": "E_EXTRA_FIELD", "field": "%s.%s" % (ERROR_FIELD, field),
                                   "detail": "非标准字段，建议删除"})
            scope = error_check.get("scope")
            if not isinstance(scope, str) or not scope.strip():
                errors.append({"code": "E_EMPTY_TEXT", "field": "%s.scope" % ERROR_FIELD,
                               "detail": "必须写明这次实际检查了什么、什么没查"})

    if isinstance(error_check, dict):
        found = error_check.get("errors")
        if "errors" not in error_check:
            errors.append({"code": "E_MISSING_FIELD", "field": "%s.errors" % ERROR_FIELD,
                           "detail": "必须是数组；没发现错误就写空数组，不能不写"})
        elif not isinstance(found, list):
            errors.append({"code": "E_BAD_ERROR_LIST", "field": "%s.errors" % ERROR_FIELD,
                           "detail": "必须是数组"})
        else:
            for index, item in enumerate(found, start=1):
                tag = "%s.errors[%d]" % (ERROR_FIELD, index)
                if not isinstance(item, dict):
                    errors.append({"code": "E_BAD_ERROR_ITEM", "field": tag,
                                   "detail": "每条错误必须是 JSON 对象"})
                    continue
                for field in ERROR_ITEM_FIELDS:
                    if field not in item:
                        errors.append({"code": "E_MISSING_FIELD", "field": "%s.%s" % (tag, field),
                                       "detail": "缺少必需字段"})
                    elif not isinstance(item[field], str) or not item[field].strip():
                        errors.append({"code": "E_EMPTY_TEXT", "field": "%s.%s" % (tag, field),
                                       "detail": "必须是非空字符串"})
                for field in item:
                    if field not in ERROR_ITEM_FIELDS:
                        errors.append({"code": "E_EXTRA_FIELD", "field": "%s.%s" % (tag, field),
                                       "detail": "非标准字段，建议删除"})
                fix = item.get("fix")
                if isinstance(fix, str) and fix.strip() and FIX_NON_ACTIONABLE_RE.match(fix):
                    warnings.append({"code": "W_VAGUE_FIX", "field": "%s.fix" % tag, "text": fix,
                                     "detail": "修改写成这样等于没说；要写出改成什么"})

    # -- 六个维度
    dimensions = card.get(DIMENSIONS_FIELD)
    if DIMENSIONS_FIELD in card:
        if not isinstance(dimensions, dict):
            errors.append({"code": "E_BAD_DIMENSIONS", "field": DIMENSIONS_FIELD,
                           "detail": "必须是对象，键为六个固定维度名"})
            dimensions = None
        else:
            for key in DIM_KEYS:
                if key not in dimensions:
                    errors.append({"code": "E_MISSING_DIMENSION", "field": key,
                                   "detail": "缺少维度「%s」" % DIM_LABEL[key]})
            for key in dimensions:
                if key not in DIM_KEYS:
                    errors.append({"code": "E_EXTRA_DIMENSION", "field": key,
                                   "detail": "非标准维度名；六个维度键名固定，不新增不细分",
                                   "allowed": list(DIM_KEYS)})

    if isinstance(dimensions, dict):
        for key in DIM_KEYS:
            if key not in dimensions:
                continue
            dim = dimensions[key]
            tag = "%s.%s" % (DIMENSIONS_FIELD, key)
            if not isinstance(dim, dict):
                errors.append({"code": "E_BAD_DIMENSION", "field": tag,
                               "detail": "每个维度必须是 JSON 对象"})
                continue

            for field in DIM_FIELDS:
                if field not in dim:
                    errors.append({"code": "E_MISSING_FIELD",
                                   "field": "%s.%s" % (tag, field),
                                   "detail": "缺少必需字段"})
                elif not isinstance(dim[field], str) or not dim[field].strip():
                    errors.append({"code": "E_EMPTY_TEXT",
                                   "field": "%s.%s" % (tag, field),
                                   "detail": "必须是非空字符串"})

            if layout_only:
                if key in LAYOUT_ONLY_UNAVAILABLE_DIMS:
                    allowed_scores = (UNAVAILABLE,)
                    note = "版面卡没有确认过的内容，这一维给不出，必须标「不适用」"
                elif key in LAYOUT_ONLY_REQUIRED_DIMS:
                    allowed_scores = SCORES
                    note = "版面卡里这一维必须给真实评分"
                elif key in LAYOUT_ONLY_OPTIONAL_DIMS:  # 图形使用
                    allowed_scores = SCORES + (UNAVAILABLE,)
                    note = "只有草稿上无图、且题型判不了时才可用「不适用」"
                else:
                    allowed_scores = SCORES
                    note = "版面卡里这一维必须给真实评分"
            else:
                allowed_scores = SCORES_LAST if key == "draft_to_solution" else SCORES
                note = None if key == "draft_to_solution" \
                    else "只有「草稿利用率」在缺少最终解答时可用「不适用」"
            score = dim.get("score")
            if isinstance(score, str) and score.strip():
                if score.strip() not in allowed_scores:
                    errors.append({"code": "E_BAD_SCORE", "field": "%s.score" % tag,
                                   "text": score,
                                   "detail": "评分取值非法",
                                   "allowed": list(allowed_scores),
                                   "note": note})
            if "positive" in dim:
                if key != POSITIVE_DIM:
                    errors.append({"code": "E_EXTRA_FIELD", "field": "%s.positive" % tag,
                                   "detail": "只有「涂改模式」可以写 positive；"
                                             "其他维度的积极信号写进 observation"})
                elif not isinstance(dim["positive"], str) or not dim["positive"].strip():
                    errors.append({"code": "E_EMPTY_TEXT", "field": "%s.positive" % tag,
                                   "detail": "必须是非空字符串"})
            for field in dim:
                if field not in DIM_FIELDS and field != "positive":
                    errors.append({"code": "E_EXTRA_FIELD", "field": "%s.%s" % (tag, field),
                                   "detail": "非标准字段，建议删除"})

            evidence = dim.get("evidence")
            if isinstance(evidence, str) and evidence.strip() and len(norm(evidence)) < 6:
                warnings.append({"code": "W_EVIDENCE_SHORT", "field": "%s.evidence" % tag,
                                 "text": evidence,
                                 "detail": "证据过短，看不出草稿里的具体位置或记号"})

    # -- 学段与来源
    grade = card.get("grade_level")
    if isinstance(grade, str) and grade.strip() and grade.strip() not in GRADES:
        errors.append({"code": "E_BAD_GRADE", "field": "grade_level", "text": grade,
                       "detail": "学段必须是小学 / 初中 / 高中 / 大学之一",
                       "allowed": list(GRADES)})
    source = card.get("draft_source")
    if isinstance(source, str) and source.strip() and source.strip() not in SOURCES:
        errors.append({"code": "E_BAD_SOURCE", "field": "draft_source", "text": source,
                       "detail": "草稿来源取值非法", "allowed": list(SOURCES)})

    # -- 版面卡的不变量：没有确认过的内容，就不许有计算错误判断，也不许来自文字草稿
    if layout_only:
        found = error_check.get("errors") if isinstance(error_check, dict) else None
        if isinstance(found, list) and found:
            errors.append({"code": "E_BASIS_ERRORS", "field": "%s.errors" % ERROR_FIELD,
                           "count": len(found),
                           "detail": "版面卡没有确认过的内容，不得包含任何计算错误判断；"
                                     "errors 必须为空"})
        source_value = source.strip() if isinstance(source, str) else ""
        if source_value not in LAYOUT_SOURCES:
            errors.append({"code": "E_BASIS_SOURCE", "field": "draft_source",
                           "text": source,
                           "detail": "版面卡没有确认过的内容，来源只能是学生描述的照片；"
                                     "机器转写意味着已经有内容，应当走完整卡",
                           "allowed": list(LAYOUT_SOURCES)})

    # -- next_step
    next_step = card.get("next_step")
    if "next_step" in card and (not isinstance(next_step, str) or not next_step.strip()):
        errors.append({"code": "E_EMPTY_TEXT", "field": "next_step",
                       "detail": "必须是非空字符串"})
    if isinstance(next_step, str) and next_step.strip():
        if len(norm(next_step)) < 6 or VAGUE_ACTION_RE.search(next_step):
            warnings.append({"code": "W_NON_ACTIONABLE", "field": "next_step",
                             "text": next_step,
                             "detail": "看不出下一道题具体做什么；写成能立刻执行的动作"})

    # -- 三条习惯
    habits = card.get(HABIT_FIELD)
    if HABIT_FIELD in card:
        if not isinstance(habits, list):
            errors.append({"code": "E_BAD_HABITS", "field": HABIT_FIELD,
                           "detail": "必须是数组，数组里每条是一个习惯"})
            habits = None
        elif layout_only:
            if len(habits) not in HABIT_COUNT_LAYOUT:
                errors.append({"code": "E_HABIT_COUNT", "count": len(habits),
                               "detail": "版面卡的习惯允许 %d–%d 条，实为 %d 条；"
                                         "只写版面能支撑的，不要凑数"
                                         % (HABIT_COUNT_LAYOUT[0],
                                            HABIT_COUNT_LAYOUT[-1], len(habits))})
        elif len(habits) != HABIT_COUNT:
            errors.append({"code": "E_HABIT_COUNT", "count": len(habits),
                           "detail": "习惯必须恰好 %d 条，实为 %d 条" % (HABIT_COUNT, len(habits))})

    if isinstance(habits, list):
        seen = {}
        for index, habit in enumerate(habits, start=1):
            tag = "%s[%d]" % (HABIT_FIELD, index)
            if not isinstance(habit, dict):
                errors.append({"code": "E_BAD_HABIT", "field": tag,
                               "detail": "每条习惯必须是 JSON 对象"})
                continue
            for field in HABIT_FIELDS:
                if field not in habit:
                    errors.append({"code": "E_MISSING_FIELD", "field": "%s.%s" % (tag, field),
                                   "detail": "缺少必需字段"})
                elif not isinstance(habit[field], str) or not habit[field].strip():
                    errors.append({"code": "E_EMPTY_TEXT", "field": "%s.%s" % (tag, field),
                                   "detail": "必须是非空字符串"})
            for field in habit:
                if field not in HABIT_FIELDS:
                    errors.append({"code": "E_EXTRA_FIELD", "field": "%s.%s" % (tag, field),
                                   "detail": "非标准字段，建议删除"})

            key = norm(habit.get("habit", ""))
            if key:
                if key in seen:
                    errors.append({"code": "E_DUPLICATE_HABIT", "field": "%s.habit" % tag,
                                   "text": habit.get("habit"),
                                   "detail": "与第 %d 条习惯重复；三条习惯要说三件事" % seen[key]})
                else:
                    seen[key] = index

            training = habit.get("training")
            if isinstance(training, str) and training.strip():
                if len(norm(training)) < 6 or VAGUE_ACTION_RE.search(training):
                    warnings.append({"code": "W_NON_ACTIONABLE",
                                     "field": "%s.training" % tag, "text": training,
                                     "detail": "看不出下一道题具体做什么；"
                                               "写成能立刻执行的动作，不是周期计划"})

    # -- 整卡层面的警告
    if isinstance(dimensions, dict):
        # 只比真实评分的维度：版面卡里有「不适用」，把它算进去这项检查必然空转
        scores = [dimensions[k].get("score") for k in DIM_KEYS
                  if isinstance(dimensions.get(k), dict)
                  and dimensions[k].get("score") in SCORES]
        if len(scores) >= 3 and len(set(scores)) == 1:
            warnings.append({"code": "W_SCORE_UNIFORM", "field": DIMENSIONS_FIELD,
                             "detail": "可评的 %d 个维度评分完全相同（%s）；"
                                       "先确认这不是没有逐维看草稿" % (len(scores), scores[0])})

    passed = not errors
    emit({
        "action": "validate",
        "input": {"card": args.card},
        "method": "字段完整性 + 错误清单四字段 + 恰好六个维度 + 评分取值（按分析依据校验）"
                  " + 习惯条数 + 学段、来源与分析依据的合法性"
                  " + 版面卡不变量（错误清单为空、来源为图片、内容三维不适用）",
        "errors": errors,
        "warnings": warnings,
        "passed": passed,
        "capability_note": "结构门只查卡片长得对不对：**它不判断你报的错误是不是真的错**，"
                           "也不判断习惯观察是否成立。错误指控是否有草稿依据由 audit 的"
                           " W_ERROR_NOT_IN_DRAFT 提醒，数学本身只能人工复核。",
    }, 0 if passed else 1)


# ---------------------------------------------------------------- hint

def cmd_hint(args):
    draft = (args.draft or "").strip()
    if not draft:
        emit({"error": "--draft must be a non-empty string"}, 2)
    grade = (args.grade_level or DEFAULT_GRADE).strip()
    if grade not in GRADES:
        emit({"error": "--grade-level must be one of %s" % " / ".join(GRADES)}, 2)

    blob = draft.lower()
    detected = []
    for key, label, keywords in SIGNAL_CUES:
        hits = [kw for kw in keywords if kw.lower() in blob]
        if hits:
            detected.append({"dimension": key, "dimension_label": DIM_LABEL[key],
                             "signal": label, "matched_keywords": hits})

    emit({
        "action": "hint",
        "input": {"draft": draft, "grade_level": grade},
        "method": "六维检查要点回显 + 学段适配表 + 草稿关键词启发式提示"
                  "（未命中不代表该维度没问题，只代表关键词表没覆盖）",
        "dimensions": [{"key": key, "label": label, "focus": focus}
                       for key, label, focus in DIM_RUBRIC],
        "grade_menu": [{"grade": g, "style": style, "training": training,
                        "focus_dimensions": [DIM_LABEL[k] for k in keys]}
                       for g, style, training, keys in GRADE_TABLE],
        "selected_grade": grade,
        "detected_signals": detected,
        "authority": "heuristic-hint-only",
        "capability_note": "关键词命中只是提示，可能误判；必须以读完草稿后的判断为准，"
                           "不得用本输出替代对草稿的理解，也不得凭关键词就下习惯结论。"
                           "六个维度都要给评分，不能因为没命中关键词就跳过。",
    }, 0)


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(
        description="Structural gate for a student draft-habit analysis card.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="structural gate for a draft analysis card")
    p_validate.add_argument("--card", required=True, help="path to the card JSON file")
    p_validate.set_defaults(func=cmd_validate)

    p_hint = sub.add_parser("hint", help="echo the six-dimension rubric and grade table")
    p_hint.add_argument("--draft", required=True, help="the student's draft content")
    p_hint.add_argument("--grade-level", default=DEFAULT_GRADE,
                        help="小学 / 初中 / 高中 / 大学（默认高中）")
    p_hint.set_defaults(func=cmd_hint)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
