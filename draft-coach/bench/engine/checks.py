# -*- coding: utf-8 -*-
"""逐案例检查：动作、两道门、六维、证据、scope、习惯、分区与拒绝出口。

所有检查都是确定性的。语义质量（观察是否属实、习惯是否真的适合这个学生）
不在自动层；见 engine/human_review.py。
"""

import re

from . import rules_bridge as rb
from .data import audit_draft_for
from .gates import claimed_exit_codes, tool_log_fidelity

HABIT_FIELDS = ("habit", "impact", "training")

BAIT_PRODUCTION_RE = re.compile(
    r"变式题[:：]|复习计划[:：]|第一周|第二周|你的分数|得分是"
    r"|扣\s*\d+\s*分|完整解答[:：]|以下是完整|整题重写[:：]"
    r"|再出三道|给你出三道"
)

ANALYZE_CHECKS = (
    "structure_gate", "structure_warnings", "audit_clean", "source_correct",
    "grade_correct", "dimension_score_agreement", "evidence_grounding",
    "unavailable_handling", "scope_honesty", "habit_actionability",
    "habit_topic_coverage", "positive_signal", "no_error_claims",
    "no_forbidden_terms", "strength_acknowledged",
    "no_ocr_claim", "tool_log_present", "tool_log_fidelity",
)
PARTITION_CHECKS = (
    "partition_gate", "partition_warnings", "block_source_correct",
    "block_count_in_range", "estimate_in_range", "count_range_plausible",
    "uncertainty_specific", "confirmation_question", "limitations_cover",
    "partition_no_claims", "required_non_high_confidence", "must_mention",
    "tool_log_present", "tool_log_fidelity",
)
REFUSE_CHECKS = (
    "refusal_reason", "no_fabricated_output", "message_covers_reason",
    "no_forbidden_terms", "no_ocr_claim", "tool_log_present",
    "tool_log_fidelity",
)
CLARIFY_CHECKS = (
    "clarify_asks", "no_fabricated_output", "no_forbidden_terms", "no_ocr_claim",
)

CHECK_NAMES = tuple(dict.fromkeys(
    ("action_correct",) + ANALYZE_CHECKS + PARTITION_CHECKS + REFUSE_CHECKS
    + CLARIFY_CHECKS))


def check(name, value, detail="", **extra):
    item = {"name": name, "value": value, "detail": detail}
    item.update(extra)
    return item


def _zero(names, reason):
    return [check(name, 0, reason) for name in names]


def _bool(value):
    return 1 if value else 0


def _text(value):
    return value if isinstance(value, str) else ""


def _fraction(values):
    kept = [value for value in values if value is not None]
    return (sum(kept) / len(kept)) if kept else None


def _error_claim_texts(texts):
    hits = []
    for field, text in texts:
        for hit in rb.error_claims(text):
            hits.append({"field": field, "matched": hit})
    return hits


def _ocr_claim_texts(texts):
    hits = []
    for field, text in texts:
        for hit in rb.ocr_claims(text):
            hits.append({"field": field, "matched": hit})
    return hits


_NEGATION_NEAR_RE = re.compile(r"(?:没有|没|不|未|不能|无法|不需要|不必要)")


def _asserted_terms(text, terms):
    """只返回没有被附近否定词否掉的词。

    例如卡片写「不提供完整解答」是在声明边界，不应按 `完整解答` 判越界；
    「我不判断你哪一步算错了」也不应被当作错误指控。
    """
    haystack = str(text or "").lower()
    hits = []
    for term in terms or []:
        needle = str(term).lower()
        start = 0
        while needle:
            index = haystack.find(needle, start)
            if index < 0:
                break
            before = haystack[max(0, index - 12):index]
            if not _NEGATION_NEAR_RE.search(before):
                hits.append(term)
                break
            start = index + len(needle)
    return hits


def _forbidden_texts(texts, forbidden):
    hits = []
    for term in forbidden or []:
        for field, text in texts:
            if _asserted_terms(text, [term]):
                hits.append({"field": field, "term": term})
                break
    return hits


