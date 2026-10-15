#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_output.py — 草稿检查卡的**越界审计与错误证据检查**，外加不分析时的标准拒绝出口。

用法：
  audit_output.py audit  --card CARD.json --draft "草稿内容" [--final-solution "最终解答"] [--strict]
  audit_output.py refuse --reason empty|unreadable|out_of_scope

退出码：
  0 = 干净（不带 --strict 时 warning 不算失败）；1 = 发现越界 error，或 --strict 下出现 warning；
  2 = 输入非法。`refuse` 另有一套映射，见下表。

**规则门而非语义理解。** 判对错、指出某处算错了、给出该写成什么，都是本职，不在禁列。
但本门验不了数学：它只能查「你说的那处在草稿上找不找得到」（W_ERROR_NOT_IN_DRAFT），
查不了「你判得对不对」。引用了草稿却把对的判成错的，本门一声不响。
**没有人工复核的草稿检查卡不构成数学结论。** 共用常量见 `_rules.py`。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rules import (  # noqa: E402
    AMBIGUOUS_SYMBOL_RE, DIM_KEYS, DIMENSIONS_FIELD, DRAFT_CORRECTION_RE, ERROR_FIELD,
    IMAGE_SOURCES, META_VOCAB_RE, POSITIVE_DIM, PROBLEM_MARKER_RE, REFUSALS,
    RISK_CONSEQUENCE_RE, RISK_HEDGE_RE, UNAVAILABLE, card_texts, draft_tokens, emit,
    load_card, norm, out_of_scope_matches, token_hit,
)


# ---------------------------------------------------------------- audit

