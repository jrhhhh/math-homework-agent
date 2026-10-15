#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_reviews.py — 把盲评包的结果拼成 evaluate.py 认的评审文件。

盲评包在 reviews/in/<hash>.json，评审结果在 reviews/out/<hash>.json，
键名对照表在 reviews/mapping.json。这里按 arm 分文件汇总。

  python3 merge_reviews.py <run_dir> <arm> <out.json> <reviewer> <model_note>
"""

import json
import sys
from pathlib import Path


def main(argv):
    run_dir = Path(argv[1]).resolve()
    arm, out_path, reviewer, model_note = argv[2:6]
    mapping = json.loads((run_dir / "reviews" / "mapping.json").read_text(encoding="utf-8"))
    out_dir = run_dir / "reviews" / "out"

    rows, expected, got, problems = [], 0, 0, []
    for bundle_id, meta in sorted(mapping.items()):
        if meta["arm"] != arm:
            continue
        expected += len(meta["metrics"])
        path = out_dir / (bundle_id + ".json")
        if not path.is_file():
            problems.append("%s: 评审结果缺失" % meta["case_id"])
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        rated = payload.get("ratings") or {}
        for name in meta["metrics"]:
            value = rated.get(name, "MISSING")
            if value == "MISSING":
                problems.append("%s/%s: 没给" % (meta["case_id"], name))
            elif value is not None and not isinstance(value, bool):
                problems.append("%s/%s: 必须是布尔或 null，实为 %r"
                                % (meta["case_id"], name, value))
            elif value is not None:
                got += 1
        rows.append({
            "case_id": meta["case_id"],
            "subset": meta["subset"],
            "metrics": {n: rated.get(n) for n in meta["metrics"]},
            "notes": payload.get("notes", ""),
        })

    payload = {"arm": arm, "layer": "model_assisted", "reviewer": reviewer,
               "model_note": model_note, "ratings": rows}
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"arm": arm, "cases": len(rows), "ratings_filled": got,
                      "ratings_expected": expected, "problems": problems[:20],
                      "problem_count": len(problems), "out": str(out)},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
