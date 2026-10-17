#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""schema_check.py — 案例与标准答案的结构、自洽与防泄漏校验（仅用标准库）。

用法：
  python3 engine/schema_check.py                 # 默认校验本目录（evals/）
  python3 engine/schema_check.py <evals 目录>
  python3 engine/schema_check.py <evals 目录> --jsonschema

它查四类东西：

1. **两份文件对齐**：`cases.jsonl` 与 `ground_truth.jsonl` 的 case_id 必须同集同序、
   不重不漏。少了答案行就是缺口，多了答案行就是孤儿。
2. **字段集**：两份文件各自的字段不许越界（输入字段放不进答案文件，反之亦然）。
3. **自洽**：**每条 evidence_anchor 必须逐字出现在该案例的草稿里**——这是数据自身的
   「证据必须有草稿依据」。`gold_correct_steps` 与 `gold_errors` 的锚点不许重叠。
4. **防泄漏**：同一 template_id 不得跨 split。

退出码：0 = 通过（可能有 warning）；1 = 有 error；2 = 输入非法（文件缺失 / JSONL 坏）。
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cases import CASES_FILE, CASE_FIELDS, DIM_KEYS, GROUND_TRUTH_FILE, GT_FIELDS, SPLITS, SUBSETS, read_jsonl  # noqa: E402
from cases import normalise, normalise_strict  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

CASE_ID_RE = r"^(MATH|EVID|DIM|BOUND|CPLX|TOOL)-[0-9]{2}$"
INPUT_FIELDS = {"prompt", "problem", "draft", "final_solution", "draft_source",
                "image_confirmed", "audit_draft"}
INPUT_REQUIRED = {"prompt", "problem", "draft", "final_solution", "draft_source"}
GT_REQUIRED = {"case_id", "gold_errors", "gold_correct_steps", "expected_behaviors",
               "forbidden_behaviors", "notes"}
ERROR_FIELDS = {"error_id", "kind", "propagates_to", "type", "severity", "location",
                "evidence_anchor", "evidence_note", "cause", "minimal_fix", "must_report"}
STEP_FIELDS = {"step_id", "location", "evidence_anchor", "note"}
DIM_FIELDS = {"label", "basis", "positive_expected", "unevaluable"}
KNOWN_METRICS = {
    "error_precision", "error_recall", "error_localization", "no_error_identification",
    "propagation_quality", "location_descriptor_correct", "fix_correctness",
    "explanation_correctness", "evidence_existence_rate", "evidence_support_rate",
    "minimal_fix_compliance", "no_full_solution_rewrite", "dimension_completeness",
    "dimension_label_match", "risk_form", "positive_signal", "utilization_handling",
    "dimension_evidence_grounded", "action_accuracy", "refuse_reason_accuracy",
    "refusal_wording_match", "over_refusal_avoidance", "no_boundary_violation",
    "clarify_quality", "multi_problem_handling", "evaluable_scope_respected",
    "cross_block_false_positive_avoidance", "mixed_content_reading", "json_parseable",
    "structure_valid", "audit_clean", "tool_log_fidelity", "exit_code_reported",
    "retry_policy_followed",
}
GRADES = {"小学", "初中", "高中", "大学"}
SOURCES = {"text_reconstruction", "image_description", "absent"}


class Issues:
    def __init__(self):
        self.errors, self.warnings = [], []

    def error(self, case_id, where, code, message):
        self.errors.append({"case_id": case_id, "where": where, "code": code, "message": message})

    def warn(self, case_id, where, code, message):
        self.warnings.append({"case_id": case_id, "where": where, "code": code, "message": message})