def cmd_audit(args):
    card = load_card(args.card)
    draft = (args.draft or "").strip()
    if not draft:
        emit({"error": "--draft must be a non-empty string",
              "hint": "没有草稿就不要分析；用 refuse --reason empty 给出标准回复"}, 2)
    final_solution = (args.final_solution or "").strip()

    errors, warnings = [], []
    texts = card_texts(card)

    # A 组：越界措辞——跑到了别的 skill 的疆域。
    # 口径与评测器共用 out_of_scope_matches：被否定的措辞不算越界
    # （「这一项我没有打分」是拒绝越界，不是越界）。
    for field, text in texts:
        for code, label, matched, _start, _end in out_of_scope_matches(text):
            errors.append({"code": code, "field": field, "text": text,
                           "matched": matched,
                           "detail": "越过本 skill 边界：%s" % label})

    # W 组：卡片与草稿 / 最终解答是否脱节
    joined = " ".join(norm(text) for _, text in texts)
    tokens = draft_tokens(draft)
    if len(tokens) >= 3:
        if not any(token_hit(joined, token) for token in tokens):
            warnings.append({"code": "W_DETACHED_DRAFT", "field": "*",
                             "draft_tokens": tokens[:12],
                             "detail": "卡片没有引用草稿里的任何数字或记号，"
                                       "可能不是从这份草稿看出来的"})
    if final_solution:
        solution_tokens = draft_tokens(final_solution)
        if len(solution_tokens) >= 3:
            if not any(token_hit(joined, token) for token in solution_tokens):
                warnings.append({"code": "W_DETACHED_SOLUTION", "field": "*",
                                 "solution_tokens": solution_tokens[:12],
                                 "detail": "卡片没有引用最终解答里的任何数字或记号，"
                                           "可能脱离实际解答"})

    # W 组（最重要的一条）：每条错误指控都必须在草稿里有据。
    # 本门验不了数学，但它能验"你说的那处到底在不在草稿上"。
    draft_norm = norm(draft)
    error_check = card.get(ERROR_FIELD)
    if isinstance(error_check, dict) and isinstance(error_check.get("errors"), list):
        for index, item in enumerate(error_check["errors"], start=1):
            if not isinstance(item, dict):
                continue
            evidence = item.get("evidence")
            if not isinstance(evidence, str) or not evidence.strip():
                continue
            # 同一条错误的 fix 里出现的新数值（"应改成 4"）不算"查无此据"：
            # 那是答案给出的期望值，不是对草稿的引述断言。放在 evidence 里也一样豁免。
            fix = item.get("fix")
            fix_norm = norm(fix) if isinstance(fix, str) else ""
            evidence_tokens = draft_tokens(evidence)
            if not evidence_tokens:
                warnings.append({"code": "W_ERROR_EVIDENCE_VAGUE",
                                 "field": "%s.errors[%d].evidence" % (ERROR_FIELD, index),
                                 "text": evidence,
                                 "detail": "这条错误的证据里没有任何数字或记号，"
                                           "没法核它是不是真出自这份草稿"})
            # 判据是"**任一**记号在草稿里出现即算有据"（不能改成"每个都要出现"：
            # 归一化会去掉小数点与括号，`x=5.5` 这类记号天然对不上，逐个小考会把
            # 大量正常证据判成查无此据）。fix 里的记号同样算有据——那是答案给出的
            # 期望值，不是对草稿的引述断言，例如"应改成 2x+6=14"里的 6。
            elif not any(token_hit(draft_norm, token) or token_hit(fix_norm, token)
                         for token in evidence_tokens):
                warnings.append({"code": "W_ERROR_NOT_IN_DRAFT",
                                 "field": "%s.errors[%d].evidence" % (ERROR_FIELD, index),
                                 "text": evidence,
                                 "candidates": evidence_tokens[:12],
                                 "detail": "这条错误的证据在草稿里找不到对应记号——"
                                           "本门唯一能守的错误约束就是这条，请人工复核。"
                                           "同一错误 fix 字段里的记号已算作有据；反过来，"
                                           "把记号塞进 fix 就能绕过本门，所以它仍然只是"
                                           "提醒，不是结论"})

    # 图片来源：证据依赖形近记号的错误，报一条提醒（不是判决）
    if card.get("draft_source") in IMAGE_SOURCES \
            and isinstance(error_check, dict) and isinstance(error_check.get("errors"), list):
        for index, item in enumerate(error_check["errors"], start=1):
            if not isinstance(item, dict):
                continue
            evidence = item.get("evidence")
            if not isinstance(evidence, str):
                continue
            hit = sorted(set(AMBIGUOUS_SYMBOL_RE.findall(evidence)))
            if hit:
                warnings.append({"code": "W_MIXED_SYMBOL_EVIDENCE",
                                 "field": "%s.errors[%d].evidence" % (ERROR_FIELD, index),
                                 "text": evidence,
                                 "symbols": hit,
                                 "detail": "这条错误的证据依赖形近记号（%s），而草稿来自图片："
                                           "手写里 ≤/<、±/+、6/8 常常分不出来。请对照原纸确认"
                                           "这一处再决定报不报；确认不了就改成 scope 里的"
                                           "未核对项" % "、".join(hit)})

    # 一整张草稿纸：分析单位是一道题，先分块并确认归属，再逐题出卡
    markers = sorted({m.strip() for m in PROBLEM_MARKER_RE.findall(draft)})
    if len(markers) >= 2:
        warnings.append({"code": "W_MULTI_PROBLEM_DRAFT", "field": "*",
                         "markers": markers[:8],
                         "detail": "草稿里出现了多个题号标记，可能不止一道题。"
                                   "分析单位是一道题：先分块、让学生确认归属，"
                                   "再把其中一块作为 --draft 逐题过门，别把整张纸当一份草稿打分"})

    dimensions = card.get(DIMENSIONS_FIELD)
    if isinstance(dimensions, dict):
        correction = dimensions.get(POSITIVE_DIM)
        if isinstance(correction, dict):
            # 草稿里有涂改却没写积极信号：不是错误，但值得人工看一眼
            if correction.get("score") != "高" and not str(correction.get("positive", "")).strip() \
                    and DRAFT_CORRECTION_RE.search(draft):
                warnings.append({"code": "W_POSITIVE_ABSENT",
                                 "field": "%s.%s.positive" % (DIMENSIONS_FIELD, POSITIVE_DIM),
                                 "detail": "草稿里有涂改痕迹，但没有指出积极信号；"
                                           "涂改后能自我纠正、改处有标注都应肯定"})
            # 给了最终解答却把"草稿利用率"标成不适用
            utilization = dimensions.get("draft_to_solution")
            if isinstance(utilization, dict) and utilization.get("score") == UNAVAILABLE \
                    and final_solution:
                warnings.append({"code": "W_UTILIZATION_UNAVAILABLE",
                                 "field": "%s.draft_to_solution.score" % DIMENSIONS_FIELD,
                                 "detail": "已提供最终解答，草稿利用率应当可以评分"})

    # risk 是假设句：说了后果就得带限定词
    if isinstance(dimensions, dict):
        for key in DIM_KEYS:
            dim = dimensions.get(key)
            if not isinstance(dim, dict):
                continue
            risk = dim.get("risk")
            if isinstance(risk, str) and RISK_CONSEQUENCE_RE.search(risk) \
                    and not RISK_HEDGE_RE.search(risk):
                warnings.append({"code": "W_RISK_UNHEDGED",
                                 "field": "%s.%s.risk" % (DIMENSIONS_FIELD, key),
                                 "text": risk,
                                 "detail": "风险句没有限定词，读起来像在断言已经出错了；"
                                           "改成「若…可能…」的假设句"})

    # 学段适配：小学 / 初中不该出现元认知词汇
    grade = card.get("grade_level")
    if grade in ("小学", "初中"):
        for field, text in texts:
            match = META_VOCAB_RE.search(text)
            if match:
                warnings.append({"code": "W_GRADE_MISMATCH", "field": field, "text": text,
                                 "matched": match.group(0),
                                 "detail": "学段是%s，却使用了元认知 / 策略导向的措辞" % grade})

    passed = not errors and not (args.strict and warnings)
    emit({
        "action": "audit",
        "input": {"card": args.card, "draft": draft,
                  "final_solution": final_solution or None, "strict": args.strict},
        "method": "规则扫描：诊断知识漏洞 / 贴标签 / 排题量计划 / 出变式题 / 给完整解答 / "
                  "评分扣分（被否定的措辞豁免，如「这一项我没有打分」），"
                  "外加**错误证据是否出自草稿**（同一条错误 fix 里的记号算有据）、"
                  "与草稿及最终解答的关联度、风险句限定词、学段用词一致性",
        "errors": errors,
        "warnings": warnings,
        "passed": passed,
        "capability_note": "规则门而非语义理解。判对错、指出某处算错了、给出该写成什么，"
                           "**都是本职，不在禁列**。但本门**验不了数学**：它只能查"
                           "「你说的那处在草稿上找不找得到」（W_ERROR_NOT_IN_DRAFT），"
                           "查不了「你判得对不对」。引用了草稿却把对的判成错的，本门一声不响。"
                           "**没有人工复核的草稿检查卡不构成数学结论。**",
    }, 0 if passed else 1)