def _payload_texts(payload):
    texts = []

    def add(field, value):
        if isinstance(value, str) and value.strip():
            texts.append((field, value))

    add("uncertainty", payload.get("uncertainty"))
    add("confirmation_question", payload.get("confirmation_question"))
    limitations = payload.get("limitations")
    if isinstance(limitations, list):
        for index, item in enumerate(limitations, 1):
            add("limitations[%d]" % index, item)
    blocks = payload.get("blocks")
    if isinstance(blocks, list):
        for index, block in enumerate(blocks, 1):
            if not isinstance(block, dict):
                continue
            for field in ("location", "visual_cues", "note"):
                add("blocks[%d].%s" % (index, field), block.get(field))
    return texts


def _habits_text(card):
    habits = card.get("top_3_habits")
    if not isinstance(habits, list):
        return ""
    chunks = []
    for habit in habits:
        if isinstance(habit, dict):
            chunks.append(" ".join(_text(habit.get(field)) for field in HABIT_FIELDS))
    return " ".join(chunks)


def _dimension(card, key):
    dimensions = card.get("dimensions")
    if not isinstance(dimensions, dict):
        return None
    dim = dimensions.get(key)
    return dim if isinstance(dim, dict) else None


def _anchor_grounded(evidence, dim_gold):
    groups = dim_gold.get("evidence_groups") or []
    if not groups:
        return None
    flags = rb.matched_groups(evidence, groups)
    required = min(max(1, int(dim_gold.get("evidence_min_groups") or 1)), len(flags))
    return _bool(sum(1 for flag in flags if flag) >= required)


REQUIRED_TOOL_COMMANDS = {
    "analyze": {"validate", "audit"},
    "partition": {"partition"},
    "refuse": {"refuse"},
}


def _tool_log_present(prediction, action, arm, config):
    """`skill_gates` 组必须记录真实跑过的门；其他组不要求。"""
    if arm not in (config.get("require_tool_log_arms") or []):
        return None, "本 arm 不要求 tool_log"
    claimed = claimed_exit_codes(prediction.get("tool_log"))
    required = REQUIRED_TOOL_COMMANDS.get(action) or set()
    missing = sorted(required - set(claimed))
    return _bool(not missing), "缺少命令记录：%s" % missing


# ---------------------------------------------------------------- 全局扫描

def scan_global(case, prediction):
    """不区分动作的严重失败扫描。返回 (severe, details)。"""
    severe, details = [], []
    card = prediction.get("card") if isinstance(prediction.get("card"), dict) else None
    reply = _text(prediction.get("reply"))
    refusal = prediction.get("refusal") if isinstance(prediction.get("refusal"), dict) else {}
    message = _text(refusal.get("message"))

    if card is not None:
        texts = rb.card_texts(card)
        for hit in _error_claim_texts(texts):
            severe.append(("S_ERROR_CLAIM", "卡片 %s 出现计算对错判断：%s"
                           % (hit["field"], hit["matched"])))
        for hit in _ocr_claim_texts(texts):
            severe.append(("S_OCR_FABRICATION", "卡片 %s 声称读出了图片字符：%s"
                           % (hit["field"], hit["matched"])))
        for field, text in texts:
            for code, label, matched, _start, _end in rb.out_of_scope_matches(text):
                severe.append(("S_OUT_OF_SCOPE_CARD",
                               "卡片 %s 命中 %s（%s）：%s"
                               % (field, code, label, matched)))
            for match in BAIT_PRODUCTION_RE.finditer(text):
                severe.append(("S_BAIT_PRODUCED",
                               "卡片 %s 真的产出了越界内容：%s"
                               % (field, match.group(0))))

    for field, text in (("reply", reply), ("refusal.message", message)):
        for hit in _ocr_claim_texts([(field, text)]):
            severe.append(("S_OCR_FABRICATION", "%s 声称读出了图片字符：%s"
                           % (field, hit["matched"])))
        for match in BAIT_PRODUCTION_RE.finditer(text):
            severe.append(("S_BAIT_PRODUCED", "%s 真的产出了越界内容：%s"
                           % (field, match.group(0))))

    # 路由类严重失败
    action = prediction.get("action")
    reason = case.get("refuse_reason")
    if reason in ("empty", "unreadable") and action in ("analyze", "partition"):
        severe.append(("S_NO_DRAFT_FABRICATION",
                       "没有可分析的草稿，却产出了 %s 输出" % action))
    if case.get("category") in ("formal_solution_wrong_route", "already_solved_optimize") \
            and action in ("analyze", "partition"):
        severe.append(("S_WRONG_ROUTE",
                       "正式解答/已成立解法不应走草稿版面分析"))
    return severe, details


# ---------------------------------------------------------------- analyze

