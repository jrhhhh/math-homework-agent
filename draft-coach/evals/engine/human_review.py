#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""human_review.py — 人工（与模型辅助）评审的导出与回读。仅用标准库。

自动指标算不了的东西——证据是否**支持**结论、错因解释是否成立、改法对不对、
六维观察是否属实——不在这里伪造分数。这里只提供接口：

  # 1) 导出待评表（每个案例只列该层该管的指标，值先留 null）
  python3 evals/engine/human_review.py export --layer human \
      --arm skill_gates --out reviews/skill_gates.human.json

  # 2) 人工把 true/false 填进去（null 表示还没评，与 false 不是一回事）

  # 3) 回读检查覆盖情况
  python3 evaluators/human_review.py check --review reviews/skill_gates.human.json

  # 4) 交给 evaluate.py 计分
  python3 evals/evaluate.py --predictions ... --review reviews/skill_gates.human.json

退出码沿用本项目约定：0 = 通过 / 干净；1 = 有效但有缺口（有指标还没评）；2 = 非法输入。
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))

from cases import load_cases  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

LAYERS = ("model_assisted", "human")


def load_config(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def metrics_for_layer(config, layer):
    """哪些指标属于这一层。"""
    return sorted(name for name, value in config["metric_layers"].items() if value == layer)


def export_template(config, cases, layer, arm, reviewer="", model_note=""):
    wanted = set(metrics_for_layer(config, layer))
    rows = []
    for case in cases:
        names = [n for n in config["subset_metrics"][case["subset"]] if n in wanted]
        if not names:
            continue
        rows.append({
            "case_id": case["case_id"],
            "subset": case["subset"],
            "draft": case["input"].get("draft"),
            "prompt": case["input"].get("prompt"),
            "metrics": {name: None for name in names},
            "notes": "",
        })
    return {
        "arm": arm,
        "layer": layer,
        "reviewer": reviewer,
        "model_note": model_note or "未填写。无法核实精确模型版本时不要声称可逐字复现。",
        "instructions": [
            "只填 true / false；null 表示还没评，不参与分母，与 false 不是一回事。",
            "不要按文字长短打分。",
            "证据存在不等于证据支持结论：先自己把这道题算一遍，再判。",
            "评完后运行 human_review.py check 与 evaluate.py --review 本文件。",
        ],
        "ratings": rows,
    }


def check_review(payload, config):
    known = set(config["metric_layers"])
    problems, filled, blank = [], 0, 0
    if payload.get("layer") not in LAYERS:
        problems.append("layer 必须是 model_assisted 或 human")
    seen = set()
    for row in payload.get("ratings") or []:
        case_id = row.get("case_id")
        if case_id in seen:
            problems.append("同一 case_id 重复：%s" % case_id)
        seen.add(case_id)
        for name, value in (row.get("metrics") or {}).items():
            if name not in known:
                problems.append("%s 出现未知指标名 %r" % (case_id, name))
                continue
            if value is None:
                blank += 1
            elif isinstance(value, bool):
                filled += 1
            else:
                problems.append("%s/%s 必须是布尔值或 null，实为 %r" % (case_id, name, value))
    return {"reviewer": payload.get("reviewer"), "layer": payload.get("layer"),
            "ratings_filled": filled, "ratings_blank": blank,
            "problems": problems, "passed": not problems}


def main(argv=None):
    parser = argparse.ArgumentParser(description="人工 / 模型辅助评审的导出与回读")
    sub = parser.add_subparsers(dest="command", required=True)

    p_export = sub.add_parser("export", help="导出待评表")
    p_export.add_argument("--layer", required=True, choices=list(LAYERS))
    p_export.add_argument("--arm", default="skill_gates")
    p_export.add_argument("--dataset", default=str(ROOT), help="装 cases.jsonl 与 ground_truth.jsonl 的目录")
    p_export.add_argument("--config", default=str(ROOT / "config.json"))
    p_export.add_argument("--reviewer", default="")
    p_export.add_argument("--out", required=True)

    p_check = sub.add_parser("check", help="回读评审文件并检查覆盖")
    p_check.add_argument("--review", required=True)
    p_check.add_argument("--config", default=str(ROOT / "config.json"))

    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "export":
            cases = load_cases(args.dataset)
            payload = export_template(config, cases, args.layer, args.arm, args.reviewer)
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
            print(json.dumps({"out": args.out, "layer": args.layer,
                              "cases": len(payload["ratings"]),
                              "metrics_per_case": {row["case_id"]: sorted(row["metrics"])
                                                   for row in payload["ratings"]}},
                             ensure_ascii=False, indent=2))
            return 0
        payload = json.loads(Path(args.review).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        print(json.dumps({"error": "invalid input", "detail": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": "invalid input", "detail": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    result = check_review(payload, config)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        return 2
    return 1 if result["ratings_blank"] else 0


if __name__ == "__main__":
    sys.exit(main())
