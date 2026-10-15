#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""assemble.py — 把逐案例的产出文件拼成 evaluation 的 prediction 文件。

  python3 assemble.py <run_dir> <arm> <run_id> <producer> <model_note> <out.json>

产出代理写的是 {case_id, response, card, tool_log, notes}；prediction schema 只认
{case_id, response, card, tool_log}，所以 notes 抽到 <out>.notes.json 单独存放，
不进评分文件。缺失的案例**不补造**——缺就是缺，让评测器报 missing。
"""

import json
import sys
from pathlib import Path


def main(argv):
    run_dir, arm, run_id, producer, model_note, out_path = argv[1:7]
    run_dir = Path(run_dir)
    known = sorted(p.stem for p in (run_dir / "inputs").glob("*.json"))

    predictions, notes, missing = [], {}, []
    for case_id in known:
        path = run_dir / "out" / arm / (case_id + ".json")
        if not path.is_file():
            missing.append(case_id)
            continue
        item = json.loads(path.read_text(encoding="utf-8"))
        predictions.append({
            "case_id": case_id,
            "response": item.get("response") or "",
            "card": item.get("card"),
            "tool_log": item.get("tool_log") or [],
        })
        if item.get("notes"):
            notes[case_id] = item["notes"]

    payload = {"arm": arm, "run_id": run_id, "producer": producer,
               "model_note": model_note, "predictions": predictions}
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if notes:
        (out.with_suffix(".notes.json")).write_text(
            json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"arm": arm, "written": len(predictions), "missing": missing,
                      "with_card": sum(1 for p in predictions if p["card"] is not None),
                      "out": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