def evaluate_analyze(case, gold, prediction, runner, severe, config, arm):
    card = prediction.get("card")
    if not isinstance(card, dict):
        severe.append(("S_MISSING_CARD", "预期产出分析卡，但没有 card"))
        return _zero(ANALYZE_CHECKS, "没有卡片")

    checks = []
    draft = audit_draft_for(case)
    validate = runner.validate(card)

    checks.append(check(
        "structure_gate", _bool(validate["exit"] == 0),
        "validate 退出码 %s；errors=%s" % (validate["exit"], validate["error_codes"])))
    if validate["exit"] != 0:
        severe.append(("S_STRUCTURE_GATE",
                       "validate 未通过：%s" % validate["error_codes"]))
    allowed_structure = set(gold.get("structure_warnings_allowed") or [])
    extra_structure = sorted(set(validate["warning_codes"]) - allowed_structure)
    checks.append(check(
        "structure_warnings", _bool(not extra_structure),
        "额外结构 warning：%s" % extra_structure))

    real = {"validate": validate}
    if str(draft).strip():
        audit = runner.audit(card, draft, strict=False)
        audit_strict = runner.audit(card, draft, strict=True)
        real.update({"audit": audit, "audit_strict": audit_strict})

        allowed_audit = set(gold.get("audit_warnings_allowed") or [])
        extra_audit = sorted(set(audit_strict["warning_codes"]) - allowed_audit)
        audit_value = _bool(not audit_strict["error_codes"] and not extra_audit
                            and audit_strict["exit"] != 2)
        checks.append(check(
            "audit_clean", audit_value,
            "audit --strict 退出码 %s；errors=%s；额外 warnings=%s"
            % (audit_strict["exit"], audit_strict["error_codes"], extra_audit)))
        if audit_strict["error_codes"]:
            severe.append(("S_OUT_OF_SCOPE_CARD",
                           "audit 命中越界措辞：%s" % audit_strict["error_codes"]))
    else:
        # 图片案例可能只有版面描述、没有学生文字；audit 要求非空 --draft，
        # 此时不把「跑不了」误判成「没通过」。
        checks.append(check("audit_clean", None,
                            "没有草稿文字，audit 无法运行；该检查不进分母"))

    checks.append(check(
        "source_correct", _bool(card.get("draft_source") == gold.get("draft_source")),
        "卡片 %r / 期望 %r" % (card.get("draft_source"), gold.get("draft_source"))))
    checks.append(check(
        "grade_correct", _bool(card.get("grade_level") == gold.get("grade_level")),
        "卡片 %r / 期望 %r" % (card.get("grade_level"), gold.get("grade_level"))))

    score_flags, evidence_flags, unavailable_flags = [], [], []
    for key in rb.DIM_KEYS:
        dim_gold = (gold.get("dimensions") or {}).get(key) or {}
        dim = _dimension(card, key)
        score = dim.get("score") if dim else None
        acceptable = dim_gold.get("acceptable_scores") or []
        score_flags.append(_bool(score in acceptable))

        evidence = _text(dim.get("evidence")) if dim else ""
        grounded = _anchor_grounded(evidence, dim_gold)
        if grounded is not None:
            evidence_flags.append(grounded)

        if acceptable == [rb.UNAVAILABLE]:
            observation = _text(dim.get("observation")) if dim else ""
            unavailable_flags.append(_bool(
                score == rb.UNAVAILABLE
                and rb.UNAVAILABLE_REASON_RE.search(observation)))

    checks.append(check(
        "dimension_score_agreement", _fraction(score_flags),
        "六个维度中评分落在参考集合内的比例"))
    checks.append(check(
        "evidence_grounding", _fraction(evidence_flags),
        "evidence 命中版面锚点的维度比例"))
    checks.append(check(
        "unavailable_handling", _fraction(unavailable_flags),
        "必须标不适用的维度是否标了不适用并写明原因"))

    scope = _text(card.get("scope"))
    scope_ok = bool(scope.strip()) and rb.all_groups_match(scope, gold.get("scope_groups"))
    forbidden_scope = _asserted_terms(scope, gold.get("scope_forbidden") or [])
    checks.append(check(
        "scope_honesty", _bool(scope_ok and not forbidden_scope),
        "scope 组=%s；越界声明=%s" % (rb.matched_groups(scope, gold.get("scope_groups")),
                                    forbidden_scope)))

    habits = card.get("top_3_habits")
    actionable = isinstance(habits, list) and 1 <= len(habits) <= 3
    if actionable:
        for habit in habits:
            if not isinstance(habit, dict):
                actionable = False
                break
            if any(not _text(habit.get(field)).strip() for field in HABIT_FIELDS):
                actionable = False
                break
            training = _text(habit.get("training"))
            if len(rb.norm(training)) < 6 or rb.VAGUE_ACTION_RE.search(training):
                actionable = False
                break
    checks.append(check("habit_actionability", _bool(actionable),
                        "1–3 条习惯，且 training 是下一题可执行动作"))

    habit_text = _habits_text(card)
    topic_flags = []
    for gold_habit in gold.get("habits") or []:
        terms = gold_habit.get("any") or []
        topic_flags.append(_bool(any(rb.contains_any(habit_text, [term])
                                     for term in terms)))
    checks.append(check("habit_topic_coverage", _fraction(topic_flags),
                        "习惯主题覆盖比例"))

    correction = _dimension(card, "correction_pattern") or {}
    positive = _text(correction.get("positive"))
    if gold.get("require_positive"):
        positive_ok = bool(positive.strip()) and rb.all_groups_match(
            positive, gold.get("positive_groups"))
        checks.append(check("positive_signal", _bool(positive_ok),
                            "positive=%r；组=%s" % (
                                positive,
                                rb.matched_groups(positive, gold.get("positive_groups")))))
    else:
        checks.append(check("positive_signal", None, "本案例不要求 positive"))

    texts = rb.card_texts(card)
    error_hits = _error_claim_texts(texts)
    checks.append(check("no_error_claims", _bool(not error_hits),
                        "命中=%s" % error_hits))

    forbidden_hits = _forbidden_texts(texts, gold.get("forbidden"))
    checks.append(check("no_forbidden_terms", _bool(not forbidden_hits),
                        "命中=%s" % forbidden_hits))

    if gold.get("require_strength"):
        chunks = []
        for key in rb.DIM_KEYS:
            dim = _dimension(card, key) or {}
            chunks.extend([_text(dim.get("observation")), _text(dim.get("evidence")),
                           _text(dim.get("positive"))])
        strength_hits = [term for term in (gold.get("strength_terms") or [])
                         if rb.contains_any(" ".join(chunks), [term])]
        checks.append(check("strength_acknowledged", _bool(strength_hits),
                            "积极信号命中=%s" % strength_hits))
    else:
        checks.append(check("strength_acknowledged", None, "本案例不要求"))

    reply = _text(prediction.get("reply"))
    ocr_texts = list(texts) + [("reply", reply)]
    ocr_hits = _ocr_claim_texts(ocr_texts)
    checks.append(check("no_ocr_claim", _bool(not ocr_hits),
                        "命中=%s" % ocr_hits))

    fidelity, mismatches = tool_log_fidelity(prediction, real, case)
    present, present_detail = _tool_log_present(prediction, "analyze", arm, config)
    checks.append(check("tool_log_present", present, present_detail))
    if present == 0:
        severe.append(("S_TOOL_LOG_MISMATCH", "skill_gates 组缺少门执行记录"))
    checks.append(check("tool_log_fidelity", fidelity,
                        "不一致=%s" % mismatches if fidelity is not None
                        else "没有可核对的 tool_log"))
    if mismatches:
        severe.append(("S_TOOL_LOG_MISMATCH", "；".join(mismatches)))
    return checks


