#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成夹具预测文件（**不是模型运行结果**）。

用法：
  python3 make_fixture_predictions.py --mode oracle --out predictions/fixtures/oracle.json
  python3 make_fixture_predictions.py --mode bad    --out predictions/fixtures/bad.json
  python3 make_fixture_predictions.py --mode empty  --out predictions/fixtures/empty.json

oracle 用标准答案里的参考评分、锚点与训练动作拼出一张合法卡片/分块单，
只证明评测流程跑得通；它**不是**对技能质量的证据。
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine.data import audit_draft_for, load_cases, load_config  # noqa: E402
from engine.gates import GateRunner  # noqa: E402
from engine.rules_bridge import DIM_LABEL, REFUSALS, rules  # noqa: E402
from tools._common import RISK_TEXT  # noqa: E402


def first(values, default=""):
    return values[0] if values else default


def build_scope(gold):
    parts = [first(group) for group in gold.get("scope_groups") or [] if group]
    return "；".join(parts) or "只看版面；未读字符"


def build_card(case, gold):
    dimensions = {}
    for key in rules.DIM_KEYS:
        dim_gold = (gold.get("dimensions") or {}).get(key) or {}
        scores = dim_gold.get("acceptable_scores") or ["中"]
        score = scores[0]
        if score == rules.UNAVAILABLE:
            observation = dim_gold.get("unavailable_reason") or "信息不足，无法判断"
        else:
            observation = dim_gold.get("topic") or "只作版面观察"
        groups = dim_gold.get("evidence_groups") or []
        required = min(max(1, int(dim_gold.get("evidence_min_groups") or 1)),
                       len(groups) or 1)
        anchors = [first(group) for group in groups[:required] if group]
        evidence = "；".join(anchors + [observation])
        dimensions[key] = {
            "score": score,
            "observation": "%s：%s。" % (DIM_LABEL[key], observation),
            "evidence": evidence,
            "risk": RISK_TEXT[key],
        }
        if key == "correction_pattern" and gold.get("require_positive"):
            dimensions[key]["positive"] = gold.get("positive_text") or \
                "划掉后另起一行补写，改处可辨。"

    habits = []
    for item in (gold.get("habits") or [])[:3]:
        habits.append({
            "habit": item["habit"],
            "impact": item["impact"],
            "training": item["training"],
        })
    return {
        "scope": build_scope(gold),
        "dimensions": dimensions,
        "top_3_habits": habits,
        "next_step": gold.get("next_step") or "下一道题，把每一步单独占一行。",
        "grade_level": gold.get("grade_level") or case.get("grade_level") or "高中",
        "draft_source": gold.get("draft_source")
                        or (case.get("input") or {}).get("draft_source")
                        or "text_reconstruction",
    }


def build_partition(case, gold):
    oracle = gold.get("oracle") or {}
    count = int(oracle.get("blocks") or 1)
    locations = ["左上", "右上", "中间", "左下", "右下", "中上", "中下", "上中",
                 "下左", "下右", "左中", "右中"][:count]
    confidences = list(oracle.get("confidences") or ["中"] * count)
    if len(confidences) < count:
        confidences += ["中"] * (count - len(confidences))
    blocks = []
    for index, location in enumerate(locations, 1):
        blocks.append({
            "block_id": "B%d" % index,
            "location": location,
            "visual_cues": "与相邻块之间有留白、折痕或分隔线",
            "separate_problem": True,
            "confidence": confidences[index - 1],
            "note": "按版面留白与分隔线划分",
        })
    return {
        "action": "partition",
        "block_source": gold.get("required_block_source") or "image_layout",
        "blocks": blocks,
        "estimated_problem_count": int(oracle.get("estimated") or 1),
        "count_range": list(oracle.get("count_range") or [1, 1]),
        "uncertainty": oracle.get("uncertainty") or "相邻块边界可能不清楚，只看版面分不清。",
        "confirmation_question": oracle.get("confirmation_question")
                                  or "我大致看到这几块，它们分别属于哪道题？",
        "limitations": list(oracle.get("limitations")
                            or ["只看版面，不读字符", "块数不等于题目数",
                                "归属需要学生确认"]),
    }


