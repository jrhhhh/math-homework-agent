#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_output.py — 草稿检查卡的**越界审计与错误证据检查**，外加不分析时的标准拒绝出口。

用法：
  audit_output.py audit   --card CARD.json --draft "草稿内容" [--final-solution "最终解答"] [--strict]
  audit_output.py refuse  --reason empty|unreadable|out_of_scope
  audit_output.py clarify --input QUESTIONS.json
  audit_output.py transcribe --input CANDIDATE.json

退出码：
  0 = 干净（不带 --strict 时 warning 不算失败）；1 = 发现越界 error，或 --strict 下出现 warning；
  2 = 输入非法。`refuse` 另有一套映射，见下表。
  `clarify` / `transcribe` 是**出口校验**：0 = 内容有效并已输出；1 = 不合格；2 = 输入非法。
  它们都不产出分析卡——调用方看 `action`，别把 0 当成"卡片已就绪"。

**规则门而非语义理解。** 判对错、指出某处算错了、给出该写成什么，都是本职，不在禁列。
但本门验不了数学：它只能查「你说的那处在草稿上找不找得到」（W_ERROR_NOT_IN_DRAFT），
查不了「你判得对不对」。引用了草稿却把对的判成错的，本门一声不响。
**没有人工复核的草稿检查卡不构成数学结论。** 共用常量见 `_rules.py`。

版面卡（`analysis_basis: "layout_only"`）没有确认过的内容，`--draft` 传的是助手自己的
**版面描述**（分区、涂改、图形、行序，不含字符内容）。这类卡上"卡片与草稿的关联度"和
"错误证据出自草稿"都无从检查，本门跳过它们，改为要求 `scope` 写明内容未经确认。
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rules import (  # noqa: E402
    AMBIGUOUS_SYMBOL_RE, ANALYSIS_BASIS_FIELD, CLARIFY_CANDIDATE_RANGE,
    CLARIFY_ITEM_FIELDS, CLARIFY_MAX_QUESTIONS, CLARIFY_REQUIRED_FIELDS, DIM_KEYS,
    DIMENSIONS_FIELD, DRAFT_CORRECTION_RE, ERROR_FIELD, FULL, IMAGE_SOURCES,
    LAYOUT_ONLY, LAYOUT_ONLY_SCOPE_RE, MACHINE_TRANSCRIPTION, META_VOCAB_RE,
    POSITIVE_DIM, PROBLEM_MARKER_RE, REFUSALS, RISK_CONSEQUENCE_RE, RISK_HEDGE_RE,
    TRANSCRIPTION_MAX_UNCERTAIN, TRANSCRIPTION_READING_RANGE, TRANSCRIPTION_SCOPE_RE,
    UNAVAILABLE, card_texts,
    draft_tokens, emit, load_card, load_json_object, norm, out_of_scope_matches,
    token_hit,
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
    # 版面卡：没有确认过的内容，--draft 传的是助手自己的版面描述。缺少该字段的历史卡
    # 一律按完整卡处理——严格性放在结构门，审计对旧卡保持原行为。
    basis = card.get(ANALYSIS_BASIS_FIELD)
    layout_only = isinstance(basis, str) and basis.strip() == LAYOUT_ONLY

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
    # 版面卡的 --draft 是助手自己写的版面描述，拿它做"卡片有没有引用草稿记号"的检查
    # 只会自我循环：内容从来没进入过这张卡，这项检查在版面卡上没有意义。
    if not layout_only:
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

    # 版面卡：scope 必须写明这次的边界。内容从没进入过这张卡，
    # "我没有核对过"与"我检查过了"的区别只能靠这句话交给学生。
    if layout_only:
        scope = error_check.get("scope") if isinstance(error_check, dict) else None
        scope_text = scope if isinstance(scope, str) else ""
        if not LAYOUT_ONLY_SCOPE_RE.search(scope_text):
            warnings.append({"code": "W_LAYOUT_ONLY_SCOPE_SILENT",
                             "field": "%s.scope" % ERROR_FIELD,
                             "text": scope_text,
                             "detail": "版面卡必须在 scope 里写明内容未经学生确认、"
                                       "不含计算错误判断（标准说法：「内容未经学生确认」"
                                       "「不含计算错误判断」）；这是学生判断这张卡"
                                       "能用到什么程度的唯一依据"})

    # 机器转写：卡片必须写明"学生已逐行核对"。脚本只查声明有没有写，
    # 查不了确认是否真的发生——provenance 仍然只能靠人守。
    if card.get("draft_source") == MACHINE_TRANSCRIPTION:
        scope = error_check.get("scope") if isinstance(error_check, dict) else None
        scope_text = scope if isinstance(scope, str) else ""
        if not TRANSCRIPTION_SCOPE_RE.search(scope_text):
            warnings.append({"code": "W_TRANSCRIPTION_SCOPE_SILENT",
                             "field": "%s.scope" % ERROR_FIELD,
                             "text": scope_text,
                             "detail": "草稿来源是机器转写，scope 必须写明学生已逐行核对"
                                       "（标准说法：「机器转写，学生已逐行核对，更正 N 处」）。"
                                       "没确认过的机器读数不能当证据"})

    # 版面卡的 --draft 是助手自己的版面描述，不能拿来当证据来源；
    # 正确写法已由结构门保证 errors 为空，这里的检查在版面卡上只会自我循环。
    if not layout_only and isinstance(error_check, dict) \
            and isinstance(error_check.get("errors"), list):
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
    if not layout_only and card.get("draft_source") in IMAGE_SOURCES \
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
                                           "这一处再决定报不报；确认不了就走 clarify 只问这一处，"
                                           "或写进 scope 的未核对项" % "、".join(hit)})

    # 一整张草稿纸：分析单位是一道题，先分块并确认归属，再逐题出卡。
    # 版面卡跳过：版面描述通常用 ①②③ 标块，那不是"多个题号"，会误报；
    # 整张纸的口径改由 scope 声明。
    if not layout_only:
        markers = sorted({m.strip() for m in PROBLEM_MARKER_RE.findall(draft)})
        if len(markers) >= 2:
            warnings.append({"code": "W_MULTI_PROBLEM_DRAFT", "field": "*",
                             "markers": markers[:8],
                             "detail": "草稿里出现了多个题号标记，可能不止一道题。"
                                       "分析单位是一道题：先分块、让学生确认归属，"
                                       "再把其中一块作为 --draft 逐题过门，"
                                       "别把整张纸当一份草稿打分"})

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
            # 给了最终解答却把"草稿利用率"标成不适用。
            # 版面卡例外：内容没进卡，利用率本来就无从判断，不构成漏评。
            utilization = dimensions.get("draft_to_solution")
            if not layout_only and isinstance(utilization, dict) \
                    and utilization.get("score") == UNAVAILABLE and final_solution:
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
                  "与草稿及最终解答的关联度、风险句限定词、学段用词一致性"
                  "（版面卡跳过与草稿的关联度与证据检查，改为检查 scope 的边界声明）",
        "analysis_basis": LAYOUT_ONLY if layout_only else FULL,
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


