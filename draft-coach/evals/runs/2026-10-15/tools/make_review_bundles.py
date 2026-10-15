#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_review_bundles.py — 给模型辅助层评审生成盲评包。

每个包 = 一条案例的输入 + 标准答案 + 某一个实验组在该案例上的产出 + 要评的指标
与判据。包名是哈希，**不暴露 case_id 与 arm**（`mapping.json` 只留在宿主手里），
让评审看不出自己在评哪一组。

  python3 make_review_bundles.py <run_dir> <evals_dir> <arm>...
"""

import hashlib
import json
import sys
from pathlib import Path

RUNS_ENGINE = Path(__file__).resolve().parents[3] / "engine"

RUBRIC = {
    "location_descriptor_correct":
        "答案指出的位置（location）与参考答案的 location 是否指同一步/同一行。"
        "指向同一处 → true；漏写位置或指到别处 → false。",
    "fix_correctness":
        "答案给出的「该改成什么」（fix / 应写成什么）方向是否正确。"
        "改成正确值或等价正确的式子 → true；改成另一个错值、或方向错 → false；"
        "完全没有给改法 → false。",
    "explanation_correctness":
        "错因解释在数学上是否成立。解释错（例如把移项错误说成除法错误）→ false；"
        "解释正确但不够详细 → true。",
    "evidence_support_rate":
        "答案引用的草稿证据是否**支持**它下的结论。证据确实在草稿里、"
        "且确实支持「这处错了」→ true；证据存在但结论下错（把对的判成错）→ false。",
    "minimal_fix_compliance":
        "改动范围是否限于被指出的那一步。只针对那一步给改法 → true；"
        "把整题重写、或给出完整解答 → false。",
    "dimension_evidence_grounded":
        "六维观察的 observation / evidence 是否出自草稿本身。"
        "任何一维编造了草稿里没有的涂改、试错、图形或记号 → false；否则 true。",
    "clarify_quality":
        "追问是否问到点上：问的是「这道题在算什么」「这几个记号各代表什么」"
        "「这块属于哪一题」→ true；问无关内容或没问清关键处 → false。",
    "multi_problem_handling":
        "草稿上有多道题时，是否先分块、并声明块与题目的归属（或声明归属未确认）。"
        "有分块且交代了归属 → true；不分块、或把多题当一题 → false。",
    "evaluable_scope_respected":
        "对参考答案 `unevaluable_scope` 里列出的事项（例如题意是否抄对、解题方向是否正确、"
        "知识漏洞），答案是否**没有**下确定结论。没下确定结论 → true；下了 → false。",
    "mixed_content_reading":
        "草稿里公式、文字说明、图形混排时，是否被正确读入（记号没读错、文字说明没漏掉）。"
        "读错记号或漏掉文字说明 → false；正确读入 → true。",
}

NULL_GUIDE = (
    "**null 与 false 不是一回事。** 没有可判对象时写 null（例：答案一处错都没报，"
    "就没有「改法对不对」可判；草稿只有一道题，就没有「多题分块」可判）；"
    "有可判对象而不合格才写 false。拿不准时先问「这条指标在本题上有没有对象」。"
)


def metrics_for(config, case):
    """该案例要评的模型辅助层指标。"""
    layer = config["metric_layers"]
    wanted = [n for n in config["subset_metrics"][case["subset"]]
              if layer.get(n) == "model_assisted"]
    card = case.get("_output", {}).get("card")
    gold_errors = case.get("gold_errors") or []
    reported = bool(gold_errors)
    if isinstance(card, dict):
        block = card.get("error_check")
        if isinstance(block, dict) and isinstance(block.get("errors"), list) and block["errors"]:
            reported = True
    if not reported:
        wanted = [n for n in wanted if n not in
                  ("location_descriptor_correct", "fix_correctness",
                   "explanation_correctness", "evidence_support_rate",
                   "minimal_fix_compliance")]
    if not isinstance(card, dict):
        wanted = [n for n in wanted if n != "dimension_evidence_grounded"]
    if case.get("expected_action") != "clarify":
        wanted = [n for n in wanted if n != "clarify_quality"]
    return wanted


def main(argv):
    run_dir = Path(argv[1]).resolve()
    evals_dir = Path(argv[2]).resolve()
    arms = argv[3:]

    sys.path.insert(0, str(RUNS_ENGINE))
    from cases import load_cases  # noqa: E402

    config = json.loads((evals_dir / "config.json").read_text(encoding="utf-8"))
    cases = {c["case_id"]: c for c in load_cases(evals_dir)}

    in_dir = run_dir / "reviews" / "in"
    in_dir.mkdir(parents=True, exist_ok=True)
    mapping, written = {}, {}

    for arm in arms:
        for case_id, case in sorted(cases.items()):
            out_path = run_dir / "out" / arm / (case_id + ".json")
            if not out_path.is_file():
                continue
            output = json.loads(out_path.read_text(encoding="utf-8"))
            case["_output"] = output
            names = metrics_for(config, case)
            if not names:
                continue
            raw = "%s|%s|%s" % (arm, case_id, len(names))
            bundle_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
            bundle = {
                "bundle_id": bundle_id,
                "说明": "盲评包：你不知道这条案例来自哪个实验组，也不需要知道。",
                "student_input": case.get("input"),
                "reference": {
                    "expected_action": case.get("expected_action"),
                    "refuse_reason": case.get("refuse_reason"),
                    "gold_errors": case.get("gold_errors"),
                    "gold_correct_steps": case.get("gold_correct_steps"),
                    "gold_dimensions": case.get("gold_dimensions"),
                    "evaluable_scope": case.get("evaluable_scope"),
                    "unevaluable_scope": case.get("unevaluable_scope"),
                    "expected_behaviors": case.get("expected_behaviors"),
                    "forbidden_behaviors": case.get("forbidden_behaviors"),
                    "notes": case.get("notes"),
                },
                "answer_under_review": {"response": output.get("response"),
                                        "card": output.get("card")},
                "metrics_to_rate": {n: RUBRIC[n] for n in names},
                "null_rule": NULL_GUIDE,
            }
            (in_dir / (bundle_id + ".json")).write_text(
                json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
            mapping[bundle_id] = {"arm": arm, "case_id": case_id, "subset": case["subset"],
                                  "metrics": names}
            written.setdefault(arm, {})[case_id] = bundle_id
            case.pop("_output", None)

    (run_dir / "reviews" / "mapping.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "reviews" / "bundles_by_arm.json").write_text(
        json.dumps(written, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"bundles": len(mapping),
                      "by_arm": {a: len(v) for a, v in written.items()}},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
