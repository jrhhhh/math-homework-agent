# -*- coding: utf-8 -*-
"""cases.py — 评测案例与标准答案的加载。仅用标准库。

数据分成两个文件，按 `case_id` 合并：

- `cases.jsonl`：输入与预期动作（题目、草稿、最终解答、该走 analyze / clarify / refuse）
- `ground_truth.jsonl`：标准答案与不允许行为（错误清单、正确步骤、六维标签、行为清单）

拆开的好处是**输入与答案可以分别给不同的人看**：写案例的人拿 cases.jsonl 就能造输入，
标注的人拿 ground_truth.jsonl 独立填答案，不必看到彼此的中间结果。
"""

import json
from pathlib import Path

SUBSETS = (
    "A_math_error_localization",
    "B_evidence_fidelity",
    "C_dimension_analysis",
    "D_boundary_refusal",
    "E_complex_drafts",
    "F_output_tool_compliance",
)
SPLITS = ("development", "validation", "test")
DIM_KEYS = ("organization", "skipping", "correction_pattern",
            "trial_and_error", "graphic_use", "draft_to_solution")

# cases.jsonl 允许的字段（输入侧）
CASE_FIELDS = (
    "case_id", "template_id", "subset", "split", "category", "difficulty",
    "grade_level", "input", "expected_action", "refuse_reason", "severity",
    "provenance", "metrics",
)
# ground_truth.jsonl 允许的字段（答案侧）
GT_FIELDS = (
    "case_id", "gold_errors", "gold_correct_steps", "gold_dimensions",
    "expected_behaviors", "forbidden_behaviors", "evaluable_scope",
    "unevaluable_scope", "notes",
)

CASES_FILE = "cases.jsonl"
GROUND_TRUTH_FILE = "ground_truth.jsonl"


def read_jsonl(path):
    """读一个 JSONL 文件，返回对象列表。空行跳过。"""
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError("%s 第 %d 行不是合法 JSON：%s" % (path, number, exc))
    return rows


def load_raw(evals_dir):
    """分别读出两份原始行，返回 (cases_rows, ground_truth_rows)。"""
    evals_dir = Path(evals_dir)
    cases = read_jsonl(evals_dir / CASES_FILE)
    truth = read_jsonl(evals_dir / GROUND_TRUTH_FILE)
    return cases, truth


def load_cases(evals_dir, splits=SPLITS):
    """合并两份 JSONL，按 split 过滤，返回评测器内部用的案例 dict 列表。

    合并后的形状与拆开之前**完全一致**，这样 metrics / scoring / schema_check
    都不必知道数据是怎么落盘的。来源信息挂在 `_source`（下划线开头，不参与校验）。
    """
    cases_rows, truth_rows = load_raw(evals_dir)
    truth_by_id = {}
    for row in truth_rows:
        case_id = row.get("case_id")
        if case_id in truth_by_id:
            raise ValueError("ground_truth.jsonl 里 case_id 重复：%r" % case_id)
        truth_by_id[case_id] = row

    merged = []
    for row in cases_rows:
        case_id = row.get("case_id")
        case = dict(row)
        case.update({k: v for k, v in (truth_by_id.get(case_id) or {}).items() if k != "case_id"})
        if case.get("split") not in splits:
            continue
        case["_source"] = {"cases_file": str(Path(evals_dir) / CASES_FILE),
                           "ground_truth_file": str(Path(evals_dir) / GROUND_TRUTH_FILE)}
        merged.append(case)
    return merged


def load_predictions(path):
    """读取一个实验组的原始输出，返回 (整份 payload, {case_id: prediction})。"""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload, {item["case_id"]: item for item in payload.get("predictions", [])}


def draft_tokens(text):
    """草稿里的地标记号：数字与 ASCII 标识符。

    与 `draft-coach/scripts/_rules.py` 的 draft_tokens 保持同一口径，
    这样「证据是否出自草稿」在本评测与技能自己的 audit 里含义一致。
    """
    import re
    tokens = re.findall(r"\d+(?:\.\d+)?", text or "") + re.findall(r"[A-Za-z][A-Za-z0-9_]{0,7}", text or "")
    seen, out = set(), []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def normalise(text):
    """去掉空白与标点、转小写。用于**记号级**比对（与技能脚本的 norm 同口径）。"""
    import re
    return re.sub(r"[\s　，。？！、；：,.?!;:'\"“”‘’（）()【】\[\]]+", "", str(text or "")).lower()


_FULLWIDTH = str.maketrans({
    "（": "(", "）": ")", "＝": "=", "＋": "+", "－": "-", "×": "*", "÷": "/",
    "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
    "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
})


def normalise_strict(text):
    """锚点比对专用的严格归一化：只去空白、统一全角，**保留括号与运算符**。

    为什么不能沿用 normalise：它会连括号一起去掉，于是原式 `2(x+3)=14` 与去括号
    后的错误式 `2x+3=14` 会归一成同一个串。那样一来，答案只要引用原式就会被判成
    「命中了去括号漏乘这条错误」，Recall 被虚高。锚点是逐字抄自草稿的片段，
    本来就该按字面比。
    """
    import re
    return re.sub(r"[\s　]+", "", str(text or "").translate(_FULLWIDTH)).lower()