# ---------------------------------------------------------------- clarify / transcribe

def _check_question_item(item, index, prefix, errors, texts, seen,
                         candidate_field="candidates", scan_candidates=True):
    """校验一个问题项；clarify 与 transcribe 共用形状，但选项字段的含义不同。

    - clarify 用 `candidates`：学生点过名的角色，学生可以点选；
    - transcribe 用 `readings`：机器认为可能的读法，**不是证据**，也不按助手措辞扫描。
    """
    tag = "%s[%d]" % (prefix, index)
    if not isinstance(item, dict):
        errors.append({"code": "E_BAD_QUESTION_ITEM", "field": tag,
                       "detail": "每个问题必须是 JSON 对象"})
        return

    allowed = ("location", "question", candidate_field, "affects")
    for field in CLARIFY_REQUIRED_FIELDS:
        value = item.get(field)
        if field not in item:
            errors.append({"code": "E_MISSING_FIELD", "field": "%s.%s" % (tag, field),
                           "detail": "缺少必需字段"})
        elif not isinstance(value, str) or not value.strip():
            errors.append({"code": "E_EMPTY_TEXT", "field": "%s.%s" % (tag, field),
                           "detail": "必须是非空字符串"})
        else:
            texts.append(("%s.%s" % (tag, field), value))

    for field in item:
        if field not in allowed:
            errors.append({"code": "E_EXTRA_FIELD", "field": "%s.%s" % (tag, field),
                           "detail": "非标准字段，建议删除"})

    if candidate_field in item:
        values = item[candidate_field]
        label = "候选" if candidate_field == "candidates" else "机器读法"
        low, high = CLARIFY_CANDIDATE_RANGE if candidate_field == "candidates" \
            else TRANSCRIPTION_READING_RANGE
        field_tag = "%s.%s" % (tag, candidate_field)
        if not isinstance(values, list) or not all(
                isinstance(value, str) and value.strip() for value in values):
            errors.append({"code": "E_BAD_CANDIDATES", "field": field_tag,
                           "detail": "%s必须是非空字符串数组" % label})
        elif not low <= len(values) <= high:
            errors.append({"code": "E_BAD_CANDIDATES", "field": field_tag,
                           "count": len(values),
                           "detail": "%s要么不给，要么给 %d–%d 个" % (label, low, high)})
        elif len({norm(value) for value in values}) != len(values):
            errors.append({"code": "E_BAD_CANDIDATES", "field": field_tag,
                           "detail": "%s有重复项" % label})
        elif scan_candidates:
            for position, value in enumerate(values, start=1):
                texts.append(("%s[%d]" % (field_tag, position), value))

    question = item.get("question")
    if isinstance(question, str) and question.strip():
        key = norm(question)
        if key in seen:
            errors.append({"code": "E_DUPLICATE_QUESTION", "field": "%s.question" % tag,
                           "detail": "与第 %d 个问题重复；问的是同一件事，"
                                     "合并，或在问题里写清位置" % seen[key]})
        else:
            seen[key] = index


