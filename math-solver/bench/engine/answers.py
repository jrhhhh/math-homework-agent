# -*- coding: utf-8 -*-
"""答案层检查。

支持四类结构化答案：
- value_set：数值集合（支持分数与 ±）
- interval_set：区间并集
- text_forms：每个关键词组至少命中一个
- piecewise：按参数分支检查“标签 + 对应结论”
- empty_set：无解 / 空集

这些检查面向本基准的固定案例，不是通用数学等价判定器。
"""

import re
from fractions import Fraction


def clean(text):
    text = str(text or "")
    text = text.replace("−", "-").replace("−", "-")
    text = text.replace("，", ",").replace("、", ",").replace("；", ";")
    text = text.replace("　", " ")
    return text


def norm_light(text):
    text = clean(text)
    text = re.sub(r"\s+", "", text)
    return text.lower()


def norm_math(text):
    text = norm_light(text)
    return (text.replace("≤", "<=").replace("≥", ">=").replace("≠", "!=")
            .replace("²", "^2").replace("³", "^3"))


def answer_text(output):
    return str((output.get("solution") or {}).get("answer") or "")


def solution_text(output):
    """答案 + 条件 + 推导，用于分支与必需项检查。"""
    solution = output.get("solution") or {}
    parts = [str(solution.get("answer") or "")]
    parts.extend(str(item) for item in (solution.get("conditions") or []))
    for step in solution.get("derivation") or []:
        if isinstance(step, dict):
            parts.append(str(step.get("expression") or ""))
            parts.append(str(step.get("justification") or ""))
    return "；".join(parts)


def verification_text(output):
    verification = output.get("verification") or {}
    parts = []
    for check in verification.get("checks") or []:
        if isinstance(check, dict):
            parts.append(str(check.get("name") or ""))
            parts.append(str(check.get("details") or ""))
    parts.extend(str(item) for item in (verification.get("issues") or []))
    return "；".join(parts)


def numbers_in(text):
    text = norm_light(text)
    text = text.replace("²", "^2").replace("³", "^3")
    # ±3 -> +3,-3（本基准的固定形式）
    text = re.sub(r"±\s*(\d+(?:\.\d+)?(?:/\d+)?)",
                  lambda m: f"+{m.group(1)},-{m.group(1)}", text)
    # 去掉 x=、x_1=、S_5=、q=、a= 这类标签，保留数值
    text = re.sub(r"[a-zA-Zα-ωΑ-Ω]_?\d*=", "", text)
    values = set()
    for token in re.findall(r"[-+]?\d+(?:\.\d+)?(?:/\d+)?", text):
        try:
            if "/" in token:
                numerator, denominator = token.split("/", 1)
                values.add(Fraction(int(numerator), int(denominator)))
            else:
                values.add(Fraction(token))
        except (ValueError, ZeroDivisionError):
            continue
    return values


def check_value_set(spec, output):
    expected = {Fraction(str(value)) for value in spec["values"]}
    actual = numbers_in(answer_text(output))
    ok = actual == expected
    return ok, f"expected={sorted(map(str, expected))} actual={sorted(map(str, actual))}"


def check_text_forms(spec, output):
    text = norm_light(answer_text(output))
    missing = []
    for group in spec["groups"]:
        if not any(norm_light(option) in text for option in group):
            missing.append(group)
    return not missing, f"missing={missing}" if missing else "all groups matched"


INTERVAL_RE = re.compile(
    r"([\[\(])\s*(inf|-inf|[-+]?\d+(?:\.\d+)?(?:/\d+)?)\s*,\s*"
    r"(inf|-inf|[-+]?\d+(?:\.\d+)?(?:/\d+)?)\s*([\]\)])"
)


def _endpoint(value):
    if value in ("inf", "+inf"):
        return float("inf")
    if value in ("-inf", "inf-"):
        return -float("inf")
    return float(Fraction(value))


def parse_intervals(text):
    text = norm_light(text).replace("∞", "inf").replace("+inf", "inf")
    intervals = set()
    for lo_bracket, lo, hi, hi_bracket in INTERVAL_RE.findall(text):
        intervals.add((
            _endpoint(lo),
            _endpoint(hi),
            lo_bracket == "[",
            hi_bracket == "]",
        ))
    return intervals


def check_interval_set(spec, output):
    expected = set()
    for item in spec["intervals"]:
        lo = float("-inf") if item["lo"] is None else float(item["lo"])
        hi = float("inf") if item["hi"] is None else float(item["hi"])
        expected.add((lo, hi, bool(item["lo_closed"]), bool(item["hi_closed"])))
    actual = parse_intervals(answer_text(output))
    ok = actual == expected
    return ok, f"expected={sorted(expected)} actual={sorted(actual)}"


def _segments(text):
    parts = re.split(r"[;。\n]", clean(text))
    return [norm_math(part) for part in parts if part.strip()]


def check_piecewise(spec, output):
    combined = solution_text(output)
    segments = _segments(combined)
    missing = []
    for case in spec["cases"]:
        label = norm_math(case["label"])
        token_groups = case["tokens"]
        found = False
        for segment in segments:
            if label not in segment:
                continue
            if all(any(norm_math(token) in segment for token in group)
                   for group in token_groups):
                found = True
                break
        if not found:
            missing.append(case["label"])
    return not missing, f"missing cases={missing}" if missing else "all cases matched"


def check_empty_set(spec, output):
    text = norm_light(answer_text(output))
    ok = any(marker in text for marker in ("无解", "空集", "∅", "没有解", "不存在解"))
    return ok, "empty-set marker found" if ok else "no empty-set marker"


def check_answer(spec, output):
    kind = spec.get("kind")
    if kind == "value_set":
        return check_value_set(spec, output)
    if kind == "interval_set":
        return check_interval_set(spec, output)
    if kind == "text_forms":
        return check_text_forms(spec, output)
    if kind == "piecewise":
        return check_piecewise(spec, output)
    if kind == "empty_set":
        return check_empty_set(spec, output)
    return False, f"unknown answer_check kind: {kind}"


def text_contains_groups(text, groups):
    normalized = norm_light(text)
    missing = []
    for group in groups:
        if not any(norm_light(option) in normalized for option in group):
            missing.append(group)
    return not missing, missing
