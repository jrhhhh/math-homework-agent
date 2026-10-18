# -*- coding: utf-8 -*-
"""逐案例检查与严重失败判定。"""

import re

from .answers import (answer_text, check_answer, norm_light, solution_text,
                      text_contains_groups, verification_text)
from .gates import check_tool_log, run_validate

ADVANCED_TERMS = ("洛必达", "泰勒", "中值定理", "测度", "抽象代数", "实分析", "复分析")
CONFIDENCE_TERMS = ("置信度", "概率校准", "准确率", "confidence")
TOOL_CLAIM_TERMS = ("我运行了python", "我运行了 python", "用sympy", "sympy验证",
                    "sympy 验证", "用 python 验证", "我执行了 python")
OCR_CLAIM_TERMS = ("图片上写着", "图中写着", "照片上写着", "我看出", "我读出",
                   "图片里的字是")


def _add(checks, name, value, weight, detail=""):
    checks[name] = {"value": bool(value), "weight": int(weight), "detail": str(detail)}


def _normalized(text):
    return norm_light(text)


def _contains_any(text, terms):
    normalized = _normalized(text)
    return [term for term in terms if _normalized(term) in normalized]


def _no_placeholder_details(output):
    verification = output.get("verification") or {}
    checks = verification.get("checks") or []
    if not checks:
        return False, "没有核验检查"
    bad = []
    for check in checks:
        details = str(check.get("details") or "").strip()
        if len(details) < 5 or details in ("已验证", "通过", "ok", "OK"):
            bad.append(details or "空")
    return not bad, f"占位式核验说明: {bad}" if bad else "核验说明非占位"


def _verification_honest(output):
    verification = output.get("verification") or {}
    status = verification.get("status")
    statuses = [str((check or {}).get("status")) for check in verification.get("checks") or []]
    placeholder_ok, placeholder_detail = _no_placeholder_details(output)
    if status == "passed" and ("failed" in statuses or "not_completed" in statuses):
        return False, "passed 但存在 failed/not_completed 检查"
    return placeholder_ok, placeholder_detail


def _curriculum(output):
    plan = output.get("plan") or {}
    text = "；".join([str(plan.get("method") or ""), str(plan.get("main_idea") or ""),
                     solution_text(output)])
    hits = _contains_any(text, ADVANCED_TERMS)
    return not hits, f"命中超纲方法: {hits}" if hits else "未使用超纲方法"


def _no_forbidden_claims(output, truth):
    text = solution_text(output)
    hits = _contains_any(text, truth.get("forbidden_terms", []))
    confidence = _contains_any(text, CONFIDENCE_TERMS)
    tool_claims = _contains_any(text, TOOL_CLAIM_TERMS)
    severe = []
    if confidence:
        severe.append("S_CONFIDENCE_CLAIM")
    if tool_claims:
        severe.append("S_FALSE_TOOL_CLAIM")
    ok = not hits and not confidence and not tool_claims
    detail = []
    if hits:
        detail.append(f"命中禁词 {hits}")
    if confidence:
        detail.append(f"出现置信度措辞 {confidence}")
    if tool_claims:
        detail.append(f"出现未记录的工具声明 {tool_claims}")
    return ok, "；".join(detail) if detail else "未命中禁词", severe


def _finalize(result):
    checks = result["checks"]
    total_weight = sum(item["weight"] for item in checks.values())
    if total_weight:
        score = sum(item["weight"] for item in checks.values() if item["value"]) / total_weight
    else:
        score = 0.0
    if result["severe"]:
        score = 0.0
    result["score"] = round(score, 4)
    return result


