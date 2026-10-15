#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evaluate.py — 批量评测一个实验组，产出报告。仅用标准库。

  python3 evals/evaluate.py --predictions predictions/skill_gates.json \
      --review reviews/skill_gates.model_assisted.json \
      --splits development validation \
      --out reports/skill_gates.report.json --markdown reports/skill_gates.report.md

它不调用模型：只读取已保存的原始输出，重放技能的两道门，算分，出报告。
退出码：0 = 全部案例都有输出且无严重失败；1 = 跑通但有缺口（缺输出 / 有严重失败）；
2 = 输入非法（配置或预测文件不合规）。
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # evals/ 自己
sys.path.insert(0, str(ROOT / "engine"))

from cases import load_cases, load_predictions  # noqa: E402
import gate_replay  # noqa: E402
import metrics as metrics_mod  # noqa: E402
import scoring  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


class InputError(Exception):
    pass


def load_config(path):
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise InputError("配置文件不存在：%s" % path)
    except json.JSONDecodeError as exc:
        raise InputError("配置文件不是合法 JSON：%s" % exc)
    for field in ("subset_weights", "subset_metrics", "metric_layers", "counting_rule"):
        if field not in config:
            raise InputError("配置缺少字段 %s" % field)
    if abs(sum(config["subset_weights"].values()) - 1.0) > 1e-6:
        raise InputError("subset_weights 之和必须为 1（当前 %r）" % sum(config["subset_weights"].values()))
    return config


def check_prediction_file(payload, known_ids):
    if not isinstance(payload, dict):
        raise InputError("预测文件必须是 JSON 对象")
    for field in ("arm", "run_id", "producer", "model_note", "predictions"):
        if field not in payload:
            raise InputError("预测文件缺少字段 %s" % field)
    seen = set()
    for item in payload["predictions"]:
        if not isinstance(item, dict):
            raise InputError("predictions 的每一条必须是对象")
        for field in ("case_id", "response", "card", "tool_log"):
            if field not in item:
                raise InputError("预测条目缺少字段 %s（case_id=%r）" % (field, item.get("case_id")))
        if item["case_id"] not in known_ids:
            raise InputError("预测里出现数据集里没有的 case_id：%r" % item["case_id"])
        if item["case_id"] in seen:
            raise InputError("同一 case_id 出现多次：%r" % item["case_id"])
        seen.add(item["case_id"])
    return payload


def load_reviews(paths, known_metrics):
    """读入模型辅助 / 人工评审，返回 {(case_id, metric): 0/1} 与来源清单。"""
    table, sources = {}, []
    for path in paths or []:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise InputError("评审文件不存在：%s" % path)
        except json.JSONDecodeError as exc:
            raise InputError("评审文件不是合法 JSON：%s（%s）" % (path, exc))
        layer = payload.get("layer")
        if layer not in ("model_assisted", "human"):
            raise InputError("评审文件 %s 的 layer 必须是 model_assisted 或 human" % path)
        try:
            table.update(scoring.merge_external(payload.get("ratings"), layer, known_metrics))
        except ValueError as exc:
            raise InputError("%s：%s" % (path, exc))
        sources.append({"path": str(path), "layer": layer,
                        "reviewer": payload.get("reviewer"),
                        "model_note": payload.get("model_note")})
    return table, sources


def evaluate(cases, payload, config, external):
    arm = payload["arm"]
    arm_config = (config.get("experiments") or {}).get(arm)
    if not isinstance(arm_config, dict):
        raise InputError("配置的 experiments 里没有实验组 %r" % arm)
    _payload, predictions = load_predictions_from(payload)

    results, missing = [], []
    for case in cases:
        case_id = case["case_id"]
        prediction = predictions.get(case_id)
        if prediction is None:
            missing.append(case_id)
            prediction = {"case_id": case_id, "response": "", "card": None, "tool_log": []}
        values = metrics_mod.automatic_metrics(case, prediction, config)
        gate_values, gate_severe = gate_replay.gate_metrics(case, prediction, config, arm_config)
        for name, value in gate_values.items():
            values[name] = value
        for name in config["metric_layers"]:
            # external 的键是 (case_id, metric) 元组；不能拿指标名单独去查
            if (case_id, name) in external:
                values[name] = external[(case_id, name)]
            values.setdefault(name, None)
        severe = metrics_mod.severe_failures(case, prediction, config) + gate_severe
        results.append({"case": case, "arm": arm, "metrics": values, "severe": severe,
                        "prediction_present": prediction.get("case_id") in predictions})
    return results, missing


