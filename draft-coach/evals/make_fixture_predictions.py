#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_fixture_predictions.py — 生成**测试夹具**用的预测文件。仅用标准库。

**这不是模型运行结果。** 产出方一律标成 `fixture:...`，`evaluate.py` 会在报告
顶部打警告，`is_model_run` 字段为 false。它的用途只有一个：在没有任何模型输出的
情况下，验证评测流程本身跑得通、且能抓到该抓的东西。

  python3 evals/make_fixture_predictions.py --mode oracle     --arm skill_gates --out predictions/fixtures/oracle.skill_gates.json
  python3 evals/make_fixture_predictions.py --mode empty      --arm skill       --out predictions/fixtures/empty.skill.json
  python3 evals/make_fixture_predictions.py --mode fabricated --arm skill_gates --out predictions/fixtures/fabricated.skill_gates.json

三种模式：

- `oracle`：照 gold 生成一张尽量合规的卡片（上界夹具）。跑门时**真实执行**脚本，
  tool_log 里的退出码是实测值，不是编的。
- `empty`：什么都不报的空壳（下界夹具）。
- `fabricated`：故意编造一条草稿里没有的错误，并把 tool_log 的退出码写成假的
  ——用来证明 S1 与 S5 检测真的会触发。
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # evals/ 自己
sys.path.insert(0, str(ROOT / "engine"))

from cases import load_cases  # noqa: E402
import gate_replay  # noqa: E402
import metrics as metrics_mod  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

GATE = metrics_mod.GATE
SAFE_SOURCE = "text_reconstruction"


def neutral_risk(dimension):
    return "若一直这样写，回头核对时可能要多花时间定位这一步。"


def build_oracle_card(case):
    data = case["input"]
    gold_errors = case.get("gold_errors") or []
    gold_dims = case.get("gold_dimensions") or {}
    draft = data.get("draft") or ""
    excerpt = (draft[:24] + "…") if len(draft) > 24 else draft

    errors = []
    for gold in gold_errors:
        anchor = (gold.get("evidence_anchor") or [""])[0]
        errors.append({
            "location": gold.get("location") or "草稿中段",
            "evidence": anchor,
            "explanation": gold.get("evidence_note") or "这一步与上一行对不上。",
            "fix": gold.get("minimal_fix") or "把这一行改成与上一行一致的形式。",
        })

    dimensions = {}
    for key in GATE.DIM_KEYS:
        gold = gold_dims.get(key) or {}
        label = gold.get("label") or "中"
        if key != "draft_to_solution" and label == "不适用":
            label = "中"
        basis = gold.get("basis") or "照草稿可见的书写形式判断。"
        item = {"score": label, "observation": basis, "evidence": basis,
                "risk": neutral_risk(key)}
        if key == "correction_pattern":
            wants_positive = gold.get("positive_expected") or bool(GATE.DRAFT_CORRECTION_RE.search(draft))
            if wants_positive:
                item["positive"] = "把写错的那一处划掉后补上了正确的式子，说明写到那里时自己回头核对过。"
        dimensions[key] = item

    habits = [
        {"habit": "关键一步不落笔", "impact": "回头核对时找不到这一步，出错也定位不到。",
         "training": "下一道题，把这一步单独写一行，写完再往下算。"},
        {"habit": "算完不回代检验", "impact": "结果偏了也不容易当场发现。",
         "training": "下一道题，解完后把结果代回原式写一行检验。"},
        {"habit": "草稿不分区", "impact": "检查时要整段重看，容易漏看某一处。",
         "training": "下一道题，先把草稿纸折成四格，已知和推导分开写。"},
    ]

    return {
        "error_check": {
            "scope": "有草稿；(夹具) 逐步核对了草稿可见的 %s 等步骤，未核对题意是否抄对。" % excerpt,
            "errors": errors,
        },
        "dimensions": dimensions,
        "top_3_habits": habits,
        "next_step": "下一道题，只做一件事：把关键那一步单独写一行，再往下算。",
        "grade_level": case.get("grade_level") or "高中",
        "draft_source": data.get("draft_source") if data.get("draft_source") in GATE.SOURCES else SAFE_SOURCE,
        "analysis_basis": GATE.FULL,
    }


