#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""draft_gate_report.py — 对已保存的草稿评测回答重跑 draft-coach 的两道门。

用法：
  python3 tests/behavior-evaluation/draft_gate_report.py [DIR]

读 DIR/inputs.json、DIR/skill.json（若存在 DIR/baseline.json 也读），对每条回答：

  - 产出了卡片：把卡片写到临时文件，跑
      scripts/validate_output.py validate --card CARD
      scripts/audit_output.py    audit    --card CARD --draft DRAFT
      scripts/audit_output.py audit --card CARD --draft DRAFT … --strict
    把**真实退出码与命中的 error / warning 代码**原样记录。
每条回答都跑一遍 refuse 的三个出口，检查回答里是否出现对应的标准话术。
**只记录「哪几条话术出现过」，不判断该不该拒绝**——出现话术可能是整条请求被退回，
也可能只是婉拒其中越界的部分（例如草稿照查、变式题不要）。

`--draft` 取 inputs.json 的 `audit_draft`（有的话），否则取整份 `draft`。
整张草稿纸按 SKILL.md 必须分块逐题过门，`audit_draft` 就是那条题所在块的原文；
拿整张纸去审一张块级卡片，任何合规卡片都会触发 W_MULTI_PROBLEM_DRAFT。

它不验数学：validate 只查卡片结构，audit 只查越界措辞。
本技能只看版面习惯，不判断计算对错。**没有人工复核的读数不构成数学结论。**

退出码（沿用本项目约定）：
  0 = 每条产出的卡片都过两道门（含 --strict）；
  1 = 输入有效，但有卡片未过门，或一条卡片都没产出；
  2 = 输入非法（文件缺失 / JSON 坏 / 某条有卡片却拿不到 --draft）。

本脚本只读已保存的回答，不调用模型、不重新作答。
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:  # Windows 控制台默认编码可能是 GBK
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


SCRIPT_DIR = Path(__file__).resolve().parents[2] / "draft-coach" / "scripts"
VALIDATE_SCRIPT = SCRIPT_DIR / "validate_output.py"
AUDIT_SCRIPT = SCRIPT_DIR / "audit_output.py"
DEFAULT_DIR = Path(__file__).resolve().parent / "draft-coach-2026-10-15"
REFUSE_REASONS = ("empty", "unreadable", "out_of_scope")


class InputError(Exception):
    """输入非法，对应退出码 2。"""


def _script_for(args):
    """子命令在哪个脚本里：validate / hint 归结构门，audit / refuse 归审计门。"""
    return VALIDATE_SCRIPT if args and args[0] in ("validate", "hint") else AUDIT_SCRIPT


def run(*args):
    return subprocess.run([sys.executable, str(_script_for(args)), *args],
                          capture_output=True, encoding="utf-8", errors="replace")


def checker_json(*args):
    """跑门脚本并解析它的 JSON 输出；跑不起来就当成输入非法，别抛裸 traceback。"""
    script = _script_for(args)
    if not script.is_file():
        raise InputError("门脚本不存在：%s" % script)
    proc = run(*args)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise InputError("门脚本 %s 的 stdout 不是 JSON（退出码 %d）：%r"
                         % (" ".join(args), proc.returncode, (proc.stdout or "")[:200]))


def codes(payload):
    return sorted({item.get("code") for item in payload.get("errors", [])
                   if isinstance(item, dict) and item.get("code")})


def warn_codes(payload):
    return sorted({item.get("code") for item in payload.get("warnings", [])
                   if isinstance(item, dict) and item.get("code")})


