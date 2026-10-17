# -*- coding: utf-8 -*-
"""把 aggregate() 的结果渲染成 Markdown。"""

from datetime import datetime


def _fmt(value, digits=1):
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, float):
        return ("%." + str(digits) + "f") % value
    return str(value)


def render_markdown(report, benchmark_version="1.0.0"):
    run = report.get("run") or {}
    lines = []
    lines.append("# Draft Coach 版面习惯基准报告")
    lines.append("")
    lines.append("- 基准版本：`%s`" % benchmark_version)
    lines.append("- 生成时间：%s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("- 实验组：`%s`" % run.get("arm", "未注明"))
    lines.append("- 模型 / 产出方：`%s`" % run.get("model", "未注明"))
    lines.append("- run_id：`%s`" % run.get("run_id", "未注明"))
    lines.append("")

    total = report.get("total") or {}
    hard = report.get("hard_pass") or {}
    lines.append("## 总览")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("| --- | ---: |")
    lines.append("| 加权总分（0–100） | **%s** |" % _fmt(total.get("score")))
    lines.append("| 硬门槛通过（无严重失败） | %s / %s（%s） |" % (
        hard.get("passed", 0), hard.get("total", 0),
        _fmt((hard.get("rate") or 0) * 100 if hard.get("rate") is not None else None)))
    lines.append("| 严重失败 | %s |" % report.get("severe_failure_count", 0))
    lines.append("| 评估案例数 | %s |" % report.get("cases_evaluated", 0))
    lines.append("")
    if total.get("renormalised"):
        lines.append("> 有子集没有可评案例，权重已重新归一化：排除 %s。"
                     % "、".join(total.get("excluded_subsets") or []))
        lines.append("")

    lines.append("## 子集分")
    lines.append("")
    lines.append("| 子集 | 权重 | 案例 | 有分案例 | 子集分 | 严重失败 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for name, data in report.get("subsets", {}).items():
        lines.append("| %s | %s | %s | %s | %s | %s |" % (
            name, data.get("configured_weight"), data.get("cases"),
            data.get("scored_cases"), _fmt(data.get("score")),
            data.get("severe_failures")))
    lines.append("")

    lines.append("## 检查项通过率")
    lines.append("")
    lines.append("| 检查 | 通过率 | 分子 / 分母 | 说明 |")
    lines.append("| --- | ---: | ---: | --- |")
    for name, data in sorted(report.get("check_rates", {}).items(),
                             key=lambda item: (item[1].get("rate") or 0, item[0])):
        rate_value = data.get("rate")
        lines.append("| `%s` | %s%% | %s / %s | %s |" % (
            name, _fmt(rate_value * 100 if rate_value is not None else None),
            _fmt(data.get("numerator"), 2), data.get("denominator"),
            data.get("ci_note") or ""))
    lines.append("")

    lines.append("## 严重失败")
    lines.append("")
    failures = report.get("severe_failures") or []
    if not failures:
        lines.append("无。")
    else:
        lines.append("| 案例 | 子集 | 代码 | 说明 |")
        lines.append("| --- | --- | --- | --- |")
        for failure in failures:
            lines.append("| %s | %s | `%s` | %s |" % (
                failure.get("case_id"), failure.get("subset"),
                failure.get("code"), failure.get("message")))
    lines.append("")

    lines.append("## 案例明细（非满分或有严重失败）")
    lines.append("")
    rows = []
    for subset in report.get("subsets", {}).values():
        for row in subset.get("case_scores") or []:
            score = row.get("score")
            if row.get("severe") or (score is not None and score < 0.999):
                rows.append((row, subset))
    if not rows:
        lines.append("所有案例满分且无严重失败。")
    else:
        lines.append("| 案例 | 分数 | 严重失败 |")
        lines.append("| --- | ---: | --- |")
        for row, _subset in rows:
            codes = "、".join(sorted({item["code"] for item in row.get("severe") or []}))
            lines.append("| %s | %s | %s |" % (
                row.get("case_id"), _fmt(row.get("score")), codes or "—"))
    lines.append("")

    lines.append("## 覆盖度")
    lines.append("")
    coverage = report.get("coverage") or {}
    for field in ("by_subset", "by_split", "by_difficulty", "by_draft_source",
                  "by_grade_level", "by_action"):
        values = coverage.get(field) or {}
        lines.append("- %s：%s" % (field, "、".join(
            "%s=%s" % (key, value) for key, value in values.items()) or "—"))
    lines.append("")

    lines.append("## 分层粗读数")
    lines.append("")
    for field, buckets in (report.get("strata") or {}).items():
        lines.append("### %s" % field)
        lines.append("")
        lines.append("| 层 | 案例 | 案例分均值 | 严重失败案例 |")
        lines.append("| --- | ---: | ---: | ---: |")
        for key, data in buckets.items():
            lines.append("| %s | %s | %s | %s |" % (
                key, data.get("cases"), _fmt(data.get("mean_case_score")),
                data.get("severe_cases")))
        lines.append("")

    lines.append("## 这套分不代表什么")
    lines.append("")
    lines.append("- 两道门都不验数学；本技能也不判断计算对错。"
                 "结构/措辞通过不等于版面观察属实。")
    lines.append("- 证据锚点只证明「卡片引用了草稿里出现过的位置或痕迹」，"
                 "不证明那处观察一定正确。")
    lines.append("- 24 条案例是合成的文字还原/文字描述，不是随机抽样的真实学生草稿；"
                 "图片案例没有真实图片，只有版面文字描述。")
    lines.append("- 自动层不评价「这条习惯是否真的适合这个学生」；"
                 "该问题只走人工层（`engine/human_review.py`）。")
    lines.append("- 权重未经试运行校准；覆盖薄的子集即使得高分也不能外推。")
    lines.append("")
    return "\n".join(lines)
