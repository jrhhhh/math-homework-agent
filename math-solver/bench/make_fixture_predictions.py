#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 oracle / bad 夹具。

oracle 用已保存的 solution JSON 拼成预测；bad 在 oracle 上定点破坏，
用来验证评分器能抓住错误答案、状态冲突、假 tool_log、错误转交与 OCR 声明。
"""

import argparse
import copy
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH))

from tools.data import CASES  # noqa: E402

ROUTE_REPLIES = {
    "MATH-29": ("math-error-diagnosis",
                "这是检查已有解答的任务，应转交 math-error-diagnosis；我不在这里重新求解。"),
    "MATH-30": ("draft-coach",
                "这是草稿版面习惯问题，应转交 draft-coach；我不判断计算对错。"),
}
CLARIFY_REPLIES = {
    "MATH-31": "这是已成立解法的优化请求；当前项目暂不提供优化技能，我不会在这里重做解答或冒充优化。",
    "MATH-32": "请把图片里的题面打成文字或口述给我；我不直接读取图片上的字符。",
}


def build_oracle():
    predictions = []
    for case in CASES:
        case_id = case["case_id"]
        action = case["expected_action"]
        if action == "solve":
            source = BENCH / case["_source_file"]
            output = json.loads(source.read_text(encoding="utf-8"))
            predictions.append({
                "case_id": case_id,
                "action": "solve",
                "output": output,
                "tool_log": [{
                    "command": f"python3 scripts/validate_output.py validate --card {case_id}.json --strict",
                    "exit_code": 0,
                }],
            })
        elif action == "route":
            route_to, reply = ROUTE_REPLIES[case_id]
            predictions.append({
                "case_id": case_id,
                "action": "route",
                "route_to": route_to,
                "reply": reply,
            })
        elif action == "clarify":
            predictions.append({
                "case_id": case_id,
                "action": "clarify",
                "reply": CLARIFY_REPLIES[case_id],
            })
    return predictions


def by_id(predictions):
    return {item["case_id"]: item for item in predictions}


def build_bad(oracle):
    predictions = copy.deepcopy(oracle)
    index = by_id(predictions)

    index["MATH-01"]["output"]["solution"]["answer"] = "x=1"
    index["MATH-02"]["output"]["status"] = "failed"
    index["MATH-03"]["tool_log"][0]["exit_code"] = 1
    index["MATH-04"].pop("tool_log", None)
    index["MATH-05"]["output"]["solution"]["conditions"].append("置信度 0.95")
    index["MATH-06"]["output"]["solution"]["conditions"].append("我用 Python 验证过")
    index["MATH-07"].pop("output", None)
    index["MATH-08"]["action"] = "route"
    index["MATH-08"]["route_to"] = "math-error-diagnosis"
    index["MATH-08"]["reply"] = "这是检查已有解答的任务。"
    index["MATH-10"]["output"]["verification"]["checks"][0]["details"] = "已验证"
    index["MATH-11"]["output"]["confidence"] = 0.99
    index["MATH-21"]["output"]["solution"]["answer"] = (
        "a<2：x<a 或 x>2；a=2：x≠2；a>2：x<a 或 x>2"
    )
    index["MATH-24"]["output"]["solution"]["answer"] = "S_5=62"
    index["MATH-29"]["route_to"] = "draft-coach"
    index["MATH-32"]["reply"] = "图片上写着 x=2，答案是 x=2。"
    return [item for item in predictions if item["case_id"] != "MATH-09"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成 math-solver 基准夹具")
    parser.add_argument("--mode", choices=["oracle", "bad"], required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    oracle = build_oracle()
    predictions = oracle if args.mode == "oracle" else build_bad(oracle)

    payload = {
        "arm": "skill_gates",
        "model": "oracle-fixture" if args.mode == "oracle" else "bad-fixture",
        "run_id": f"fixture-{args.mode}-2026-10-18",
        "predictions": predictions,
    }
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(predictions)} predictions to {path}")


if __name__ == "__main__":
    main()