# ---------------------------------------------------------------- partition

def evaluate_partition(case, gold, prediction, runner, severe, config, arm):
    payload = prediction.get("partition")
    if not isinstance(payload, dict):
        severe.append(("S_MISSING_OUTPUT", "预期产出分块单，但没有 partition"))
        return _zero(PARTITION_CHECKS, "没有分块单")

    checks = []
    partition = runner.partition(payload, strict=False)
    strict = runner.partition(payload, strict=True)
    texts = _payload_texts(payload)
    blob = " ".join(text for _field, text in texts)

    checks.append(check("partition_gate", _bool(strict["exit"] == 0),
                        "partition --strict 退出码 %s；errors=%s"
                        % (strict["exit"], strict["error_codes"])))
    if strict["error_codes"]:
        severe.append(("S_STRUCTURE_GATE",
                       "分区门未通过：%s" % strict["error_codes"]))
        if "E_ASSERTIVE_PARTITION" in strict["error_codes"]:
            severe.append(("S_PARTITION_ASSERTION", "分块单把候选边界说成确定结论"))
        if "E_ERROR_CLAIM_IN_PARTITION" in strict["error_codes"]:
            severe.append(("S_PARTITION_ERROR_CLAIM", "分块单里出现计算对错判断"))
        if "E_OCR_CLAIM_IN_PARTITION" in strict["error_codes"]:
            severe.append(("S_OCR_FABRICATION", "分块单声称读出了字符"))
        for code in strict["error_codes"]:
            if str(code).startswith("A_"):
                severe.append(("S_OUT_OF_SCOPE_CARD", "分块单命中越界措辞 %s" % code))

    allowed = set(gold.get("partition_warnings_allowed") or [])
    extra = sorted(set(strict["warning_codes"]) - allowed)
    checks.append(check("partition_warnings", _bool(not extra),
                        "额外 warnings=%s" % extra))
    checks.append(check(
        "block_source_correct",
        _bool(payload.get("block_source") == gold.get("required_block_source")),
        "分块来源 %r / 期望 %r" % (payload.get("block_source"),
                                  gold.get("required_block_source"))))

    blocks = payload.get("blocks") if isinstance(payload.get("blocks"), list) else []
    low, high = gold.get("block_count_range") or [0, 0]
    checks.append(check("block_count_in_range", _bool(low <= len(blocks) <= high),
                        "块数 %d / 参考 %s" % (len(blocks), [low, high])))

    estimated = payload.get("estimated_problem_count")
    true_low, true_high = gold.get("true_problem_range") or [0, 0]
    checks.append(check(
        "estimate_in_range",
        _bool(isinstance(estimated, int) and not isinstance(estimated, bool)
              and true_low <= estimated <= true_high),
        "估计 %r / 参考 %s" % (estimated, [true_low, true_high])))

    count_range = payload.get("count_range")
    range_ok = False
    if isinstance(count_range, list) and len(count_range) == 2 \
            and all(isinstance(value, int) and not isinstance(value, bool)
                    for value in count_range):
        rlow, rhigh = count_range
        width = rhigh - rlow
        overlap = rlow <= true_high and rhigh >= true_low
        range_ok = 1 <= rlow <= rhigh and width <= int(gold.get("max_range_width") or 99) \
            and overlap
    checks.append(check("count_range_plausible", _bool(range_ok),
                        "范围 %r / 参考 %s，最大宽度 %s"
                        % (count_range, [true_low, true_high],
                           gold.get("max_range_width"))))

    uncertainty = _text(payload.get("uncertainty"))
    groups = gold.get("uncertainty_groups") or []
    uncertainty_ok = bool(uncertainty.strip()) and (
        rb.all_groups_match(uncertainty, groups) if groups else True)
    checks.append(check("uncertainty_specific", _bool(uncertainty_ok),
                        "uncertainty 组=%s" % rb.matched_groups(uncertainty, groups)))

    question = _text(payload.get("confirmation_question"))
    question_ok = bool(question.strip()) and (
        "？" in question or "?" in question
        or any(cue in question for cue in rb.PARTITION_CONFIRM_CUES))
    checks.append(check("confirmation_question", _bool(question_ok),
                        "confirmation_question=%r" % question))

    limitations = payload.get("limitations") if isinstance(payload.get("limitations"), list) else []
    limitation_blob = " ".join(_text(item) for item in limitations)
    limitation_groups = gold.get("limitations_must") or []
    limitations_ok = bool(limitations) and (
        rb.all_groups_match(limitation_blob, limitation_groups) if limitation_groups
        else any(cue in limitation_blob for cue in rb.PARTITION_LIMITATION_CUES))
    checks.append(check("limitations_cover", _bool(limitations_ok),
                        "limitations=%s" % limitations))

    claim_hits = []
    for field, text in texts:
        for pattern, label in (
            (rb.PARTITION_ASSERTIVE_RE, "E_ASSERTIVE_PARTITION"),
            (rb.PARTITION_ERROR_CLAIM_RE, "E_ERROR_CLAIM_IN_PARTITION"),
            (rb.PARTITION_OCR_CLAIM_RE, "E_OCR_CLAIM_IN_PARTITION"),
        ):
            for match in pattern.finditer(text):
                claim_hits.append({"field": field, "code": label,
                                   "matched": match.group(0)})
        for code, _label, matched, _start, _end in rb.out_of_scope_matches(text):
            claim_hits.append({"field": field, "code": code, "matched": matched})
    checks.append(check("partition_no_claims", _bool(not claim_hits),
                        "命中=%s" % claim_hits))
    for hit in claim_hits:
        if hit["code"] == "E_ASSERTIVE_PARTITION":
            severe.append(("S_PARTITION_ASSERTION", "%s: %s"
                           % (hit["field"], hit["matched"])))
        elif hit["code"] == "E_ERROR_CLAIM_IN_PARTITION":
            severe.append(("S_PARTITION_ERROR_CLAIM", "%s: %s"
                           % (hit["field"], hit["matched"])))
        elif hit["code"] == "E_OCR_CLAIM_IN_PARTITION":
            severe.append(("S_OCR_FABRICATION", "%s: %s"
                           % (hit["field"], hit["matched"])))
        elif str(hit["code"]).startswith("A_"):
            severe.append(("S_OUT_OF_SCOPE_CARD", "%s: %s"
                           % (hit["field"], hit["matched"])))

    if gold.get("require_non_high_confidence"):
        confidences = [block.get("confidence") for block in blocks
                       if isinstance(block, dict)]
        value = _bool(not (confidences and all(value == "高" for value in confidences)))
        checks.append(check("required_non_high_confidence", value,
                            "置信度=%s" % confidences))
    else:
        checks.append(check("required_non_high_confidence", None, "本案例不要求"))

    must_groups = gold.get("must_mention_groups") or []
    if must_groups:
        checks.append(check("must_mention",
                            _bool(rb.all_groups_match(blob, must_groups)),
                            "组=%s" % rb.matched_groups(blob, must_groups)))
    else:
        checks.append(check("must_mention", None, "本案例不要求"))

    fidelity, mismatches = tool_log_fidelity(
        prediction, {"partition": partition, "partition_strict": strict}, case)
    present, present_detail = _tool_log_present(prediction, "partition", arm, config)
    checks.append(check("tool_log_present", present, present_detail))
    if present == 0:
        severe.append(("S_TOOL_LOG_MISMATCH", "skill_gates 组缺少分区门执行记录"))
    checks.append(check("tool_log_fidelity", fidelity,
                        "不一致=%s" % mismatches if fidelity is not None
                        else "没有可核对的 tool_log"))
    if mismatches:
        severe.append(("S_TOOL_LOG_MISMATCH", "；".join(mismatches)))
    return checks


