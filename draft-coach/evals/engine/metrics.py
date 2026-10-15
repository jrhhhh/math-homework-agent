# -*- coding: utf-8 -*-
"""自动指标计算。仅用标准库，不含任何模型判断。

分层原则（见 docs/DESIGN.md §2）：这里只算**自动**指标；证据是否支持结论、
解释与改法是否正确、六维观察是否属实——一律留空（None），交给
model_assisted / human 层填充。空值不参与分母，绝不当作 0 分或满分。

越界措辞、风险句限定词、题号标记这些规则**直接复用 `scripts/_rules.py` 的常量**，
不在这里另抄一份，避免基准与技能漂移。
"""

import importlib.util
import re
from pathlib import Path

from cases import DIM_KEYS, draft_tokens, normalise, normalise_strict

_RULES_PATH = Path(__file__).resolve().parents[2] / "scripts" / "_rules.py"


def load_gate_module(path=None):
    """按路径加载技能脚本的常量模块（不重抄正则）。

    常量只在 `scripts/_rules.py` 存一份：六维键名、越界正则、REFUSALS 等若有第二份，
    改一处忘另一处必然不一致。
    """
    path = Path(path or _RULES_PATH)
    spec = importlib.util.spec_from_file_location("draft_coach_rules", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GATE = load_gate_module()


# ------------------------------------------------------------------ 匹配

def pred_errors(card):
    """从卡片里取出错误条目；没有卡片或结构不对时返回 []。"""
    if not isinstance(card, dict):
        return []
    block = card.get("error_check")
    if not isinstance(block, dict) or not isinstance(block.get("errors"), list):
        return []
    return [item for item in block["errors"] if isinstance(item, dict)]


def pred_fields(pred):
    """预测里参与匹配的文本字段（各自归一化、**不拼接**）。

    不能把 evidence 与 location 拼成一个串再找子串：归一化会去掉空白，两个字段
    的残尾会首尾相接造出草稿里根本没有的式子。实例：evidence 与 location 都是
    `x=12/7`，拼起来得到 `x=12/7x=12/7`，其中意外含有 `7x=12`，于是这条预测被
    错判成命中了 gold 里 `7x=12` 那条错误，真错反而成了假阳性。
    """
    return [key for key in (normalise_strict(pred.get("evidence") or ""),
                            normalise_strict(pred.get("location") or "")) if key]


def match_one(pred, gold_errors):
    """一条预测匹配到哪条 gold？返回 error_id 或 None。

    匹配口径（DESIGN §3.1）：gold 的某个 evidence_anchor 逐字出现在预测的
    evidence 或 location 里。**匹配只说明引用的是草稿那处，不说明那处真的错了。**

    用 normalise_strict（保留括号与运算符）：否则原式 `2(x+3)=14` 与漏乘后的
    `2x+3=14` 会归一成同一个串，答案只要引用原式就会被误判成命中了那条错误。
    """
    fields = pred_fields(pred)
    if not fields:
        return None
    for gold in gold_errors:
        if not isinstance(gold, dict):
            continue
        for anchor in gold.get("evidence_anchor") or []:
            key = normalise_strict(anchor)
            if key and any(key in field for field in fields):
                return gold.get("error_id")
    return None


def assign(preds, gold_errors):
    """把预测逐条匹配到 gold。返回 (匹配结果列表, 被判为假阳性的下标列表)。

    同一条 gold 被多条预测命中时，第一条算命中，其余按假阳性计。
    """
    taken, matches, false_positives = set(), [], []
    for index, pred in enumerate(preds):
        target = match_one(pred, gold_errors)
        if target is not None and target not in taken:
            taken.add(target)
            matches.append((index, target))
        else:
            # 命中已被占用的 gold，或完全匹配不上：都算假阳性
            false_positives.append(index)
    return matches, false_positives


def required_gold(case, config):
    """参与 Precision / Recall 的 gold 条目：kind 在白名单里且 must_report。"""
    rule = config.get("counting_rule", {})
    kinds = set(rule.get("precision_recall_kinds", ["root", "independent"]))
    require_must_report = rule.get("require_must_report", True)
    out = []
    for gold in case.get("gold_errors") or []:
        if not isinstance(gold, dict):
            continue
        if gold.get("kind") not in kinds:
            continue
        if require_must_report and not gold.get("must_report"):
            continue
        out.append(gold)
    return out


# ------------------------------------------------------------------ 证据

def evidence_exists(pred, draft):
    """预测的 evidence 里至少有一个记号真的出现在草稿里吗？"""
    evidence = pred.get("evidence") or ""
    if not evidence.strip():
        return False
    draft_norm = normalise(draft)
    if not draft_norm:
        return False
    for token in draft_tokens(evidence):
        if token[0].isdigit():
            if re.search(r"(?<!\d)" + re.escape(token) + r"(?!\d)", draft_norm):
                return True
        elif token in draft_norm:
            return True
    # 记号都没有时，退一步看证据片段本身是否逐字出现在草稿里
    return bool(normalise(evidence)) and normalise(evidence)[:12] in draft_norm


def boundary_hits(text):
    """扫描一段文字命中的越界措辞，返回 A 组代码列表。

    与技能自己的 `audit` 走**同一个函数**（`_rules.out_of_scope_codes`），
    包括那条否定豁免：「这一项我没有打分」是谢绝评分，不是越界评分。
    两边若各写一份，改一处忘另一处必然漂移。
    """
    return GATE.out_of_scope_codes(text)


REFUSAL_TEXTS = tuple(message for _error, message, _code in GATE.REFUSALS.values())


def strip_refusal_wording(text):
    """去掉技能自己的标准拒绝话术。

    那三句话本身就**必须**点名「变式题」「复习计划」才能把它们退回去（「要变式题、
    复习计划，请交给对应的技能」），拿越界措辞规则去扫它必然误报。它是技能自己
    写的合规范本，不是越界。答案若真去出变式题，写的是自己的话，照样会被扫到。
    """
    for message in REFUSAL_TEXTS:
        text = text.replace(message, "")
    return text


def scan_texts(card, response):
    """把卡片的所有文字字段摊平，连同交付文字一起扫。"""
    texts = [strip_refusal_wording(response or "")]
    if isinstance(card, dict):
        texts += [text for _field, text in GATE.card_texts(card)]
    return texts


def refusal_reasons_in(text):
    """回答里出现了哪几条标准拒绝话术。"""
    return sorted(reason for reason, (_err, message, _code) in GATE.REFUSALS.items()
                  if message in (text or ""))


# ------------------------------------------------------------------ 动作判定

def predict_action(prediction):
    """从一份输出判定实际动作：analyze / refuse / clarify / unclear。"""
    if prediction.get("card") is not None:
        return "analyze"
    response = prediction.get("response") or ""
    if refusal_reasons_in(response):
        return "refuse"
    if "？" in response or "?" in response or "麻烦" in response or "请补充" in response:
        return "clarify"
    return "unclear"


# ------------------------------------------------------------------ 结构

def dimension_block(card):
    if not isinstance(card, dict):
        return None
    dims = card.get("dimensions")
    return dims if isinstance(dims, dict) else None


def dimension_complete(card):
    """六维齐全、键名固定、每维四字段齐全，且习惯恰好三条、每条三字段。"""
    dims = dimension_block(card)
    if dims is None or set(dims) != set(DIM_KEYS):
        return False
    for key in DIM_KEYS:
        item = dims.get(key)
        if not isinstance(item, dict):
            return False
        for field in ("score", "observation", "evidence", "risk"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                return False
        if "positive" in item and key != "correction_pattern":
            return False
    habits = card.get("top_3_habits")
    if not isinstance(habits, list) or len(habits) != 3:
        return False
    for habit in habits:
        if not isinstance(habit, dict):
            return False
        for field in ("habit", "impact", "training"):
            if not isinstance(habit.get(field), str) or not habit[field].strip():
                return False
    return True


def label_match(card, case):
    """标签与 gold 一致的比例；unevaluable 的维度不进门。返回 None 表示无维度可判。"""
    dims = dimension_block(card)
    gold_dims = case.get("gold_dimensions")
    if dims is None or not isinstance(gold_dims, dict):
        return None
    hit = total = 0
    for key in DIM_KEYS:
        gold = gold_dims.get(key)
        if not isinstance(gold, dict) or gold.get("unevaluable"):
            continue
        item = dims.get(key)
        if not isinstance(item, dict):
            total += 1
            continue
        total += 1
        if (item.get("score") or "").strip() == gold.get("label"):
            hit += 1
    return (hit / total) if total else None


def risk_form_ok(card):
    """risk 必须是假设句：出现后果词却没有限定词即不合格。"""
    dims = dimension_block(card)
    if dims is None:
        return None
    checked = 0
    for key in DIM_KEYS:
        item = dims.get(key)
        if not isinstance(item, dict):
            continue
        risk = item.get("risk")
        if not isinstance(risk, str) or not risk.strip():
            continue
        checked += 1
        if GATE.RISK_CONSEQUENCE_RE.search(risk) and not GATE.RISK_HEDGE_RE.search(risk):
            return False
    return True if checked else None


def positive_signal_ok(card, case):
    """应有积极信号的维度上，答案有没有给出 positive。"""
    dims = dimension_block(card)
    gold_dims = case.get("gold_dimensions") or {}
    expected = [key for key in DIM_KEYS
                if isinstance(gold_dims.get(key), dict) and gold_dims[key].get("positive_expected")]
    if not expected:
        return None
    if dims is None:
        return False
    for key in expected:
        item = dims.get(key)
        if not isinstance(item, dict) or not str(item.get("positive") or "").strip():
            return False
    return True


def utilization_ok(card, case):
    """没有最终解答时利用率应标「不适用」；有最终解答时不应标。"""
    dims = dimension_block(card)
    if dims is None:
        return None
    item = dims.get("draft_to_solution")
    if not isinstance(item, dict):
        return None
    score = (item.get("score") or "").strip()
    has_solution = bool((case.get("input", {}).get("final_solution") or "").strip())
    if has_solution:
        return score != "不适用"
    return score == "不适用"


# ------------------------------------------------------------------ 主入口

def automatic_metrics(case, prediction, config):
    """算一个 (案例, 输出) 上的全部自动指标。值为 0/1，或 None（不适用 / 非自动层）。"""
    card = prediction.get("card")
    response = prediction.get("response") or ""
    draft = case.get("input", {}).get("draft") or ""
    gold = case.get("gold_errors") or []
    preds = pred_errors(card)
    matches, fps = assign(preds, gold)
    matched_ids = {target for _index, target in matches}
    required = required_gold(case, config)
    required_ids = {g.get("error_id") for g in required}
    tp = len(matched_ids & required_ids)
    fp = len(fps)
    out = {}

    # --- A 数学错误定位
    out["error_precision"] = (tp / (tp + fp)) if (tp + fp) else None
    out["error_recall"] = (tp / len(required)) if required else None
    if required:
        by_id = {g.get("error_id"): g for g in required}
        localised = 0
        cited_fields = [field for p in preds for field in pred_fields(p)]
        for error_id in matched_ids & required_ids:
            passed = False
            for anchor in by_id[error_id].get("evidence_anchor") or []:
                key = normalise_strict(anchor)
                if key and any(key in field for field in cited_fields):
                    passed = True
                    break
            if passed:
                localised += 1
        out["error_localization"] = localised / len(required)
    else:
        out["error_localization"] = None

    no_error_case = not gold
    out["no_error_identification"] = (len(preds) == 0) if no_error_case else None

    propagated = [g for g in gold if g.get("kind") == "propagated"]
    if propagated:
        roots = [g for g in gold if g.get("kind") == "root"]
        # 传播识别：有没有把根错那一步指出来。指出来不等于说得对，那要走模型辅助层。
        out["propagation_quality"] = 1 if any(r.get("error_id") in matched_ids for r in roots) else 0
    else:
        out["propagation_quality"] = None

    out["location_descriptor_correct"] = None    # model_assisted
    out["fix_correctness"] = None                # model_assisted
    out["explanation_correctness"] = None        # model_assisted

    # --- B 证据忠实度
    if preds:
        exists = [evidence_exists(p, draft) for p in preds]
        out["evidence_existence_rate"] = sum(exists) / len(exists)
    else:
        out["evidence_existence_rate"] = None
    out["evidence_support_rate"] = None          # model_assisted
    out["minimal_fix_compliance"] = None         # model_assisted
    texts = scan_texts(card, response)
    out["no_full_solution_rewrite"] = 0 if any("A_SOLUTION" in boundary_hits(t) for t in texts) else 1

    # --- C 六维
    out["dimension_completeness"] = dimension_complete(card) if isinstance(card, dict) else None
    out["dimension_label_match"] = label_match(card, case)
    out["risk_form"] = risk_form_ok(card)
    out["positive_signal"] = positive_signal_ok(card, case)
    out["utilization_handling"] = utilization_ok(card, case)
    out["dimension_evidence_grounded"] = None    # model_assisted

    # --- D 边界与拒绝
    expected = case.get("expected_action")
    actual = predict_action(prediction)
    out["action_accuracy"] = int(actual == expected)
    if expected == "refuse":
        matched_reasons = refusal_reasons_in(response)
        want = case.get("refuse_reason")
        out["refuse_reason_accuracy"] = int(want in matched_reasons) if matched_reasons else 0
        out["refusal_wording_match"] = int(bool(matched_reasons))
    else:
        out["refuse_reason_accuracy"] = None
        out["refusal_wording_match"] = None
    out["over_refusal_avoidance"] = (int(actual == "analyze") if expected == "analyze" else None)
    violation = any(boundary_hits(t) for t in texts)
    out["no_boundary_violation"] = int(not violation)
    out["clarify_quality"] = None                # model_assisted

    # --- E 复杂草稿
    multi = bool(GATE.PROBLEM_MARKER_RE.findall(draft)) and len(
        set(m.strip() for m in GATE.PROBLEM_MARKER_RE.findall(draft))) >= 2
    if case.get("subset") == "E_complex_drafts" or multi:
        out["cross_block_false_positive_avoidance"] = int(fp == 0)
    else:
        out["cross_block_false_positive_avoidance"] = None
    out["multi_problem_handling"] = None         # model_assisted
    out["evaluable_scope_respected"] = None      # model_assisted
    out["mixed_content_reading"] = None          # model_assisted

    # --- F 输出与工具合规（需要重放的部分由 run_gates.py 填）
    if card is None:
        out["json_parseable"] = None
    else:
        out["json_parseable"] = int(isinstance(card, dict))
    for name in ("structure_valid", "audit_clean", "tool_log_fidelity", "exit_code_reported"):
        out.setdefault(name, None)
    out["retry_policy_followed"] = None           # human

    return out


def severe_failures(case, prediction, config):
    """判定可自动判定的严重失败。返回 [(编号, 说明)]。"""
    found = []
    card = prediction.get("card")
    draft = case.get("input", {}).get("draft") or ""
    preds = pred_errors(card)
    gold = case.get("gold_errors") or []
    matches, fps = assign(preds, gold)

    # S1 编造证据：证据里连一个草稿记号都没有
    for index in fps:
        if not evidence_exists(preds[index], draft):
            found.append(("S1", "错误条目「%s」的证据在草稿里找不到任何记号"
                          % (preds[index].get("evidence") or "")[:40]))
            break

    # S2 把明确正确的步骤误判为错误：假阳性的锚点落在 gold_correct_steps 上
    correct_anchors = [a for step in case.get("gold_correct_steps") or []
                       for a in step.get("evidence_anchor") or []]
    for index in fps:
        fields = pred_fields(preds[index])
        for anchor in correct_anchors:
            key = normalise_strict(anchor)
            if key and any(key in field for field in fields):
                found.append(("S2", "把正确步骤 %r 报成了错误" % anchor))
                break
        else:
            continue
        break

    # S4 没有草稿却伪造草稿分析
    if not draft.strip() and preds:
        found.append(("S4", "没有草稿却给出了 %d 条错误" % len(preds)))

    # S6 明显越界（与 A 组规则同一套）
    texts = scan_texts(card, prediction.get("response"))
    hits = sorted({code for text in texts for code in boundary_hits(text)})
    if hits:
        found.append(("S6", "命中越界措辞：%s" % "、".join(hits)))

    # S5 由 run_gates.py 在重放后判定
    return found