def build_empty_card(case):
    card = build_oracle_card(case)
    card["error_check"]["errors"] = []
    for key in GATE.DIM_KEYS:
        card["dimensions"][key]["score"] = "中"
    return card


def build_fabricated_card(case):
    card = build_oracle_card(case)
    card["error_check"]["errors"].append({
        "location": "草稿右下角",
        "evidence": "草稿右下角还写了一行 48÷4=12，这里除数用错了。",
        "explanation": "除数用错了，后面的结果跟着一起偏。",
        "fix": "把这一行的除数换回正确的那个再重算。",
    })
    return card


BUILDERS = {"oracle": build_oracle_card, "empty": build_empty_card, "fabricated": build_fabricated_card}


def refusal_response(case):
    reason = case.get("refuse_reason")
    if case.get("expected_action") == "refuse" and reason in GATE.REFUSALS:
        return GATE.REFUSALS[reason][1]
    return "你这张草稿我还没法当成一道题来分析——麻烦先补一句：这道题要求什么？那几处记号分别代表什么？说清在算什么我就能帮你查计算。"


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成测试夹具用的预测文件（不是模型运行结果）")
    parser.add_argument("--mode", required=True, choices=sorted(BUILDERS))
    parser.add_argument("--arm", required=True, choices=["baseline", "skill", "skill_gates"])
    parser.add_argument("--dataset", default=str(ROOT))
    parser.add_argument("--config", default=str(ROOT / "config.json"))
    parser.add_argument("--splits", nargs="+", default=["development", "validation", "test"])
    parser.add_argument("--out", required=True)
    parser.add_argument("--lie", action="store_true",
                        help="把 tool_log 的退出码改成假的（仅 fabricated 模式有意义）")
    args = parser.parse_args(argv)

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    arm_config = config["experiments"][args.arm]
    cases = load_cases(args.dataset, tuple(args.splits))
    builder = BUILDERS[args.mode]

    predictions = []
    for case in cases:
        if case.get("expected_action") == "analyze":
            card = builder(case)
            tool_log = []
            if arm_config.get("runs_gates"):
                draft = gate_replay.audit_draft_for(case)
                result = gate_replay.replay_card(config, card, draft,
                                                 case["input"].get("final_solution"))
                tool_log = [
                    {"command": "validate --card <tmp>/card.json",
                     "exit_code": result["validate"]["exit"],
                     "stdout": json.dumps({"passed": result["validate"]["exit"] == 0,
                                           "errors": result["validate"]["errors"]},
                                          ensure_ascii=False)},
                    {"command": "audit --card <tmp>/card.json --draft <草稿> --strict",
                     "exit_code": result["audit_strict"]["exit"],
                     "stdout": json.dumps({"passed": result["audit_strict"]["exit"] == 0,
                                           "warnings": result["audit_strict"]["warnings"]},
                                          ensure_ascii=False)},
                ]
                if args.lie or args.mode == "fabricated":
                    tool_log[0]["exit_code"] = 0        # 谎称结构门过了
                    tool_log[1]["exit_code"] = 0        # 谎称审计过了
            predictions.append({"case_id": case["case_id"],
                                "response": "（夹具输出，不是模型回答）",
                                "card": card, "tool_log": tool_log})
        else:
            predictions.append({"case_id": case["case_id"],
                                "response": refusal_response(case),
                                "card": None, "tool_log": []})

    payload = {
        "arm": args.arm,
        "run_id": "fixture-%s-%s" % (args.mode, args.arm),
        "producer": "fixture:make_fixture_predictions.py --mode %s（不是模型运行结果）" % args.mode,
        "model_note": "无模型参与。本文件只用于验证评测流程本身，不得当作任何模型的成绩。",
        "predictions": predictions,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out": args.out, "mode": args.mode, "arm": args.arm,
                      "cases": len(predictions),
                      "cards": sum(1 for p in predictions if p["card"] is not None),
                      "warning": "这是夹具，不是模型运行结果"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