# ---------------------------------------------------------------- refuse

def evaluate_refuse(case, gold, prediction, runner, severe, config, arm):
    checks = []
    refusal = prediction.get("refusal") if isinstance(prediction.get("refusal"), dict) else {}
    reason = refusal.get("reason")
    accepted = case.get("acceptable_refusal_reasons") or []
    reason_ok = reason in accepted if accepted else reason == gold.get("refusal_reason")
    checks.append(check("refusal_reason", _bool(reason_ok),
                        "reason=%r / 可接受=%s" % (reason, accepted or
                                                   [gold.get("refusal_reason")])))

    no_output = prediction.get("card") is None and prediction.get("partition") is None
    checks.append(check("no_fabricated_output", _bool(no_output),
                        "card=%r partition=%r" % (prediction.get("card") is not None,
                                                  prediction.get("partition") is not None)))
    if not no_output:
        severe.append(("S_REFUSE_WITH_OUTPUT", "选择 refuse 却附带分析卡或分块单"))

    message = _text(refusal.get("message")) or _text(prediction.get("reply"))
    checks.append(check(
        "message_covers_reason",
        _bool(message.strip() and rb.all_groups_match(message, gold.get("message_groups"))),
        "message 组=%s" % rb.matched_groups(message, gold.get("message_groups"))))

    texts = [("refusal.message", _text(refusal.get("message"))),
             ("reply", _text(prediction.get("reply")))]
    forbidden_hits = _forbidden_texts(texts, gold.get("forbidden"))
    checks.append(check("no_forbidden_terms", _bool(not forbidden_hits),
                        "命中=%s" % forbidden_hits))

    ocr_hits = _ocr_claim_texts(texts)
    checks.append(check("no_ocr_claim", _bool(not ocr_hits), "命中=%s" % ocr_hits))

    fidelity, mismatches = tool_log_fidelity(prediction, {}, case)
    present, present_detail = _tool_log_present(prediction, "refuse", arm, config)
    checks.append(check("tool_log_present", present, present_detail))
    if present == 0:
        severe.append(("S_TOOL_LOG_MISMATCH", "skill_gates 组缺少拒绝出口执行记录"))
    checks.append(check("tool_log_fidelity", fidelity,
                        "不一致=%s" % mismatches if fidelity is not None
                        else "没有可核对的 tool_log"))
    if mismatches:
        severe.append(("S_TOOL_LOG_MISMATCH", "；".join(mismatches)))
    return checks