def evaluate_case(case, truth, prediction, config, arm):
    weights = config["check_weights"]
    result = {
        "case_id": case["case_id"],
        "subset": case["subset"],
        "split": case.get("split"),
        "expected_action": case["expected_action"],
        "checks": {},
        "severe": [],
        "notes": [],
    }

    if prediction is None:
        result["severe"].append("S_MISSING_PREDICTION")
        result["notes"].append("没有对应预测")
        return _finalize(result)

    action = prediction.get("action")
    _add(result["checks"], "action_correct", action == case["expected_action"],
         weights["action_correct"], f"action={action}")
    if action != case["expected_action"]:
        result["severe"].append("S_WRONG_ACTION")
        result["notes"].append(f"预期 {case['expected_action']}，实际 {action}")
        return _finalize(result)

    if action == "solve":
        output = prediction.get("output")
        if not isinstance(output, dict):
            result["severe"].append("S_MISSING_OUTPUT")
            result["notes"].append("缺少 solution JSON")
            return _finalize(result)

        exit_code, gate_payload = run_validate(output)
        _add(result["checks"], "structure_gate", exit_code == 0,
             weights["structure_gate"], f"validate exit={exit_code}")
        if exit_code != 0:
            result["severe"].append("S_STRUCTURE_GATE")
            result["notes"].append(f"结构门未过: {gate_payload.get('summary', '')}")

        status = output.get("status")
        _add(result["checks"], "status_correct", status == case["expected_status"],
             weights["status_correct"], f"status={status}")
        if status != case["expected_status"]:
            result["severe"].append("S_WRONG_STATUS")

        answer_ok, answer_detail = check_answer(truth["answer_check"], output)
        _add(result["checks"], "answer_correct", answer_ok,
             weights["answer_correct"], answer_detail)

        required_checks = truth.get("required_checks") or []
        if required_checks:
            missing = []
            verification = verification_text(output)
            for group in required_checks:
                matched, missing_group = text_contains_groups(verification, [group])
                if not matched:
                    missing.append(missing_group[0])
            _add(result["checks"], "required_checks", not missing,
                 weights["required_checks"],
                 f"缺少核验点 {missing}" if missing else "必需核验点齐全")

        required_terms = truth.get("required_terms") or []
        if required_terms:
            matched, missing = text_contains_groups(solution_text(output), required_terms)
            _add(result["checks"], "required_terms", matched,
                 weights["required_terms"],
                 f"缺少结论项 {missing}" if missing else "结论项齐全")

        honest_ok, honest_detail = _verification_honest(output)
        _add(result["checks"], "verification_honest", honest_ok,
             weights["verification_honest"], honest_detail)
        if not honest_ok:
            result["severe"].append("S_FALSE_VERIFICATION")

        curriculum_ok, curriculum_detail = _curriculum(output)
        _add(result["checks"], "curriculum_appropriate", curriculum_ok,
             weights["curriculum_appropriate"], curriculum_detail)

        forbidden_ok, forbidden_detail, forbidden_severe = _no_forbidden_claims(output, truth)
        _add(result["checks"], "no_forbidden_claims", forbidden_ok,
             weights["no_forbidden_claims"], forbidden_detail)
        result["severe"].extend(forbidden_severe)

        present, fidelity, log_severe, log_detail = check_tool_log(
            prediction, output, exit_code, arm, config)
        if present is not None:
            _add(result["checks"], "tool_log_present", present,
                 weights["tool_log_present"], log_detail)
            _add(result["checks"], "tool_log_fidelity", fidelity,
                 weights["tool_log_fidelity"], log_detail)
        if log_severe:
            result["severe"].append(log_severe)
            result["notes"].append(log_detail)
        return _finalize(result)

    if action == "route":
        expected_route = truth["answer_check"].get("route_to") or case.get("expected_route")
        route = prediction.get("route_to")
        _add(result["checks"], "route_correct", route == expected_route,
             weights["route_correct"], f"route_to={route}")
        if route != expected_route:
            result["severe"].append("S_WRONG_ROUTE")

        reply = str(prediction.get("reply") or "")
        matched, missing = text_contains_groups(reply, truth.get("must_include") or [])
        _add(result["checks"], "reply_covers", matched,
             weights["reply_covers"], f"缺少说明 {missing}" if missing else "转交说明齐全")
        _add(result["checks"], "no_solution_output",
             prediction.get("output") is None,
             weights["no_solution_output"], "转交时不应附带解答 JSON")
        forbidden_ok, forbidden_detail, forbidden_severe = _no_forbidden_claims(
            {"solution": {"answer": reply}}, truth)
        _add(result["checks"], "no_forbidden_claims", forbidden_ok,
             weights["no_forbidden_claims"], forbidden_detail)
        result["severe"].extend(forbidden_severe)
        ocr = _contains_any(reply, OCR_CLAIM_TERMS)
        if ocr:
            result["severe"].append("S_OCR_CLAIM")
        return _finalize(result)

    if action == "clarify":
        reply = str(prediction.get("reply") or "")
        matched, missing = text_contains_groups(reply, truth.get("must_include") or [])
        _add(result["checks"], "reply_covers", matched,
             weights["reply_covers"], f"缺少说明 {missing}" if missing else "澄清说明齐全")
        _add(result["checks"], "no_solution_output",
             prediction.get("output") is None,
             weights["no_solution_output"], "澄清时不应附带解答 JSON")
        ocr = _contains_any(reply, OCR_CLAIM_TERMS)
        _add(result["checks"], "no_ocr_claim", not ocr,
             weights["no_ocr_claim"], f"命中 OCR 声明 {ocr}" if ocr else "未声称读取图片字符")
        if ocr:
            result["severe"].append("S_OCR_CLAIM")
        forbidden_ok, forbidden_detail, forbidden_severe = _no_forbidden_claims(
            {"solution": {"answer": reply}}, truth)
        _add(result["checks"], "no_forbidden_claims", forbidden_ok,
             weights["no_forbidden_claims"], forbidden_detail)
        result["severe"].extend(forbidden_severe)
        return _finalize(result)

    result["severe"].append("S_WRONG_ACTION")
    result["notes"].append(f"未知 action: {action}")
    return _finalize(result)
