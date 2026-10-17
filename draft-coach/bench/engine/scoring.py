# -*- coding: utf-8 -*-
"""把逐案例结果合成子集分、总分与诊断性指标。

口径：
- 案例分 = 适用检查的加权平均；有严重失败时**直接记 0**，不被其他检查抵消。
- 子集分 = 该子集案例分的算术平均。
- 总分 = 子集分按 config 权重加权；缺失子集时重新归一化并写明。
- `None` 不是 0 分：不适用的检查不进分母。
"""

import math

from .checks import CHECK_NAMES


def wilson(successes, total, z=1.96):
    if not total:
        return None
    phat = successes / total
    denominator = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / denominator
    return {"low": max(0.0, centre - margin), "high": min(1.0, centre + margin)}


def rate(values, z=1.96):
    kept = [value for value in values if value is not None]
    if not kept:
        return {"numerator": 0, "denominator": 0, "rate": None, "ci": None,
                "status": "未运行或不适用"}
    total = sum(kept)
    binary = all(value in (0, 1) for value in kept)
    return {
        "numerator": round(total, 4),
        "denominator": len(kept),
        "rate": total / len(kept),
        "ci": wilson(int(total), len(kept), z) if binary else None,
        "ci_note": None if binary else "含分数值，不适用二项区间",
        "status": "ok",
    }


def _mean(values):
    kept = [value for value in values if value is not None]
    return (sum(kept) / len(kept)) if kept else None


def _score100(values):
    """案例分是 0–1；子集分与总分统一报 0–100。"""
    value = _mean(values)
    return value * 100 if value is not None else None


def aggregate(results, config, run_meta=None):
    weights = config.get("subset_weights") or {}
    subsets = list(weights)
    report = {
        "run": run_meta or {},
        "cases_evaluated": len(results),
        "subsets": {},
        "check_rates": {},
        "severe_failures": [],
        "severe_failure_count": 0,
        "hard_pass": None,
        "total": None,
        "coverage": {},
        "strata": {},
    }

    for subset in subsets:
        rows = [result for result in results if result["subset"] == subset]
        scores = [result["score"] for result in rows]
        severe = [failure for result in rows for failure in result.get("severe") or []]
        report["subsets"][subset] = {
            "cases": len(rows),
            "scored_cases": sum(1 for score in scores if score is not None),
            "score": _score100(scores),
            "severe_failures": len(severe),
            "configured_weight": weights.get(subset),
            "case_scores": [{"case_id": result["case_id"],
                             "score": (result["score"] * 100
                                       if result["score"] is not None else None),
                             "severe": result.get("severe") or []}
                            for result in rows],
        }

    for name in CHECK_NAMES:
        values = []
        for result in results:
            for item in result.get("checks") or []:
                if item["name"] == name:
                    values.append(item.get("value"))
        if any(value is not None for value in values):
            report["check_rates"][name] = rate(values)

    for result in results:
        for failure in result.get("severe") or []:
            report["severe_failures"].append({
                "case_id": result["case_id"],
                "subset": result["subset"],
                "code": failure["code"],
                "message": failure["message"],
            })
    report["severe_failure_count"] = len(report["severe_failures"])

    scored_subsets = {name: data["score"] for name, data in report["subsets"].items()
                      if data["score"] is not None}
    if scored_subsets:
        weight_sum = sum(weights[name] for name in scored_subsets)
        total = sum(weights[name] * value for name, value in scored_subsets.items()) / weight_sum
        report["total"] = {
            "score": total,
            "used_weights": {name: weights[name] / weight_sum for name in scored_subsets},
            "excluded_subsets": sorted(set(subsets) - set(scored_subsets)),
            "renormalised": bool(set(subsets) - set(scored_subsets)),
        }
    else:
        report["total"] = {"score": None, "used_weights": {},
                           "excluded_subsets": subsets, "renormalised": False}

    report["hard_pass"] = {
        "passed": sum(1 for result in results if not result.get("severe")),
        "total": len(results),
        "rate": (sum(1 for result in results if not result.get("severe")) / len(results))
                if results else None,
    }

    report["coverage"] = {
        "by_subset": {name: report["subsets"][name]["cases"] for name in subsets},
        "by_split": _counts(results, "split"),
        "by_difficulty": _counts(results, "difficulty"),
        "by_draft_source": _counts(results, "draft_source"),
        "by_grade_level": _counts(results, "grade_level"),
        "by_action": _counts(results, "action"),
    }
    report["strata"] = {
        field: _strata(results, field)
        for field in ("split", "difficulty", "draft_source", "grade_level")
    }
    return report


def _counts(results, field):
    counts = {}
    for result in results:
        key = str(result.get(field))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _strata(results, field):
    buckets = {}
    for result in results:
        buckets.setdefault(str(result.get(field)), []).append(result)
    out = {}
    for key, rows in sorted(buckets.items()):
        scores = [row["score"] for row in rows]
        out[key] = {
            "cases": len(rows),
            "mean_case_score": _score100(scores),
            "severe_cases": sum(1 for row in rows if row.get("severe")),
            "note": "粗口径：案例分均值（0–100），不是子集分",
        }
    return out
