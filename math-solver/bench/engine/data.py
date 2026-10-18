# -*- coding: utf-8 -*-
"""数据加载与索引。"""

import json
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_jsonl(path):
    rows = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def index_by_id(rows):
    return {row["case_id"]: row for row in rows}


def load_dataset_paths(cases_path, truth_path, config_path):
    cases = load_jsonl(cases_path)
    truths = index_by_id(load_jsonl(truth_path))
    config = load_json(config_path)
    return cases, truths, config


def load_dataset(bench_dir):
    bench = Path(bench_dir)
    return load_dataset_paths(bench / "cases.jsonl",
                              bench / "ground_truth.jsonl",
                              bench / "config.json")


def load_predictions(path):
    payload = load_json(path)
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        raise ValueError("predictions 文件缺少 predictions 数组")
    return payload, index_by_id(predictions)