def cmd_clarify(args):
    """校验并输出一张"只补几处关键记号"的问题单。

    它不产出分析卡：学生确认后，把回答原样追加进草稿文字，再重跑诊断流程。
    """
    payload = load_json_object(args.input, "questions")
    errors, warnings = [], []

    for field in payload:
        if field not in ("message", "questions"):
            errors.append({"code": "E_EXTRA_FIELD", "field": field,
                           "detail": "问题单只接收 message 与 questions"})

    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        errors.append({"code": "E_EMPTY_TEXT", "field": "message",
                       "detail": "必须是非空字符串：这句话会直接给学生看"})

    questions = payload.get("questions")
    if not isinstance(questions, list):
        errors.append({"code": "E_BAD_QUESTIONS", "field": "questions",
                       "detail": "questions 必须是数组，每项一个问题"})
        questions = []
    elif not questions:
        errors.append({"code": "E_CLARIFY_COUNT", "count": 0,
                       "detail": "至少提一个问题；没有问题就不要走 clarify"})
    elif len(questions) > CLARIFY_MAX_QUESTIONS:
        errors.append({"code": "E_CLARIFY_COUNT", "count": len(questions),
                       "detail": "一轮最多 %d 个问题；超过就拆题、请学生补文字，"
                                 "或出更保守的卡——不许把整页变成问卷"
                                 % CLARIFY_MAX_QUESTIONS})

    texts = [("message", message)] if isinstance(message, str) else []
    seen = {}
    for index, item in enumerate(questions, start=1):
        _check_question_item(item, index, "questions", errors, texts, seen)

    # 问题单也会直接给学生看：越界措辞一样不许出现
    for field, text in texts:
        for code, label, matched, _start, _end in out_of_scope_matches(text):
            errors.append({"code": code, "field": field, "text": text,
                           "matched": matched,
                           "detail": "越过本 skill 边界：%s" % label})

    passed = not errors
    emit({
        "action": "clarify",
        "message": message,
        "questions": questions,
        "method": "问题单校验：message 非空；1–%d 个问题；每项 location / question / "
                  "affects 必填，candidates 可选（%d–%d 个、不重复）；问题不重复；"
                  "全部措辞按越界规则扫描"
                  % (CLARIFY_MAX_QUESTIONS, CLARIFY_CANDIDATE_RANGE[0],
                     CLARIFY_CANDIDATE_RANGE[1]),
        "errors": errors,
        "warnings": warnings,
        "passed": passed,
        "note": "本轮不产出分析卡。学生回答后，把回答原样追加进草稿文字"
                "（【学生补充·原话】…），再重跑 validate / audit。",
        "capability_note": "问题单只让学生补几处记号，不是让他重述整页；"
                           "它本身不产出任何数学结论，也不验证学生回答得对不对。"
                           "候选只能来自学生文字已点名、但没写清的角色——"
                           "不许从照片上的字形推断出这是什么记号。",
    }, 0 if passed else 1)


# ---------------------------------------------------------------- transcribe

