# -*- coding: utf-8 -*-
"""打分：把三层指标合成子集分与总分。仅用标准库。

三条硬规矩：

1. **None 不等于 0 分，也不等于满分。** 没算出来的指标（未运行的层、不适用的案例）
   直接从分母里剔除，并在报告里标出该指标「未运行 / 不适用」。剔除后权重会重新
   归一化——报告必须打印重新归一化这件事，不能悄悄做。
2. **严重失败不参与加权。** 它单独统计，不被任何高分抵消。
3. **分层不混算。** 自动、模型辅助、人工三层分别给出比率，再合成子集分。
"""

import math

from cases import SUBSETS

METRIC_LAYER_ORDER = ("automatic", "model_assisted", "human")


def wilson(successes, total, z=1.96):
    """Wilson 区间。样本量很小时区间会很宽——报告里要照实呈现。"""
    if not total:
        return None
    phat = successes / total
    denominator = 1 + z * z / total
    centre = (phat + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(phat * (1 - phat) / total + z * z / (4 * total * total)) / denominator
    return {"low": max(0.0, centre - margin), "high": min(1.0, centre + margin)}


def rate(values, z=1.96):
    """一串 0/1/None → 分子、分母、比率与区间。None 不进分母。

    值不一定是 0/1：像 `tool_log_fidelity`、`evidence_existence_rate` 这类案例级
    结果是**分数**（一个案例里 3 条证据只对了 2 条就是 2/3）。所以这里求平均，
    不能把非零值一律当成 1——那会把 0.5 抬成满分。

    Wilson 区间只在全是 0/1 时才给；有分数值时它是无意义的，如实置空。
    """
    kept = [v for v in values if v is not None]
    if not kept:
        return {"numerator": 0, "denominator": 0, "rate": None, "ci": None,
                "status": "未运行或不适用"}
    total = sum(kept)
    binary = all(v in (0, 1) for v in kept)
    return {"numerator": _tidy(total), "denominator": len(kept),
            "rate": total / len(kept),
            "ci": wilson(int(total), len(kept), z) if binary else None,
            "ci_note": None if binary else "含分数值，不适用二项区间",
            "status": "ok"}


def _tidy(value):
    """整数就返回整数，否则保留两位，便于报告里读。"""
    if isinstance(value, float) and abs(value - round(value)) < 1e-9:
        return int(round(value))
    return round(value, 2) if isinstance(value, float) else value


def merge_external(ratings, layer, known_metrics):
    """把外部评审（模型辅助 / 人工）的评分并成 {(case_id, metric): 0/1}。

    严格校验布尔值：0/1、"true" 这类都拒收，避免把半个评分悄悄当成评分。
    值为 null 表示「还没评」，跳过——它与 false 是两回事，不能混。
    """
    table = {}
    for row in ratings or []:
        case_id = row.get("case_id")
        for name, value in (row.get("metrics") or {}).items():
            if name not in known_metrics:
                raise ValueError("评审里出现未知指标名：%r" % name)
            if value is None:
                continue
            if not isinstance(value, bool):
                raise ValueError("评审的 %s/%s 必须是布尔值或 null，实为 %r" % (case_id, name, value))
            table[(case_id, name)] = int(value)
    return table


def subset_score(metric_rates, metrics, weights):
    """子集分 = 100 × Σ(w×rate)/Σ(w)，只对算得出来的指标求和。"""
    usable = [(name, metric_rates[name]["rate"]) for name in metrics
              if metric_rates.get(name, {}).get("rate") is not None]
    if not usable:
        return None, {"used": [], "skipped": list(metrics)}
    used_weights = {name: weights.get(name, 1.0) for name, _ in usable}
    total_weight = sum(used_weights.values())
    score = 100 * sum(used_weights[name] * value for name, value in usable) / total_weight
    skipped = [name for name in metrics if name not in {u[0] for u in usable}]
    return score, {"used": [name for name, _ in usable], "skipped": skipped,
                   "weights": used_weights}


def aggregate(case_results, config):
    """case_results: [{"case": …, "arm": …, "metrics": {…}, "severe": [...]}]

    返回完整报告数据：子集分、总分、分层、指标明细、严重失败。
    """
    subset_metrics = config["subset_metrics"]
    subset_weights = config["subset_weights"]
    metric_layers = config["metric_layers"]
    within = config.get("metric_weights_within_subset") or {}
    z = (config.get("proportion_ci") or {}).get("z", 1.96)

    known = set(metric_layers)
    per_subset_cases = {name: [] for name in SUBSETS}
    for result in case_results:
        subset = result["case"].get("subset")
        per_subset_cases.setdefault(subset, []).append(result)

    cross_cutting = set(config.get("cross_cutting_subsets") or [])
    ordered = [name for name in SUBSETS if name in subset_metrics]
    report = {"subsets": {}, "severe_failures": [], "cases": {}}
    for subset in ordered:
        # 跨子集指标（例如「输出与工具合规」）在所有案例上统计：卡片是否合规是
        # 产出的属性，与案例属于哪个子集无关。分母仍然只含该指标算得出来的案例。
        results = case_results if subset in cross_cutting else (per_subset_cases.get(subset) or [])
        metrics = subset_metrics[subset]
        metric_rates = {}
        for name in metrics:
            values = [r["metrics"].get(name) for r in results]
            metric_rates[name] = rate(values, z)
            metric_rates[name]["layer"] = metric_layers.get(name)
            metric_rates[name]["weight"] = within.get(name, 1.0)
        score, detail = subset_score(metric_rates, metrics, within)
        # 覆盖度只看**自动层**：模型辅助 / 人工层没加载是另一回事（by_layer 与
        # review_sources 里已经写明「未运行」），把它算进 thin 只会让告警变成噪音。
        # 自动指标算不出来才是真缺口——例如「什么错都不报」的空答案在「证据忠实度」
        # 上没有证据可判不忠实，分母塌成 0，这个子集分就只剩一项指标在撑。
        used = detail["used"]
        auto_metrics = [name for name in metrics if metric_layers.get(name) == "automatic"]
        auto_used = [name for name in auto_metrics if metric_rates[name]["rate"] is not None]
        auto_denominators = [metric_rates[name]["denominator"] for name in auto_used]
        min_auto = min(auto_denominators) if auto_denominators else 0
        # thin 只标「有自动指标压根算不出来」。像 no_error_identification 只在无错案例上
        # 有分母、propagation_quality 只在有传播的案例上有分母，这些是设计如此，
        # 拿「最小分母 < 案例数」当告警会让它几乎恒真，反而掩盖真正的缺口。
        thin = bool(auto_metrics) and len(auto_used) < len(auto_metrics)
        detail["coverage"] = {
            "cases": len(results),
            "automatic_metrics_used": len(auto_used),
            "automatic_metrics_available": len(auto_metrics),
            "min_automatic_denominator": min_auto,
            "unavailable_automatic_metrics": [n for n in auto_metrics if n not in auto_used],
            "layers_loaded": sorted({metric_layers.get(name) for name in used}),
            "thin": thin,
            "note": ("自动层有算不出来的指标：%s。这些指标不进分母，读的时候要连着"
                     "分子分母一起看。" % "、".join(n for n in auto_metrics if n not in auto_used))
                    if thin else "自动层覆盖完整。",
        }
        by_layer = {}
        for layer in METRIC_LAYER_ORDER:
            names = [n for n in metrics if metric_layers.get(n) == layer]
            values = [r["metrics"].get(n) for r in results for n in names]
            by_layer[layer] = rate(values, z)
            by_layer[layer]["metrics"] = names
        report["subsets"][subset] = {
            "cases": len(results),
            "cases_scope": "全部案例（跨子集指标）" if subset in cross_cutting else "本子集案例",
            "score": score,
            "metric_detail": metric_rates,
            "by_layer": by_layer,
            "scoring_detail": detail,
            "configured_weight": subset_weights.get(subset),
        }

    # 总分：只对算得出的子集加权，并如实报告重新归一化
    scored = {name: data["score"] for name, data in report["subsets"].items()
              if data["score"] is not None}
    unscored = sorted(set(subset_metrics) - set(scored))
    if scored:
        weight_sum = sum(subset_weights[name] for name in scored)
        total = sum(subset_weights[name] * value for name, value in scored.items()) / weight_sum
        report["total"] = {
            "score": total,
            "renormalised": bool(unscored),
            "used_weights": {name: subset_weights[name] / weight_sum for name in scored},
            "excluded_subsets": unscored,
            "note": "被剔除的子集权重已重新归一化；这会让总分与完整权重口径不可直接比较。"
                    if unscored else "六个子集全部参与，未做重新归一化。",
        }
    else:
        report["total"] = {"score": None, "excluded_subsets": unscored,
                           "note": "没有任何子集算得出分——检查预测文件与评审文件是否齐备。"}

    # 严重失败：逐条列出，不参与加权
    for result in case_results:
        for code, message in result.get("severe") or []:
            report["severe_failures"].append({
                "case_id": result["case"].get("case_id"), "arm": result["arm"],
                "code": code, "message": message,
            })
    report["severe_failure_count"] = len(report["severe_failures"])
    report["cases_evaluated"] = len(case_results)

    report["strata"] = _strata(case_results, config, z)
    return report


def _strata(case_results, config, z):
    """按难度、细分类、草稿来源分层。粗口径：该层所有非空指标的通过率。"""
    strata = {}
    for field in ("difficulty", "category", "draft_source"):
        buckets = {}
        for result in case_results:
            if field == "draft_source":
                key = result["case"].get("input", {}).get("draft_source")
            else:
                key = result["case"].get(field)
            buckets.setdefault(key, []).append(result)
        strata[field] = {}
        for key, results in sorted(buckets.items(), key=lambda item: str(item[0])):
            values = [v for r in results for v in r["metrics"].values() if v is not None]
            stats = rate(values, z)
            stats["cases"] = len(results)
            stats["severe"] = sum(1 for r in results if r.get("severe"))
            stats["note"] = "粗口径：该层全部非空指标的通过率，不是子集分"
            strata[field][str(key)] = stats
    return strata