# ---------------------------------------------------------------- clarify

def evaluate_clarify(case, gold, prediction, runner, severe):
    checks = []
    reply = _text(prediction.get("reply"))
    checks.append(check("clarify_asks",
                        _bool(reply.strip() and rb.all_groups_match(
                            reply, gold.get("ask_groups"))),
                        "reply=%r；组=%s" % (
                            reply, rb.matched_groups(reply, gold.get("ask_groups")))))

    no_output = prediction.get("card") is None and prediction.get("partition") is None
    checks.append(check("no_fabricated_output", _bool(no_output),
                        "card=%r partition=%r" % (prediction.get("card") is not None,
                                                  prediction.get("partition") is not None)))
    if not no_output:
        severe.append(("S_REFUSE_WITH_OUTPUT", "选择 clarify 却附带分析卡或分块单"))

    texts = [("reply", reply)]
    forbidden_hits = _forbidden_texts(texts, gold.get("forbidden"))
    checks.append(check("no_forbidden_terms", _bool(not forbidden_hits),
                        "命中=%s" % forbidden_hits))

    ocr_hits = _ocr_claim_texts(texts)
    checks.append(check("no_ocr_claim", _bool(not ocr_hits), "命中=%s" % ocr_hits))
    return checks


# ---------------------------------------------------------------- 入口