def check_file_fields(rows, allowed, required, filename, issues, id_key="case_id"):
    """查一份 JSONL 的字段集：缺必需字段、出现非本文件的字段。"""
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            issues.error("<第%d行>" % index, filename, "E_TYPE", "每行必须是 JSON 对象")
            continue
        cid = row.get(id_key, "<无 case_id>")
        for field in sorted(required):
            if field not in row:
                issues.error(cid, filename, "E_REQUIRED", "缺少必需字段 %s" % field)
        for field in sorted(set(row) - allowed):
            issues.error(cid, filename, "E_EXTRA_FIELD",
                         "字段 %s 不属于 %s（输入与标准答案要分开放）" % (field, filename))


def check_case(case, issues):
    """合并后的案例自洽检查。返回 case_id。"""
    if not isinstance(case, dict):
        issues.error("<非对象>", "merged", "E_TYPE", "案例必须是对象")
        return None
    cid = case.get("case_id", "<无 case_id>")

    import re as _re
    if not isinstance(cid, str) or not _re.match(CASE_ID_RE, cid):
        issues.error(cid, "merged", "E_PATTERN",
                     "case_id 必须形如 MATH-01 / EVID-02 / DIM-03 / BOUND-04 / CPLX-05 / TOOL-06")
    if case.get("subset") not in SUBSETS:
        issues.error(cid, "merged", "E_ENUM", "subset 取值非法：%r" % case.get("subset"))
    if case.get("split") not in SPLITS:
        issues.error(cid, "merged", "E_ENUM", "split 取值非法：%r" % case.get("split"))
    for field, allowed in (("difficulty", {"easy", "medium", "hard"}),
                           ("grade_level", GRADES),
                           ("expected_action", {"analyze", "clarify", "refuse"}),
                           ("severity", {"low", "medium", "high"}),
                           ("provenance", {"synthetic", "imported"})):
        if case.get(field) not in allowed:
            issues.error(cid, "merged", "E_ENUM", "%s 取值非法：%r" % (field, case.get(field)))
    if not isinstance(case.get("template_id"), str) or len(case.get("template_id", "")) < 3:
        issues.error(cid, "merged", "E_TYPE", "template_id 必须是不短于 3 的字符串")
    if not isinstance(case.get("notes"), str) or not case.get("notes", "").strip():
        issues.error(cid, "merged", "E_REQUIRED", "notes 必须非空（写清歧义与标注备注）")

    # -- input
    data = case.get("input")
    draft = None
    if not isinstance(data, dict):
        issues.error(cid, "merged", "E_TYPE", "input 必须是对象")
    else:
        for field in sorted(INPUT_REQUIRED):
            if field not in data:
                issues.error(cid, "merged", "E_REQUIRED", "input 缺少字段 %s" % field)
        for field in sorted(set(data) - INPUT_FIELDS):
            issues.error(cid, "merged", "E_EXTRA_FIELD", "input 里的非标准字段 %s" % field)
        if not isinstance(data.get("prompt"), str) or not data.get("prompt", "").strip():
            issues.error(cid, "merged", "E_REQUIRED", "input.prompt 必须非空")
        for field in ("problem", "draft", "final_solution"):
            if field in data and data[field] is not None and not isinstance(data[field], str):
                issues.error(cid, "merged", "E_TYPE", "input.%s 只能是字符串或 null" % field)
        if data.get("draft_source") not in SOURCES:
            issues.error(cid, "merged", "E_ENUM",
                         "input.draft_source 取值非法：%r" % data.get("draft_source"))
        has_draft = bool((data.get("draft") or "").strip())
        if has_draft and data.get("draft_source") == "absent":
            issues.error(cid, "merged", "E_DRAFT_SOURCE_CONFLICT", "有草稿内容却把 draft_source 标成 absent")
        if not has_draft and data.get("draft_source") != "absent":
            issues.error(cid, "merged", "E_DRAFT_SOURCE_CONFLICT",
                         "没有草稿内容时 draft_source 必须是 absent")
        if "image_confirmed" in data and not isinstance(data["image_confirmed"], bool):
            issues.error(cid, "merged", "E_TYPE", "input.image_confirmed 必须是布尔值")
        if data.get("draft_source") == "image_description" \
                and data.get("image_confirmed") is None:
            issues.error(cid, "merged", "E_REQUIRED",
                         "图片类草稿必须显式给出 input.image_confirmed（内容是否已核对）")
        draft = data.get("draft")
        audit_draft = data.get("audit_draft")
        if audit_draft is not None:
            if not isinstance(audit_draft, str) or not audit_draft.strip():
                issues.error(cid, "merged", "E_TYPE", "input.audit_draft 只能是 null 或非空字符串")
            elif normalise_strict(audit_draft) not in normalise_strict(draft):
                issues.error(cid, "merged", "E_AUDIT_DRAFT",
                             "input.audit_draft 必须是 input.draft 里的一段（整张纸分块后的那一块）")

    draft_norm = normalise(draft)
    draft_strict = normalise_strict(draft)

    def check_anchors(where, anchors):
        if not isinstance(anchors, list) or not anchors:
            issues.error(cid, "merged", "E_TYPE", "%s.evidence_anchor 必须是非空数组" % where)
            return
        for anchor in anchors:
            if not isinstance(anchor, str) or not anchor.strip():
                issues.error(cid, "merged", "E_TYPE", "%s.evidence_anchor 里有空项" % where)
                continue
            if not draft_strict:
                issues.error(cid, "merged", "E_ANCHOR_NO_DRAFT", "%s 给了锚点但没有草稿可核" % where)
            elif normalise_strict(anchor) not in draft_strict:
                issues.error(cid, "merged", "E_ANCHOR_NOT_IN_DRAFT",
                             "%s 的锚点 %r 没有逐字出现在 input.draft 里" % (where, anchor))

    # -- 动作与拒绝理由
    action = case.get("expected_action")
    reason = case.get("refuse_reason", None)
    if action == "refuse":
        if reason not in ("empty", "unreadable", "out_of_scope"):
            issues.error(cid, "merged", "E_REFUSE_REASON",
                         "expected_action=refuse 时必须给出合法 refuse_reason")
    elif reason is not None:
        issues.error(cid, "merged", "E_REFUSE_REASON",
                     "expected_action=%s 时 refuse_reason 必须为 null" % action)

    # -- gold_errors
    errors = case.get("gold_errors")
    ids_in_case = set()
    if not isinstance(errors, list):
        issues.error(cid, "merged", "E_TYPE", "gold_errors 必须是数组（草稿无错就写空数组）")
    else:
        if not draft_norm and errors:
            issues.error(cid, "merged", "E_SEVERE_S4", "没有草稿的案例不能有 gold_errors（禁止伪造草稿分析）")
        for index, item in enumerate(errors):
            tag = "gold_errors[%d]" % index
            if not isinstance(item, dict):
                issues.error(cid, "merged", "E_TYPE", "%s 必须是对象" % tag)
                continue
            for field in sorted(ERROR_FIELDS):
                if field not in item:
                    issues.error(cid, "merged", "E_REQUIRED", "%s 缺少字段 %s" % (tag, field))
            for field in sorted(set(item) - ERROR_FIELDS):
                issues.error(cid, "merged", "E_EXTRA_FIELD", "%s 里的非标准字段 %s" % (tag, field))
            if item.get("kind") not in ("root", "propagated", "independent"):
                issues.error(cid, "merged", "E_ENUM", "%s.kind 取值非法：%r" % (tag, item.get("kind")))
            if item.get("type") not in ("arithmetic", "transposition", "sign", "algebra",
                                        "factorization", "calculus", "limit", "matrix",
                                        "trigonometry", "geometry", "other"):
                issues.error(cid, "merged", "E_ENUM", "%s.type 取值非法：%r" % (tag, item.get("type")))
            if item.get("severity") not in ("major", "minor"):
                issues.error(cid, "merged", "E_ENUM", "%s.severity 取值非法" % tag)
            if not isinstance(item.get("must_report"), bool):
                issues.error(cid, "merged", "E_TYPE", "%s.must_report 必须是布尔值" % tag)
            for field in ("location", "evidence_note", "cause", "minimal_fix"):
                if not isinstance(item.get(field), str) or not item.get(field, "").strip():
                    issues.error(cid, "merged", "E_REQUIRED", "%s.%s 必须是非空字符串" % (tag, field))
            check_anchors(tag, item.get("evidence_anchor"))
            eid = item.get("error_id")
            if not isinstance(eid, str) or not eid.startswith(str(cid) + "-E"):
                issues.error(cid, "merged", "E_ERROR_ID_PREFIX",
                             "%s.error_id 必须以 %s-E 开头，实为 %r" % (tag, cid, eid))
            if isinstance(eid, str):
                if eid in ids_in_case:
                    issues.error(cid, "merged", "E_DUP_ID", "error_id 重复：%s" % eid)
                ids_in_case.add(eid)
            if not isinstance(item.get("propagates_to"), list):
                issues.error(cid, "merged", "E_TYPE", "%s.propagates_to 必须是数组" % tag)
            elif item.get("kind") != "root" and item["propagates_to"]:
                issues.error(cid, "merged", "E_PROPAGATION",
                             "%s.kind=%s 时 propagates_to 必须为空数组" % (tag, item.get("kind")))

        by_id = {i.get("error_id"): i for i in errors if isinstance(i, dict)}
        for index, item in enumerate(errors):
            if not isinstance(item, dict):
                continue
            for target in item.get("propagates_to") or []:
                if target not in by_id:
                    issues.error(cid, "merged", "E_PROPAGATION",
                                 "gold_errors[%d].propagates_to 指向不存在的 %r" % (index, target))
                elif by_id[target].get("kind") != "propagated":
                    issues.error(cid, "merged", "E_PROPAGATION",
                                 "propagates_to 只能指向 kind=propagated 的条目，%r 不是" % target)

    # -- gold_correct_steps
    steps = case.get("gold_correct_steps")
    if not isinstance(steps, list):
        issues.error(cid, "merged", "E_TYPE", "gold_correct_steps 必须是数组")
    else:
        for index, item in enumerate(steps):
            tag = "gold_correct_steps[%d]" % index
            if not isinstance(item, dict):
                issues.error(cid, "merged", "E_TYPE", "%s 必须是对象" % tag)
                continue
            for field in sorted(STEP_FIELDS):
                if field not in item:
                    issues.error(cid, "merged", "E_REQUIRED", "%s 缺少字段 %s" % (tag, field))
            for field in sorted(set(item) - STEP_FIELDS):
                issues.error(cid, "merged", "E_EXTRA_FIELD", "%s 里的非标准字段 %s" % (tag, field))
            check_anchors(tag, item.get("evidence_anchor"))
            for anchor in item.get("evidence_anchor") or []:
                for err in errors or []:
                    if isinstance(err, dict) and anchor in (err.get("evidence_anchor") or []):
                        issues.error(cid, "merged", "E_ANCHOR_CONFLICT",
                                     "锚点 %r 同时出现在 gold_errors 与 gold_correct_steps" % anchor)

    # -- gold_dimensions
    dims = case.get("gold_dimensions")
    if action == "analyze" and not isinstance(dims, dict):
        issues.error(cid, "merged", "E_REQUIRED", "expected_action=analyze 时必须给出 gold_dimensions")
    if isinstance(dims, dict):
        for key in DIM_KEYS:
            if key not in dims:
                issues.error(cid, "merged", "E_DIM_KEYS", "gold_dimensions 缺维度 %s" % key)
        for key in sorted(set(dims) - set(DIM_KEYS)):
            issues.error(cid, "merged", "E_DIM_KEYS", "gold_dimensions 里的非标准维度名 %s" % key)
        for key in DIM_KEYS:
            item = dims.get(key)
            if not isinstance(item, dict):
                continue
            for field in sorted(set(item) - DIM_FIELDS):
                issues.error(cid, "merged", "E_EXTRA_FIELD",
                             "gold_dimensions.%s 里的非标准字段 %s" % (key, field))
            if item.get("label") not in ("高", "中", "低", "不适用"):
                issues.error(cid, "merged", "E_DIM_LABEL",
                             "gold_dimensions.%s.label 取值非法：%r" % (key, item.get("label")))
            if item.get("label") == "不适用" and key != "draft_to_solution":
                issues.error(cid, "merged", "E_DIM_LABEL",
                             "只有 draft_to_solution 可以用「不适用」，%s 不行" % key)
            if not isinstance(item.get("basis"), str) or not item.get("basis", "").strip():
                issues.error(cid, "merged", "E_REQUIRED", "gold_dimensions.%s.basis 必须非空" % key)
            if "positive_expected" in item and not isinstance(item["positive_expected"], bool):
                issues.error(cid, "merged", "E_TYPE",
                             "gold_dimensions.%s.positive_expected 必须是布尔值" % key)
            if item.get("positive_expected") and key != "correction_pattern":
                issues.error(cid, "merged", "E_DIM_POSITIVE",
                             "positive_expected 只对 correction_pattern 有意义，%s 不该有" % key)
        util = dims.get("draft_to_solution")
        no_solution = not (case.get("input", {}).get("final_solution") or "").strip()
        if isinstance(util, dict) and no_solution and util.get("label") != "不适用":
            issues.warn(cid, "merged", "W_UTILIZATION_LABEL",
                        "未提供最终解答，draft_to_solution 通常应标「不适用」，实为 %r" % util.get("label"))
        if isinstance(util, dict) and not no_solution and util.get("label") == "不适用":
            issues.error(cid, "merged", "E_UTILIZATION_LABEL",
                         "已提供最终解答，draft_to_solution 不应标「不适用」")

    # -- 复杂案例必须写明可判定 / 不可判定范围
    if case.get("subset") == "E_complex_drafts":
        for field in ("evaluable_scope", "unevaluable_scope"):
            if not isinstance(case.get(field), list) or not case.get(field):
                issues.error(cid, "merged", "E_REQUIRED",
                             "复杂草稿案例必须写明 %s（可判定与不可判定范围）" % field)

    # -- 行为清单与指标名
    for field in ("expected_behaviors", "forbidden_behaviors"):
        value = case.get(field)
        if not isinstance(value, list) or not value or not all(isinstance(x, str) and x.strip() for x in value):
            issues.error(cid, "merged", "E_REQUIRED", "%s 必须是非空字符串数组" % field)
    for name in case.get("metrics") or []:
        if name not in KNOWN_METRICS:
            issues.error(cid, "merged", "E_UNKNOWN_METRIC", "未知指标名 %r" % name)
    for field in ("evaluable_scope", "unevaluable_scope"):
        value = case.get(field)
        if value is not None and (not isinstance(value, list)
                                  or not all(isinstance(x, str) for x in value)):
            issues.error(cid, "merged", "E_TYPE", "%s 必须是字符串数组" % field)
    return cid