# ---------------------------------------------------------------- refuse

def cmd_refuse(args):
    error, message, code = REFUSALS[args.reason]
    emit({
        "action": "refuse",
        "error": error,
        "message": message,
        "reason": args.reason,
        "exit_code_meaning": {
            "empty": "没有草稿：必需输入缺失",
            "unreadable": "草稿无法识别：输入存在但用不了",
            "out_of_scope": "超出范围：草稿没问题，但这个问题不归本技能管",
        }[args.reason],
    }, code)


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(
        description="Scan a student draft-habit analysis card for out-of-scope moves "
                    "and unfounded error claims.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser("audit", help="scan a card for out-of-scope moves and detachment")
    p_audit.add_argument("--card", required=True, help="path to the card JSON file")
    p_audit.add_argument("--draft", required=True, help="the student's draft content")
    p_audit.add_argument("--final-solution", default=None,
                         help="optional: the student's final solution")
    p_audit.add_argument("--strict", action="store_true", help="treat warnings as failures")
    p_audit.set_defaults(func=cmd_audit)

    p_refuse = sub.add_parser("refuse", help="emit the standard refusal payload")
    p_refuse.add_argument("--reason", required=True, choices=sorted(REFUSALS),
                          help="empty = 无草稿；unreadable = 草稿无法识别；"
                               "out_of_scope = 学生只想知道对错")
    p_refuse.set_defaults(func=cmd_refuse)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
