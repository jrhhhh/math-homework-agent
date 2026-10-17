# -*- coding: utf-8 -*-
"""案例、标准答案与预测文件的加载。仅用标准库。"""

import json
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parents[1]
CASES_FILE = "cases.jsonl"
GROUND_TRUTH_FILE = "ground_truth.jsonl"
SPLITS = ("development", "validation", "test")
ACTIONS = ("analyze", "partition", "refuse", "clarify")


def read_jsonl(path):
    rows = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError("%s 第 %d 行不是合法 JSON：%s" % (path, number, exc))
    return rows


def load_config(bench_dir=None):
    bench_dir = Path(bench_dir or BENCH_DIR)
    return json.loads((bench_dir / "config.json").read_text(encoding="utf-8"))


def load_raw(bench_dir=None):
    bench_dir = Path(bench_dir or BENCH_DIR)
    return (read_jsonl(bench_dir / CASES_FILE),
            read_jsonl(bench_dir / GROUND_TRUTH_FILE))


def load_cases(bench_dir=None, splits=None, subsets=None):
    """合并 cases.jsonl 与 ground_truth.jsonl，按 split / subset 过滤。"""
    cases_rows, truth_rows = load_raw(bench_dir)
    truth_by_id = {}
    for row in truth_rows:
        case_id = row.get("case_id")
        if case_id in truth_by_id:
            raise ValueError("ground_truth.jsonl 里 case_id 重复：%r" % case_id)
        truth_by_id[case_id] = row

    merged = []
    for row in cases_rows:
        case_id = row.get("case_id")
        truth = truth_by_id.get(case_id)
        if truth is None:
            raise ValueError("案例 %r 没有对应的 ground truth" % case_id)
        if splits and row.get("split") not in splits:
            continue
        if subsets and row.get("subset") not in subsets:
            continue
        case = dict(row)
        case["ground_truth"] = truth
        merged.append(case)
    return merged


def load_predictions(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("预测文件必须是 JSON 对象")
    predictions = {}
    for item in payload.get("predictions") or []:
        if not isinstance(item, dict):
            raise ValueError("predictions 里每项必须是 JSON 对象")
        case_id = item.get("case_id")
        if not case_id:
            raise ValueError("预测项缺少 case_id")
        if case_id in predictions:
            raise ValueError("预测里 case_id 重复：%r" % case_id)
        predictions[case_id] = item
    return payload, predictions


def audit_draft_for(case):
    """audit --draft 传什么：整张纸用分块后的那一块，否则用整份草稿。"""
    data = case.get("input") or {}
    block = data.get("audit_draft")
    return (block if block and str(block).strip() else data.get("draft")) or ""


def image_note(case):
    return (case.get("input") or {}).get("image_note") or ""


def draft_source(case):
    return (case.get("input") or {}).get("draft_source") or "text_reconstruction"