def check_dataset(evals_dir, use_jsonschema=False):
    evals_dir = Path(evals_dir)
    issues = Issues()
    if not (evals_dir / CASES_FILE).is_file() or not (evals_dir / GROUND_TRUTH_FILE).is_file():
        return None, issues
    try:
        cases_rows = read_jsonl(evals_dir / CASES_FILE)
        truth_rows = read_jsonl(evals_dir / GROUND_TRUTH_FILE)
    except ValueError as exc:
        issues.error("<解析失败>", "jsonl", "E_PARSE", str(exc))
        return {}, issues

    check_file_fields(cases_rows, set(CASE_FIELDS), {"case_id", "subset", "split", "input",
                                                     "expected_action"},
                      CASES_FILE, issues)
    check_file_fields(truth_rows, set(GT_FIELDS), GT_REQUIRED, GROUND_TRUTH_FILE, issues)

    # 两份文件必须同集同序
    case_ids = [row.get("case_id") for row in cases_rows]
    truth_ids = [row.get("case_id") for row in truth_rows]
    for ids, filename in ((case_ids, CASES_FILE), (truth_ids, GROUND_TRUTH_FILE)):
        seen = set()
        for cid in ids:
            if cid in seen:
                issues.error(cid, filename, "E_DUP_ID", "case_id 重复")
            seen.add(cid)
    if set(case_ids) != set(truth_ids):
        missing = sorted(set(case_ids) - set(truth_ids))
        orphan = sorted(set(truth_ids) - set(case_ids))
        if missing:
            issues.error("<对齐>", GROUND_TRUTH_FILE, "E_GT_MISSING",
                         "这些案例没有标准答案行：%s" % "、".join(missing))
        if orphan:
            issues.error("<对齐>", CASES_FILE, "E_GT_ORPHAN",
                         "这些标准答案没有对应案例：%s" % "、".join(orphan))
    elif case_ids != truth_ids:
        issues.warn("<对齐>", "jsonl", "W_ORDER",
                    "两份文件的 case_id 集合相同但顺序不同；建议保持同序便于 diff")

    merged = []
    truth_by_id = {row.get("case_id"): row for row in truth_rows if isinstance(row, dict)}
    for row in cases_rows:
        if not isinstance(row, dict):
            continue
        case = dict(row)
        case.update({k: v for k, v in (truth_by_id.get(row.get("case_id")) or {}).items()
                     if k != "case_id"})
        merged.append(case)

    ids, templates = {}, {}
    for case in merged:
        cid = check_case(case, issues)
        if cid:
            if cid in ids:
                issues.error(cid, "jsonl", "E_DUP_ID", "case_id 与另一行重复")
            ids[cid] = True
            if case.get("template_id"):
                templates.setdefault(case["template_id"], set()).add(case.get("split"))
        if use_jsonschema:
            _jsonschema_cross_check(case, cid, issues)

    for template, splits in sorted(templates.items()):
        if len(splits) > 1:
            issues.error("<防泄漏>", "jsonl", "E_TEMPLATE_SPLIT_LEAK",
                         "template_id %s 同时出现在 %s——同一模板（含只换数字的近重复）必须落在同一 split"
                         % (template, "、".join(sorted(str(s) for s in splits))))
    return ids, issues