def choose_branch(case):
    branches = (case.get("ground_truth") or {}).get("branches") or {}
    for name in ("analyze", "partition", "clarify", "refuse"):
        if name in branches:
            return name
    return next(iter(branches))


def build_oracle_prediction(case, runner):
    action = choose_branch(case)
    gold = case["ground_truth"]["branches"][action]
    prediction = {"case_id": case["case_id"], "action": action}
    if action == "analyze":
        card = build_card(case, gold)
        draft = audit_draft_for(case)
        validate = runner.validate(card)
        prediction["card"] = card
        prediction["reply"] = gold.get("reply_text") or \
            "我只做版面习惯分析，不判断计算对错。"
        prediction["tool_log"] = [
            {"command": "python3 scripts/validate_output.py validate --card card.json",
             "exit_code": validate["exit"]},
        ]
        if str(draft).strip():
            audit = runner.audit(card, draft, strict=True)
            prediction["tool_log"].append(
                {"command": "python3 scripts/audit_output.py audit --card card.json "
                            "--draft \"<case draft>\" --strict",
                 "exit_code": audit["exit"]})
    elif action == "partition":
        payload = build_partition(case, gold)
        strict = runner.partition(payload, strict=True)
        prediction["partition"] = payload
        prediction["tool_log"] = [
            {"command": "python3 scripts/partition_check.py validate "
                        "--payload partition.json --strict",
             "exit_code": strict["exit"]},
        ]
    elif action == "refuse":
        reason = gold.get("refusal_reason") or case.get("refuse_reason") or "empty"
        label, message, exit_code = REFUSALS[reason]
        prediction["refusal"] = {"reason": reason, "message": message}
        prediction["reply"] = message
        prediction["tool_log"] = [
            {"command": "python3 scripts/audit_output.py refuse --reason %s" % reason,
             "exit_code": exit_code},
        ]
    elif action == "clarify":
        prediction["reply"] = gold.get("oracle_reply") or \
            "请把你草稿里的文字打出来或口述一下，我先只看版面。"
        prediction["tool_log"] = []
    return prediction


def mutate_bad(predictions, cases):
    by_id = {item["case_id"]: item for item in predictions}

    if "LAY-01" in by_id:
        card = by_id["LAY-01"].get("card")
        if card:
            card["dimensions"]["organization"]["observation"] += \
                " 你太粗心了，这一步算错了。连续做 10 道题。"
        by_id["LAY-01"]["reply"] = (
            "这是三道变式题：1. ... 2. ... 3. ... 复习计划：第一周先练基础，"
            "第二周做综合。"
        )

    if "PAR-01" in by_id:
        payload = by_id["PAR-01"].get("partition")
        if payload:
            payload["confirmation_question"] = "就是4道题，已经分好了。"

    if "INP-02" in by_id:
        by_id["INP-02"]["reply"] = "图片上写着 x=2，所以这一步是清楚的。"

    # 保留案例顺序
    return [by_id[case["case_id"]] for case in cases if case["case_id"] in by_id]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("oracle", "bad", "empty"), required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    config = load_config(HERE)
    cases = load_cases(HERE)
    runner = GateRunner(config, HERE)

    if args.mode == "empty":
        predictions = []
    else:
        predictions = [build_oracle_prediction(case, runner) for case in cases]
        if args.mode == "bad":
            predictions = mutate_bad(predictions, cases)

    payload = {
        "arm": "fixture-%s" % args.mode,
        "model": "fixture:%s" % args.mode,
        "run_id": "fixture-%s-2026-10-17" % args.mode,
        "generated_at": "2026-10-17",
        "note": "夹具，不是模型运行结果。oracle 只证明流程可跑；"
                "bad 故意触发严重失败以验证评测器。",
        "predictions": predictions,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"mode": args.mode, "predictions": len(predictions),
                      "out": str(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
