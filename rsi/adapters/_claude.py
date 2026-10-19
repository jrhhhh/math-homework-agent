# -*- coding: utf-8 -*-
"""本机 claude CLI 的公共封装。

只用 `claude -p` 的非交互模式：
- 不启用任何工具（`--tools ""`），因此模型不会声称跑过 Python/SymPy；
- `--safe-mode` 避免项目/用户的 CLAUDE.md、skills、hooks 污染实验；
- prompt 从 stdin 传入，避开 Windows 命令行长度限制；
- 记录 CLI 返回的 token 与美元成本。

权限说明：这里没有使用 `--dangerously-skip-permissions` 或
`--permission-mode bypassPermissions`。模型侧没有工具，文件写入由 adapter
自己的 Python 代码完成。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any


class ClaudeError(RuntimeError):
    """CLI 无法执行或返回无法解析。"""


def claude_bin() -> str:
    """返回可执行的 claude 路径。

    Windows 上 `claude` 可能是无扩展名的 shell 脚本，subprocess 直接调用会
    FileNotFoundError；`shutil.which` 会优先找到 `claude.CMD`。
    """
    override = os.environ.get("CLAUDE_BIN")
    if override:
        return override
    for name in ("claude", "claude.cmd"):
        found = shutil.which(name)
        if found:
            return found
    return "claude"


def parse_result(stdout: str) -> dict[str, Any] | None:
    """从 CLI stdout 中找出最后的 result JSON。

    CLI 可能先打印 `[claude-code:unrecognized_model] ...` 之类的非 JSON 行；
    真正的 result 是一整行 JSON。
    """
    found = None
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and ("result" in payload or payload.get("type") == "result"):
            found = payload
    return found


def run_claude(user_prompt: str, system_prompt: str | None = None, *,
               system_prompt_file: str | None = None,
               max_budget_usd: float, timeout: float,
               model: str | None = None,
               cwd: str | None = None) -> dict[str, Any]:
    """调用 `claude -p`。

    长技能文本必须走 `--system-prompt-file`，不要塞进 stdin 的用户消息：
    这个 provider/CLI 组合在用户消息过长时会退化成“直接打印文本”，
    stream-json 的 usage/cost 就丢了。
    """
    if not system_prompt and not system_prompt_file:
        raise ClaudeError("需要 system_prompt 或 system_prompt_file")
    argv = [
        claude_bin(), "-p",
        "--tools", "",
        "--safe-mode",
        "--verbose",
        "--output-format", "stream-json",
        "--no-session-persistence",
        "--max-budget-usd", f"{max_budget_usd:.4f}",
    ]
    if system_prompt_file:
        argv.extend(["--system-prompt-file", system_prompt_file])
    else:
        argv.extend(["--system-prompt", system_prompt])
    if model:
        argv.extend(["--model", model])
    try:
        result = subprocess.run(
            argv,
            input=user_prompt,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        raise ClaudeError(f"找不到 claude CLI：{claude_bin()}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ClaudeError(f"claude CLI 超时（{timeout}s）") from exc

    if result.returncode != 0:
        raise ClaudeError(
            f"claude CLI 退出 {result.returncode}："
            f"{(result.stderr or result.stdout)[:1000]}")

    payload = parse_result(result.stdout)
    if payload is None:
        # 某些 provider/CLI 组合会把模型文本直接写到 stdout，不套 result 信封。
        # 这时仍然可以拿到预测，但拿不到 usage/cost。
        text = "\n".join(
            line for line in result.stdout.splitlines()
            if not line.strip().startswith("[claude-code"))
        if not text.strip():
            raise ClaudeError(
                f"无法从 CLI 输出解析 result JSON：{result.stdout[:800]}")
        payload = {
            "type": "result",
            "result": text.strip(),
            "usage": {},
            "total_cost_usd": None,
            "num_turns": 1,
            "is_error": False,
            "fallback_direct_output": True,
        }
    return payload


def usage_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    usage = payload.get("usage") or {}
    input_tokens = sum(int(usage.get(key) or 0) for key in (
        "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    output_tokens = int(usage.get("output_tokens") or 0)
    return {
        "total_tokens": input_tokens + output_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": payload.get("total_cost_usd"),
        "num_turns": payload.get("num_turns"),
        "tool_calls": 0,
    }


def budget_usd(request: dict[str, Any], default: float,
               env_key: str) -> float:
    env_value = os.environ.get(env_key)
    if env_value:
        try:
            return float(env_value)
        except ValueError:
            pass
    budget = request.get("budget") or {}
    value = budget.get("max_cost_usd")
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    return default


def timeout_seconds(request: dict[str, Any], default: float = 900.0) -> float:
    budget = request.get("budget") or {}
    value = budget.get("max_seconds")
    if isinstance(value, (int, float)) and value > 0:
        return float(value) + 120.0
    return default


def extract_json_object(text: str) -> dict[str, Any] | None:
    """从模型输出里提取一个预测/编辑对象。

    优先返回带 action 的对象，其次返回 solution JSON、route、clarify。
    允许模型在 JSON 前后夹带少量说明；不依赖 markdown 围栏。
    """
    decoder = json.JSONDecoder()
    candidates: list[dict[str, Any]] = []
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            candidates.append(obj)

    for obj in candidates:
        if obj.get("action") in ("solve", "route", "clarify"):
            return obj
    for obj in candidates:
        if "status" in obj and isinstance(obj.get("solution"), dict):
            return {"action": "solve", "output": obj}
    for obj in candidates:
        if isinstance(obj.get("route_to"), str):
            return {"action": "route", "route_to": obj["route_to"],
                    "reply": str(obj.get("reply") or "")}
    for obj in reversed(candidates):
        if isinstance(obj.get("reply"), str):
            return {"action": "clarify", "reply": obj["reply"]}
    return None


def extract_edits_object(text: str) -> dict[str, Any] | None:
    """提取外层改写对象（带 edits / rationale 的 JSON）。"""
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and (
                isinstance(obj.get("edits"), list) or "rationale" in obj):
            return obj
    return None


def prediction_from_text(text: str) -> dict[str, Any]:
    parsed = extract_json_object(text)
    if parsed is None:
        return {"action": None, "adapter_error": "无法从模型输出解析预测"}
    action = parsed.get("action")
    if action == "solve":
        output = parsed.get("output")
        if not isinstance(output, dict):
            return {"action": None, "adapter_error": "solve 预测缺少 output 对象"}
        return {"action": "solve", "output": output}
    if action == "route":
        return {"action": "route",
                "route_to": parsed.get("route_to"),
                "reply": str(parsed.get("reply") or "")}
    if action == "clarify":
        return {"action": "clarify", "reply": str(parsed.get("reply") or "")}
    return {"action": None, "adapter_error": f"未知 action：{action!r}"}