def load_predictions_from(payload):
    return payload, {item["case_id"]: item for item in payload["predictions"]}


def render_markdown(report, payload, review_sources, missing):
    lines = []
    lines.append("# Draft Coach Benchmark 评分报告\n")
    lines.append("> 本报告由 `evals/evaluate.py` 生成，只重放已保存输出，不调用模型。\n")
    lines.append("| 项目 | 值 |")
    lines.append("| --- | --- |")
    lines.append("| 实验组 | `%s` |" % report["arm"])
    lines.append("| run_id | `%s` |" % payload["run_id"])
    lines.append("| 产出方 | %s |" % payload["producer"])
    lines.append("| 模型说明 | %s |" % payload["model_note"])
    lines.append("| 评测案例数 | %d |" % report["cases_evaluated"])
    lines.append("| 缺输出案例 | %s |" % (", ".join(missing) if missing else "无"))
    lines.append("| 严重失败 | %d 条 |" % report["severe_failure_count"])
    lines.append("")
    if not report.get("is_model_run", True):
        lines.append("> **警告：这不是模型运行结果。** 该预测文件的产出方标记为 %r，"
                     "只能用来验证评测流程本身。\n" % payload["producer"])
    lines.append("## 子集得分\n")
    lines.append("| 子集 | 案例 | 配置权重 | 得分 | 自动层 | 模型辅助层 | 人工层 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for subset, data in report["subsets"].items():
        def show(layer):
            stats = data["by_layer"][layer]
            if stats["rate"] is None:
                return "未运行"
            return "%s/%d" % (stats["numerator"], stats["denominator"])
        lines.append("| `%s` | %d | %.0f%% | %s | %s | %s | %s |" % (
            subset, data["cases"], 100 * (data["configured_weight"] or 0),
            "未运行" if data["score"] is None else "%.1f" % data["score"],
            show("automatic"), show("model_assisted"), show("human")))
    total = report["total"]
    lines.append("")
    lines.append("**总分：%s**" % ("未运行" if total["score"] is None else "%.1f / 100" % total["score"]))
    if total.get("renormalised"):
        lines.append("")
        lines.append("> 注意：子集 %s 没有算出分，其权重已**重新归一化**到其余子集，"
                     "因此该总分与完整权重口径不可直接比较。"
                     % "、".join(total["excluded_subsets"]))
    lines.append("")
    lines.append("## 覆盖度（自动层；分子/分母薄的地方必须看得见）\n")
    lines.append("| 子集 | 案例范围 | 自动指标已用/可用 | 最小自动分母 | 实际参与计分的层 | 覆盖 |")
    lines.append("| --- | --- | ---: | ---: | --- | --- |")
    for subset, data in report["subsets"].items():
        cov = data["scoring_detail"]["coverage"]
        lines.append("| `%s` | %s | %d/%d | %d | %s | %s |" % (
            subset, data["cases_scope"], cov["automatic_metrics_used"],
            cov["automatic_metrics_available"], cov["min_automatic_denominator"],
            "、".join(cov["layers_loaded"]) or "无",
            "**偏薄**" if cov["thin"] else "完整"))
    lines.append("")
    lines.append("> 自动层覆盖偏薄时分数仍可能是 100 分，必须连着分子分母一起读。最典型的情形："
                 "「什么错都不报」的空答案在「证据忠实度」上没有证据可判不忠实，于是拿到满分"
                 "——它真正的失分在「数学错误定位」的 Recall 上。")
    lines.append(">")
    lines.append("> 模型辅助层与人工层未加载时记为「未运行」，**不是 0 分**，也不参与子集分；"
                 "这也是「实际参与计分的层」一列存在的原因。\n")
    lines.append("## 指标明细（分子/分母，不允许只给比率）\n")
    for subset, data in report["subsets"].items():
        lines.append("### `%s`\n" % subset)
        lines.append("| 指标 | 层 | 分子/分母 | 比率 | 95% Wilson |")
        lines.append("| --- | --- | ---: | ---: | --- |")
        for name, stats in data["metric_detail"].items():
            if stats["rate"] is None:
                lines.append("| `%s` | %s | — | 未运行 | — |" % (name, stats["layer"]))
                continue
            if stats.get("ci"):
                ci = "[%.3f, %.3f]" % (stats["ci"]["low"], stats["ci"]["high"])
            else:
                ci = "—（%s）" % (stats.get("ci_note") or "不适用")
            lines.append("| `%s` | %s | %s/%d | %.3f | %s |" % (
                name, stats["layer"], stats["numerator"], stats["denominator"],
                stats["rate"], ci))
        lines.append("")
    lines.append("## 严重失败（不参与加权，不被高分抵消）\n")
    if not report["severe_failures"]:
        lines.append("本次运行未观察到严重失败。**有限样本中没有观察到，不代表真实使用中绝不会失败。**\n")
    else:
        lines.append("| 案例 | 编号 | 说明 |")
        lines.append("| --- | --- | --- |")
        for item in report["severe_failures"]:
            lines.append("| %s | %s | %s |" % (item["case_id"], item["code"], item["message"]))
        lines.append("")
    lines.append("## 分层结果（粗口径）\n")
    for field, buckets in report["strata"].items():
        lines.append("### 按 `%s`\n" % field)
        lines.append("| 取值 | 案例 | 严重失败 | 非空指标通过率 |")
        lines.append("| --- | ---: | ---: | --- |")
        for key, stats in buckets.items():
            share = "未运行" if stats["rate"] is None else "%d/%d" % (stats["numerator"], stats["denominator"])
            lines.append("| %s | %d | %d | %s |" % (key, stats["cases"], stats["severe"], share))
        lines.append("")
    lines.append("## 评审来源\n")
    if not review_sources:
        lines.append("本次运行没有加载模型辅助或人工评审文件：这两层在报告里标为「未运行」，"
                     "**不是 0 分**，也没有被算进子集分。\n")
    else:
        for source in review_sources:
            lines.append("- `%s`（%s，评审：%s）" % (source["path"], source["layer"],
                                                     source.get("reviewer") or "未署名"))
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="批量评测一个实验组的已保存输出")
    parser.add_argument("--dataset", default=str(ROOT),
                        help="装 cases.jsonl 与 ground_truth.jsonl 的目录")
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--review", action="append", default=[],
                        help="模型辅助 / 人工评审文件，可重复")
    parser.add_argument("--splits", nargs="+", default=["development", "validation", "test"])
    parser.add_argument("--out", default=None, help="把 JSON 报告写到这个路径")
    parser.add_argument("--markdown", default=None, help="把 Markdown 报告写到这个路径")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        cases = load_cases(args.dataset, tuple(args.splits))
        if not cases:
            raise InputError("数据集里没有任何案例（splits=%s）" % ",".join(args.splits))
        payload = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
        check_prediction_file(payload, {c["case_id"] for c in cases})
        external, sources = load_reviews(args.review, set(config["metric_layers"]))
        results, missing = evaluate(cases, payload, config, external)
    except InputError as exc:
        print(json.dumps({"error": "invalid input", "detail": str(exc)},
                         ensure_ascii=False, indent=2))
        return 2
    except FileNotFoundError as exc:
        print(json.dumps({"error": "invalid input", "detail": str(exc)},
                         ensure_ascii=False, indent=2))
        return 2

    report = scoring.aggregate(results, config)
    report["arm"] = payload["arm"]
    report["run_id"] = payload["run_id"]
    report["producer"] = payload["producer"]
    report["is_model_run"] = not str(payload["producer"]).startswith("fixture")
    report["missing_predictions"] = missing
    report["review_sources"] = sources
    report["config_version"] = config.get("version")
    report["config_path"] = str(args.config)
    report["limitations"] = [
        "本报告只重放已保存输出与门脚本，不调用模型、不重新作答。",
        "模型辅助与人工两层未加载时记为「未运行」，不是 0 分。",
        "两道门不验数学：结构/措辞通过不代表「这处算错了」判得对。",
        "自动指标里的锚点匹配只能证明引用的是草稿那处，不能证明那处真的错。",
    ]

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown:
        Path(args.markdown).parent.mkdir(parents=True, exist_ok=True)
        Path(args.markdown).write_text(render_markdown(report, payload, sources, missing),
                                       encoding="utf-8")
    print(json.dumps({
        "arm": report["arm"], "producer": report["producer"], "is_model_run": report["is_model_run"],
        "cases_evaluated": report["cases_evaluated"], "missing_predictions": missing,
        "total": report["total"]["score"], "renormalised": report["total"].get("renormalised"),
        "subset_scores": {k: v["score"] for k, v in report["subsets"].items()},
        "severe_failure_count": report["severe_failure_count"],
    }, ensure_ascii=False, indent=2))
    if missing or report["severe_failure_count"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