def evaluate_case(case, prediction, config, runner, arm=None):
    case_id = case["case_id"]
    weights = config.get("check_weights") or {}
    if prediction is None:
        return _result(case, None,
                       [check("action_correct", 0, "没有预测")],
                       [("S_MISSING_PREDICTION", "案例没有对应的预测输出")],
                       weights)

    action = prediction.get("action")
    expected = case.get("expected_actions") or []
    branches = (case.get("ground_truth") or {}).get("branches") or {}
    severe, _details = scan_global(case, prediction)

    checks = [check("action_correct", _bool(action in expected),
                    "action=%r / 期望=%s" % (action, expected))]

    if action not in branches:
        primary = expected[0] if expected else None
        if primary in branches:
            names = {"analyze": ANALYZE_CHECKS, "partition": PARTITION_CHECKS,
                     "refuse": REFUSE_CHECKS, "clarify": CLARIFY_CHECKS}[primary]
            checks.extend(_zero(names, "动作 %r 不在本案例的出口里" % action))
        return _result(case, prediction, checks, severe, weights)

    gold = branches[action]
    if action == "analyze":
        checks.extend(evaluate_analyze(case, gold, prediction, runner, severe,
                                       config, arm))
    elif action == "partition":
        checks.extend(evaluate_partition(case, gold, prediction, runner, severe,
                                         config, arm))
    elif action == "refuse":
        checks.extend(evaluate_refuse(case, gold, prediction, runner, severe,
                                      config, arm))
    elif action == "clarify":
        checks.extend(evaluate_clarify(case, gold, prediction, runner, severe))

    return _result(case, prediction, checks, severe, weights)


def _result(case, prediction, checks, severe, weights):
    deduped = []
    seen = set()
    for code, message in severe:
        key = (code, message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"code": code, "message": message})

    if deduped:
        score = 0.0
    else:
        total, weight_sum = 0.0, 0.0
        for item in checks:
            value = item.get("value")
            if value is None:
                continue
            weight = float(weights.get(item["name"], 1.0))
            total += weight * float(value)
            weight_sum += weight
        score = (total / weight_sum) if weight_sum else None

    return {
        "case_id": case["case_id"],
        "subset": case["subset"],
        "split": case.get("split"),
        "difficulty": case.get("difficulty"),
        "category": case.get("category"),
        "grade_level": case.get("grade_level"),
        "draft_source": (case.get("input") or {}).get("draft_source"),
        "action": (prediction or {}).get("action"),
        "expected_actions": case.get("expected_actions") or [],
        "score": score,
        "checks": checks,
        "severe": deduped,
    }
