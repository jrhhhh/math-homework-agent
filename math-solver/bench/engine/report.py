# -*- coding: utf-8 -*-
"""Markdown 报告渲染。"""


def _fmt(value):
    if value is None:
        return "—"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _escape(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def _check_value(result, name):
    check = result["checks"].get(name)
    if check is None:
        return "—"
    return "✓" if check["value"] else "✗"


def render_markdown(report, meta):
    lines = []
    lines.append("# math-solver 基准报告")
    lines.append("")
    lines.append(f"- 预测文件：`{meta.get('predictions', '')}`")
    lines.append(f"- 运行组：`{meta.get('arm', '')}`")
    lines.append(f"- 模型：`{meta.get('model', '')}`")
    lines.append(f"- 运行 ID：`{meta.get('run_id', '')}`")
    lines.append("")
    lines.append("## 总分")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("| --- | ---: |")
    lines.append(f"| 总分 | **{_fmt(report['total'])}** |")
    answer_ci = report.get("answer_accuracy_ci")
    status_ci = report.get("status_accuracy_ci")
    answer_ci_text = f"（95% CI {_fmt(answer_ci[0])}–{_fmt(answer_ci[1])}）" if answer_ci else ""
    status_ci_text = f"（95% CI {_fmt(status_ci[0])}–{_fmt(status_ci[1])}）" if status_ci else ""
    lines.append(f"| 答案正确率 | {_fmt(report['answer_accuracy'])}%{answer_ci_text} |")
    lines.append(f"| 状态正确率 | {_fmt(report['status_accuracy'])}%{status_ci_text} |")
    lines.append(f"| 核验诚实率 | {_fmt(report['verification_honesty'])}% |")
    lines.append(f"| 边界路由分 | {_fmt(report['boundary_accuracy'])} |")
    lines.append(f"| 案例数 | {report['case_count']} |")
    lines.append(f"| 严重失败数 | {report['severe_count']} |")
    lines.append("")
    lines.append("## 子集")
    lines.append("")
    lines.append("| 子集 | 案例 | 权重 | 得分 |")
    lines.append("| --- | ---: | ---: | ---: |")
    for subset, score in report["subset_scores"].items():
        lines.append(f"| `{subset}` | {report['subset_counts'][subset]} | "
                     f"{report['subset_weights'].get(subset)} | {_fmt(score)} |")
    lines.append("")
    lines.append("## 数据划分")
    lines.append("")
    lines.append("| 划分 | 案例 | 得分 |")
    lines.append("| --- | ---: | ---: |")
    for split, score in report.get("split_scores", {}).items():
        lines.append(f"| `{split}` | {report['split_counts'][split]} | {_fmt(score)} |")
    lines.append("")
    lines.append("## 严重失败")
    lines.append("")
    if report["severe_failures"]:
        lines.append("| 案例 | 代码 |")
        lines.append("| --- | --- |")
        for item in report["severe_failures"]:
            lines.append(f"| `{item['case_id']}` | {', '.join(item['codes'])} |")
    else:
        lines.append("无。")
    lines.append("")
    lines.append("## 逐案例")
    lines.append("")
    lines.append("| 案例 | 子集 | 动作 | 得分 | 答案 | 状态 | 核验 | 转交/澄清 | 严重失败 |")
    lines.append("| --- | --- | --- | ---: | --- | --- | --- | --- | --- |")
    for result in report["cases"]:
        route_check = result["checks"].get("route_correct") or result["checks"].get("reply_covers")
        route = "—" if route_check is None else ("✓" if route_check["value"] else "✗")
        severe = ", ".join(result["severe"]) if result["severe"] else "—"
        lines.append(
            f"| `{result['case_id']}` | `{result['subset']}` | {result['expected_action']} | "
            f"{_fmt(result['score'] * 100)} | {_check_value(result, 'answer_correct')} | "
            f"{_check_value(result, 'status_correct')} | "
            f"{_check_value(result, 'verification_honest')} | {route} | {severe} |"
        )
    lines.append("")
    lines.append("## 读分口径")
    lines.append("")
    lines.append("- 自动层只做结构、答案形式、分支覆盖与措辞检查；**不判断推导是否优雅、方法是否最优**。")
    lines.append("- 答案检查面向本基准的固定案例：`value_set`、`interval_set`、`text_forms`、`piecewise`、`empty_set`。")
    lines.append("- 严重失败直接把案例记 0，不参与加权抵消。")
    lines.append("- 答案正确率与状态正确率单独列出，不应只用总分概括。")
    lines.append("- 括号内是 95% Wilson 区间；32 条样本下区间很宽，不要把点估计当作稳定准确率。")
    lines.append("")
    return "\n".join(lines)
