"""Inference through the user's installed, authenticated Codex CLI.

Each request runs in an empty temporary directory, without project instructions.
No task delegation or development work is requested: only one mathematical JSON response.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


class ModelError(RuntimeError):
    pass


def available():
    return bool(shutil.which(os.environ.get('MATH_CODEX_BIN', 'codex')))


def generate(prompt, timeout=240):
    binary = shutil.which(os.environ.get('MATH_CODEX_BIN', 'codex'))
    if not binary:
        raise ModelError('未找到 Codex CLI，请安装并登录后重试。')
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='math-inference-') as folder:
        output = Path(folder) / 'answer.txt'
        command = [binary, 'exec', '--ephemeral', '--skip-git-repo-check',
                   '--sandbox', 'read-only', '--json', '--color', 'never',
                   '-c', 'features.shell_tool=false', '-c', 'features.multi_agent=false',
                   '-C', folder, '-o', str(output), '-']
        if os.environ.get('MATH_MODEL'):
            command[2:2] = ['--model', os.environ['MATH_MODEL']]
        try:
            result = subprocess.run(command, input=prompt, text=True, capture_output=True,
                                    timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise ModelError('模型调用超时；本次没有生成可交付结果。') from exc
        events = []
        for line in result.stdout.splitlines():
            try:
                events.append(json.loads(line))
            except ValueError:
                pass
        if result.returncode or not output.exists():
            # Avoid returning stderr: CLI diagnostics can contain local account details.
            raise ModelError('模型调用失败，请检查 Codex 登录状态与网络。')
        raw = output.read_text(encoding='utf-8').strip()
        usage = [e.get('usage') for e in events if e.get('type') == 'turn.completed']
        return {'raw': raw, 'elapsed_seconds': round(time.monotonic()-started, 3),
                'usage': usage, 'events': events, 'backend': 'codex-cli',
                'requested_model': os.environ.get('MATH_MODEL', 'user-config-default')}


def parse_json(raw):
    text = raw.strip()
    if text.startswith('```') and text.endswith('```'):
        text = '\n'.join(text.splitlines()[1:-1])
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError('输出必须为 JSON 对象')
    return value