def read_json(path):
    if not path.is_file():
        raise InputError("文件不存在：%s" % path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InputError("%s 不是合法 JSON：%s" % (path, exc))
    except UnicodeError as exc:
        raise InputError("%s 不是合法 UTF-8：%s" % (path, exc))


def gate_check(card, draft):
    """跑两道门，返回真实退出码与代码；顺带把脚本的原始 JSON 存下来。"""
    with tempfile.TemporaryDirectory() as tmp:
        card_path = Path(tmp) / "card.json"
        card_path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")

        result = {"validate": {}, "audit": {}, "audit_strict": {}}

        code, payload = checker_json("validate", "--card", str(card_path))
        result["validate"] = {"exit": code, "passed": payload.get("passed"),
                              "errors": codes(payload), "warnings": warn_codes(payload),
                              "raw": payload}

        base = ["audit", "--card", str(card_path), "--draft", draft]
        for key, extra in (("audit", []), ("audit_strict", ["--strict"])):
            code, payload = checker_json(*(base + extra))
            result[key] = {"exit": code, "passed": payload.get("passed"),
                           "errors": codes(payload), "warnings": warn_codes(payload),
                           "raw": payload}
    return result


def refusal_messages():
    """三条标准话术的真实文本，来自脚本本身，不在这里抄一遍。"""
    out = {}
    for reason in REFUSE_REASONS:
        code, payload = checker_json("refuse", "--reason", reason)
        out[reason] = {"message": payload["message"], "exit": code}
    return out


def report(directory):
    directory = Path(directory)
    inputs = read_json(directory / "inputs.json")
    if not isinstance(inputs, list):
        raise InputError("inputs.json 必须是数组")
    ids = [row.get("id") for row in inputs]
    if any(not isinstance(i, str) for i in ids) or len(ids) != len(set(ids)):
        raise InputError("inputs.json 的 id 必须是非空且互不重复的字符串")

    skill_rows = read_json(directory / "skill.json")
    if not isinstance(skill_rows, list):
        raise InputError("skill.json 必须是数组")
    skill = {row.get("id"): row for row in skill_rows}
    if [row.get("id") for row in skill_rows] != ids:
        raise InputError("skill.json 的 id 顺序必须与 inputs.json 完全一致")

    baseline = {}
    if (directory / "baseline.json").is_file():
        rows = read_json(directory / "baseline.json")
        if not isinstance(rows, list):
            raise InputError("baseline.json 必须是数组")
        baseline = {row.get("id"): row for row in rows}

    refusals = refusal_messages()
    per_case = []
    gate_failures, cards_produced = [], 0

    for row in inputs:
        case_id = row["id"]
        draft = row.get("draft") or ""
        # 整张草稿纸必须按块过门（SKILL.md 明写）：有 audit_draft 时用它，
        # 否则用整份 draft。两种口径都要在报告里写明，免得读数被误读。
        audit_draft = row.get("audit_draft") or draft
        entry = skill[case_id]
        card = entry.get("card")
        item = {"id": case_id, "kind": row.get("kind"), "grade_level": row.get("grade_level"),
                "draft_supplied": bool(draft.strip()), "card_produced": card is not None,
                "audit_draft_source": "audit_draft" if row.get("audit_draft") else "draft"}

        # 记录回答里出现了哪几条标准拒绝话术。**只报事实，不判断该不该拒绝**：
        # 出话术可能是整条请求被退回，也可能只是婉拒其中越界的部分。
        item["refusal_message_matched"] = {
            condition: sorted(
                reason for reason, info in refusals.items()
                if rows[case_id].get("response") and info["message"] in rows[case_id]["response"])
            for condition, rows in (("skill", skill), ("baseline", baseline)) if case_id in rows}

        if card is None:
            item["card"] = "none"
        else:
            cards_produced += 1
            if not audit_draft.strip():
                raise InputError("%s 产出了卡片，但 inputs.json 里没有可传给 --draft 的草稿" % case_id)
            item["card"] = gate_check(card, audit_draft)
            if item["card"]["validate"]["exit"] != 0 or item["card"]["audit_strict"]["exit"] != 0:
                gate_failures.append(case_id)
        per_case.append(item)

    clean = [c["id"] for c in per_case
             if c["card"] != "none" and c["card"]["validate"]["exit"] == 0
             and c["card"]["audit_strict"]["exit"] == 0]
    passed = not gate_failures and cards_produced > 0
    return {
        "directory": str(directory),
        "cases": len(inputs),
        "cards_produced": cards_produced,
        "validate_clean": sum(1 for c in per_case
                              if c["card"] != "none" and c["card"]["validate"]["exit"] == 0),
        "audit_clean": sum(1 for c in per_case
                           if c["card"] != "none" and c["card"]["audit"]["exit"] == 0),
        "audit_strict_clean": len(clean),
        "both_gates_clean": clean,
        "gate_failed_cases": gate_failures,
        "per_case": per_case,
        "passed": passed,
        "capability_note": "两道门都不验数学。validate 只查卡片结构，audit 只查越界措辞与"
                           "「错误证据在不在草稿里」（W_ERROR_NOT_IN_DRAFT）。"
                           "引用了草稿却把对的判成错的，这里一声不响。"
                           "本报告只重放已保存回答的退出码，不调用模型、不重新作答。",
    }


def main():
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    try:
        payload = report(directory)
    except InputError as exc:
        print(json.dumps({"error": "invalid input", "detail": str(exc)},
                         ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