def cmd_transcribe(args):
    """校验并输出一份"机器候选转写，等学生全文核对"的稿子。

    它不产出分析卡，也不证明转写准确；学生确认前，候选稿不能当证据。
    """
    payload = load_json_object(args.input, "candidate")
    errors, warnings = [], []

    for field in payload:
        if field not in ("message", "candidate", "uncertain"):
            errors.append({"code": "E_EXTRA_FIELD", "field": field,
                           "detail": "转写稿只接收 message、candidate 与 uncertain"})

    message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        errors.append({"code": "E_EMPTY_TEXT", "field": "message",
                       "detail": "必须是非空字符串：这句话会直接给学生看"})

    candidate = payload.get("candidate")
    if not isinstance(candidate, str) or not candidate.strip():
        errors.append({"code": "E_EMPTY_TEXT", "field": "candidate",
                       "detail": "必须是非空字符串：这是机器转写的候选稿"})

    uncertain = payload.get("uncertain", [])
    if not isinstance(uncertain, list):
        errors.append({"code": "E_BAD_UNCERTAIN", "field": "uncertain",
                       "detail": "uncertain 必须是数组；没有不确定处就省略"})
        uncertain = []
    elif len(uncertain) > TRANSCRIPTION_MAX_UNCERTAIN:
        errors.append({"code": "E_UNCERTAIN_COUNT", "count": len(uncertain),
                       "detail": "最多 %d 处不确定；超过说明这份转写还不适合直接进分析，"
                                 "改走 clarify 或只出版面卡" % TRANSCRIPTION_MAX_UNCERTAIN})

    # candidate 是学生内容，不按"助手措辞"扫描；message 与 uncertain 会直接给学生看。
    texts = [("message", message)] if isinstance(message, str) else []
    seen = {}
    for index, item in enumerate(uncertain, start=1):
        _check_question_item(item, index, "uncertain", errors, texts, seen,
                             candidate_field="readings", scan_candidates=False)

    for field, text in texts:
        for code, label, matched, _start, _end in out_of_scope_matches(text):
            errors.append({"code": code, "field": field, "text": text,
                           "matched": matched,
                           "detail": "越过本 skill 边界：%s" % label})

    passed = not errors
    emit({
        "action": "transcribe",
        "status": "awaiting_student_confirmation",
        "confirmation_scope": "full",
        "message": message,
        "candidate": candidate,
        "uncertain": uncertain,
        "method": "候选转写校验：message / candidate 非空；uncertain 可选、最多 %d 项，"
                  "每项 location / question / affects 必填，readings 可选（%d–%d 个）；"
                  "message 与 uncertain 的助手措辞按越界规则扫描，candidate 与 readings 不扫"
                  % (TRANSCRIPTION_MAX_UNCERTAIN, TRANSCRIPTION_READING_RANGE[0],
                     TRANSCRIPTION_READING_RANGE[1]),
        "errors": errors,
        "warnings": warnings,
        "passed": passed,
        "note": "学生逐行核对并确认后，把确认稿作为 --draft，草稿来源写 "
                "machine_transcription；确认之前，这份候选不能当证据。",
        "capability_note": "本命令只校验候选稿与问题的形状，不检查转写是否准确，"
                           "也不验证学生是否真的核对过。未确认的机器读数不能进 errors；"
                           "转写准确率必须在真实手写照片上另行验收。",
    }, 0 if passed else 1)


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(
        description="Scan a student draft-habit analysis card for out-of-scope moves "
                    "and unfounded error claims; also validate the non-analysis exits "
                    "(refuse / clarify / transcribe).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser("audit", help="scan a card for out-of-scope moves and detachment")
    p_audit.add_argument("--card", required=True, help="path to the card JSON file")
    p_audit.add_argument("--draft", required=True,
                         help="the student's draft content; for a layout-only card, "
                              "the assistant's own layout description (no character content)")
    p_audit.add_argument("--final-solution", default=None,
                         help="optional: the student's final solution")
    p_audit.add_argument("--strict", action="store_true", help="treat warnings as failures")
    p_audit.set_defaults(func=cmd_audit)

    p_refuse = sub.add_parser("refuse", help="emit the standard refusal payload")
    p_refuse.add_argument("--reason", required=True, choices=sorted(REFUSALS),
                          help="empty = 无草稿；unreadable = 草稿无法识别；"
                               "out_of_scope = 学生只想知道对错")
    p_refuse.set_defaults(func=cmd_refuse)

    p_clarify = sub.add_parser(
        "clarify", help="validate and emit a question list for missing key marks")
    p_clarify.add_argument("--input", required=True,
                           help="path to the questions JSON file (message + questions)")
    p_clarify.set_defaults(func=cmd_clarify)

    p_transcribe = sub.add_parser(
        "transcribe", help="validate and emit a candidate transcription for student confirmation")
    p_transcribe.add_argument("--input", required=True,
                              help="path to the candidate JSON file "
                                   "(message + candidate + optional uncertain)")
    p_transcribe.set_defaults(func=cmd_transcribe)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
