#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compare_gate_versions.py — 把已保存的真实卡片同时喂给**两版门脚本**，逐条对比。

改门脚本之后，"应该不会影响别的案例"是不能靠印象说的（AGENTS.md 明写）。
这个脚本把旧版脚本从 git 里取出来（或由调用方给定目录），对同一批卡片各跑一遍
validate 与 audit --strict，只列出**结果不同**的案例。

  python3 compare_gate_versions.py <evals_dir> <predictions.json> <old_scripts_dir>

old_scripts_dir 里要有 audit_output.py、validate_output.py 与 _rules.py 三份旧文件。
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "engine"))

from cases import load_cases  # noqa: E402
import gate_replay  # noqa: E402


def run(script, args):
    proc = subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, encoding="utf-8", errors="replace")
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {}
    codes = sorted({item.get("code") for item in payload.get("warnings", []) if isinstance(item, dict)}
                   | {item.get("code") for item in payload.get("errors", []) if isinstance(item, dict)})
    return proc.returncode, codes


def main(argv):
    evals_dir, predictions, old_dir = (Path(argv[1]).resolve(), Path(argv[2]).resolve(),
                                      Path(argv[3]).resolve())
    config = json.loads((evals_dir / "config.json").read_text(encoding="utf-8"))
    cases = {c["case_id"]: c for c in load_cases(evals_dir)}
    payload = json.loads(predictions.read_text(encoding="utf-8"))

    new = {"validate": evals_dir.parent / "scripts/validate_output.py",
           "audit": evals_dir.parent / "scripts/audit_output.py"}
    old = {"validate": old_dir / "validate_output.py", "audit": old_dir / "audit_output.py"}

    diffs, checked = [], 0
    for item in payload["predictions"]:
        card = item.get("card")
        if card is None:
            continue
        case = cases.get(item["case_id"])
        if case is None:
            continue
        draft = gate_replay.audit_draft_for(case)
        if not draft.strip():
            continue
        checked += 1
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "card.json"
            path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
            base = ["audit", "--card", str(path), "--draft", draft]
            if case.get("input", {}).get("final_solution"):
                base += ["--final-solution", case["input"]["final_solution"]]
            audit_args = base + ["--strict"]
            validate_args = ["validate", "--card", str(path)]

            for name, args in (("validate", validate_args), ("audit", audit_args)):
                a = run(new[name], args)
                b = run(old[name], args)
                if a != b:
                    diffs.append({"case_id": item["case_id"], "gate": name,
                                  "old": {"exit": b[0], "codes": b[1]},
                                  "new": {"exit": a[0], "codes": a[1]}})

    print(json.dumps({"cards_checked": checked, "differences": len(diffs),
                      "detail": diffs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