def _jsonschema_cross_check(case, cid, issues):
    """可选：用 jsonschema 交叉校验。缺依赖时静默跳过，不构成运行依赖。"""
    try:
        import jsonschema
    except Exception:
        return
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "case.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        clean = {k: v for k, v in case.items() if not k.startswith("_")}
        jsonschema.validate(clean, schema)
    except Exception as exc:
        issues.warn(cid, "merged", "W_JSONSCHEMA", "jsonschema 交叉校验告警：%s" % exc)


def main(argv):
    evals_dir = Path(argv[1]) if len(argv) > 1 and not argv[1].startswith("-") \
        else Path(__file__).resolve().parents[1]
    use_jsonschema = "--jsonschema" in argv
    ids, issues = check_dataset(evals_dir, use_jsonschema)
    if ids is None:
        print(json.dumps({"error": "cases.jsonl / ground_truth.jsonl not found",
                          "path": str(evals_dir)}, ensure_ascii=False, indent=2))
        return 2
    payload = {
        "evals_dir": str(evals_dir),
        "cases": len(ids),
        "errors": issues.errors,
        "warnings": issues.warnings,
        "passed": not issues.errors,
        "note": "本校验只查结构与自洽（含锚点是否逐字出现在草稿里），以及两份文件是否对齐。"
                "它不判数学，也不判断锚点是否真的支持那条错误结论。",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not issues.errors else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
