# -*- coding: utf-8 -*-
"""聚合评分。"""

import math


def _mean(values):
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _counts(results, check_name):
    total = len(results)
    successes = sum(1 for result in results
                    if result["checks"].get(check_name)
                    and result["checks"][check_name]["value"])
    return successes, total


def _wilson(successes, total, z=1.96):
    """95% Wilson 区间，返回百分数 [lo, hi]；小样本时不要只看点估计。"""
    if total == 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, center - half) * 100, 2),
            round(min(1.0, center + half) * 100, 2)]


def _rate(results, check_name):
    """分母是全部传入的案例；缺该检查（如缺输出）记 0，不缩小分母。"""
    successes, total = _counts(results, check_name)
    return round(successes / total * 100, 2) if total else None


def aggregate(results, config):
    subset_weights = config["subset_weights"]
    by_subset = {}
    for result in results:
        by_subset.setdefault(result["subset"], []).append(result)

    subset_scores = {}
    subset_counts = {}
    for subset, rows in by_subset.items():
        subset_scores[subset] = round(_mean(row["score"] for row in rows) * 100, 2)
        subset_counts[subset] = len(rows)

    available = [subset for subset in subset_scores if subset in subset_weights]
    total_weight = sum(subset_weights[subset] for subset in available)
    total = (round(sum(subset_scores[subset] * subset_weights[subset]
                       for subset in available) / total_weight, 2)
             if total_weight else 0.0)

    by_split = {}
    for result in results:
        by_split.setdefault(result.get("split") or "unspecified", []).append(result)
    split_scores = {
        split: round(_mean(row["score"] for row in rows) * 100, 2)
        for split, rows in by_split.items()
    }
    split_counts = {split: len(rows) for split, rows in by_split.items()}

    solve_results = [r for r in results if r["expected_action"] == "solve"]
    boundary_results = [r for r in results if r["subset"] == "boundary_routing"]

    severe = [
        {"case_id": r["case_id"], "codes": r["severe"]}
        for r in results if r["severe"]
    ]

    return {
        "case_count": len(results),
        "subset_counts": subset_counts,
        "subset_scores": subset_scores,
        "subset_weights": {s: subset_weights.get(s) for s in subset_scores},
        "split_scores": split_scores,
        "split_counts": split_counts,
        "total": total,
        "answer_accuracy": _rate(solve_results, "answer_correct"),
        "answer_accuracy_ci": _wilson(*_counts(solve_results, "answer_correct")),
        "status_accuracy": _rate(solve_results, "status_correct"),
        "status_accuracy_ci": _wilson(*_counts(solve_results, "status_correct")),
        "verification_honesty": _rate(solve_results, "verification_honest"),
        "boundary_accuracy": (round(_mean(r["score"] for r in boundary_results) * 100, 2)
                              if boundary_results else None),
        "severe_failures": severe,
        "severe_count": len(severe),
        "cases": results,
    }
