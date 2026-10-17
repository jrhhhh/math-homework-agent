# -*- coding: utf-8 -*-
"""重放技能自己的三道门，并核对 tool_log 声称的退出码。

这是评测里唯一不由模型产出的读数。两道分析门仍然**不验数学**，
分区门也**不验证图片**；它们只回答「卡片/分块单有没有越过结构线与措辞线」。
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .rules_bridge import REFUSALS

BENCH_DIR = Path(__file__).resolve().parents[1]


class GateRunner:
    def __init__(self, config, bench_dir=None):
        self.config = config
        self.bench_dir = Path(bench_dir or BENCH_DIR)

    def script(self, key):
        mapping = self.config.get("gate_scripts") or {}
        raw = mapping.get(key)
        if not raw:
            raise FileNotFoundError("config 的 gate_scripts 里没有 %r" % key)
        path = (self.bench_dir / raw).resolve()
        if not path.is_file():
            raise FileNotFoundError("门脚本不存在：%s" % path)
        return path

    def run(self, key, *args):
        proc = subprocess.run(
            [sys.executable, str(self.script(key)), *args],
            capture_output=True, encoding="utf-8", errors="replace",
        )
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = {"_unparsable_stdout": (proc.stdout or "")[:400],
                       "_stderr": (proc.stderr or "")[:400]}
        return proc.returncode, payload

    def validate(self, card):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "card.json"
            path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
            code, payload = self.run("validate", "validate", "--card", str(path))
        return self._result(code, payload)

    def audit(self, card, draft, strict=False):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "card.json"
            path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
            args = ["audit", "--card", str(path), "--draft", str(draft or "")]
            if strict:
                args.append("--strict")
            code, payload = self.run("audit", *args)
        return self._result(code, payload)

    def partition(self, payload, strict=False):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "partition.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            args = ["validate", "--payload", str(path)]
            if strict:
                args.append("--strict")
            code, out = self.run("partition", *args)
        return self._result(code, out)

    @staticmethod
    def _result(code, payload):
        errors = payload.get("errors") if isinstance(payload, dict) else []
        warnings = payload.get("warnings") if isinstance(payload, dict) else []
        return {
            "exit": code,
            "errors": [item for item in (errors or []) if isinstance(item, dict)],
            "warnings": [item for item in (warnings or []) if isinstance(item, dict)],
            "error_codes": sorted({item.get("code") for item in (errors or [])
                                   if isinstance(item, dict) and item.get("code")}),
            "warning_codes": sorted({item.get("code") for item in (warnings or [])
                                     if isinstance(item, dict) and item.get("code")}),
            "payload": payload,
        }


_SUBCOMMAND_RE = re.compile(r"(?:^|\s)(refuse|partition|audit|validate)(?:\s|$)")


def claimed_exit_codes(tool_log):
    """从 tool_log 命令里抠出 {子命令: (退出码, 是否 strict)}。

    同一子命令出现多次时**取最后一次**：重试后交付的是最终那次门运行，
    不能拿第一次失败的退出码去对最终卡片。
    """
    claimed = {}
    for entry in tool_log or []:
        if not isinstance(entry, dict):
            continue
        command = str(entry.get("command") or "")
        key = None
        if "partition_check" in command:
            key = "partition"
        elif re.search(r"(?:^|\s)refuse(?:\s|$)", command):
            key = "refuse"
        elif "audit_output" in command:
            key = "audit"
        elif "validate_output" in command:
            key = "validate"
        else:
            match = _SUBCOMMAND_RE.search(command)
            key = match.group(1) if match else None
        if key:
            claimed[key] = {
                "exit_code": entry.get("exit_code"),
                "strict": "--strict" in command,
            }
    return claimed


def tool_log_fidelity(prediction, real, case):
    """返回 (0–1 或 None, 不匹配说明列表)。None = 没有可核对的工具记录。"""
    claimed = claimed_exit_codes((prediction or {}).get("tool_log"))
    if not claimed:
        return None, []

    truth = {}
    action = (prediction or {}).get("action")
    if action == "analyze" and real.get("validate") is not None:
        truth["validate"] = real["validate"]["exit"]
        audit_key = "audit_strict" if claimed.get("audit", {}).get("strict") \
            else "audit"
        if real.get(audit_key) is not None:
            truth["audit"] = real[audit_key]["exit"]
    elif action == "partition" and real.get("partition") is not None:
        partition_key = "partition_strict" if claimed.get("partition", {}).get("strict") \
            else "partition"
        if real.get(partition_key) is not None:
            truth["partition"] = real[partition_key]["exit"]
    elif action == "refuse":
        reason = ((prediction.get("refusal") or {}).get("reason")
                  or case.get("refuse_reason"))
        if reason in REFUSALS:
            truth["refuse"] = REFUSALS[reason][2]

    comparisons, mismatches = [], []
    for key, value in claimed.items():
        if key not in truth:
            continue
        comparisons.append(int(value["exit_code"] == truth[key]))
        if value["exit_code"] != truth[key]:
            mismatches.append("%s 声称退出码 %r，重放实测 %r"
                              % (key, value["exit_code"], truth[key]))
    if not comparisons:
        return None, mismatches
    return sum(comparisons) / len(comparisons), mismatches
