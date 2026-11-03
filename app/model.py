"""Inference backends for one mathematical JSON response.

Selectable backends:

- ``http``: a direct OpenAI-compatible endpoint.
- ``codex-cli``: the user's installed, authenticated Codex CLI.
- ``dsh-cli``: an isolated DeepSeek Harness headless invocation.

The effective choice comes from :mod:`app.settings`, where environment
variables override values saved in the workbench UI. All backends return the
same shape, so the router and gates do not care which one produced the answer.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

from . import settings

MAX_HTTP_RESPONSE_BYTES = 2_000_000


class ModelError(RuntimeError):
    def __init__(self, message, diagnostic=None):
        super().__init__(message)
        self.diagnostic = diagnostic or {}


def backend():
    """Which backend the effective configuration selects."""
    config = settings.resolve()
    if config['backend'] == 'http' and config['base_url']:
        return 'http'
    if config['backend'] == 'dsh-cli':
        return 'dsh-cli' if _dsh_binary(config) else 'none'
    if shutil.which(config.get('codex_bin') or 'codex'):
        return 'codex-cli'
    return 'none'


def available():
    return backend() != 'none'


def generate(prompt, timeout=240):
    config = settings.resolve()
    if config['backend'] == 'http' and config['base_url']:
        return _generate_http(prompt, timeout, config)
    if config['backend'] == 'dsh-cli':
        return _generate_dsh(prompt, timeout, config)
    return _generate_codex(prompt, timeout, config)


def probe(config):
    """Lightweight connectivity check used by the settings panel."""
    if config['backend'] == 'http':
        try:
            result = _generate_http('只输出 {"ok": true}，不要输出其他内容。', 30, config)
            return {'ok': True, 'backend': 'http', 'message': '接口可用。',
                    'usage': result.get('usage')}
        except ModelError as exc:
            return {'ok': False, 'backend': 'http', 'message': str(exc),
                    'diagnostic': exc.diagnostic}
    if config['backend'] == 'dsh-cli':
        try:
            result = _generate_dsh('只输出 JSON 对象 {\"ok\":true}。', 90, config)
            if parse_json(result['raw']).get('ok') is not True:
                raise ModelError('DeepSeek Harness 返回的测试内容不符合预期。')
            return {'ok': True, 'backend': 'dsh-cli', 'message': 'DeepSeek Harness 连接成功。'}
        except (ModelError, ValueError):
            return {'ok': False, 'backend': 'dsh-cli', 'message': 'DeepSeek Harness 连接失败，请检查密钥、版本和网络。'}
    binary = shutil.which(config.get('codex_bin') or 'codex')
    if not binary:
        return {'ok': False, 'backend': 'codex-cli', 'message': '未找到 Codex CLI。'}
    try:
        result = subprocess.run([binary, 'login', 'status'], capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return {'ok': False, 'backend': 'codex-cli', 'message': '无法运行 Codex CLI。'}
    if result.returncode == 0:
        return {'ok': True, 'backend': 'codex-cli', 'message': 'Codex CLI 已就绪。'}
    return {'ok': False, 'backend': 'codex-cli', 'message': 'Codex CLI 未登录或不可用。'}


def _generate_codex(prompt, timeout, config):
    binary = shutil.which(config.get('codex_bin') or 'codex')
    if not binary:
        raise ModelError('未找到 Codex CLI，请安装并登录，或在设置中改用 HTTP 后端。')
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='math-inference-') as folder:
        output = Path(folder) / 'answer.txt'
        command = [binary, 'exec', '--ephemeral', '--skip-git-repo-check',
                   '--sandbox', 'read-only', '--json', '--color', 'never',
                   '-c', 'features.shell_tool=false', '-c', 'features.multi_agent=false',
                   '-C', folder, '-o', str(output), '-']
        model_name = config.get('model') or ''
        if model_name:
            command[2:2] = ['--model', model_name]
        try:
            result = subprocess.run(command, input=prompt, text=True, capture_output=True,
                                    encoding='utf-8', errors='replace', timeout=timeout)
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
            messages = ' '.join(str(e.get('message', '')) + ' ' + str(e.get('error', ''))
                                for e in events).lower()
            category = ('rate_limit' if any(t in messages for t in ('rate limit', 'usage limit', 'quota')) else
                        'authentication' if any(t in messages for t in ('unauthorized', 'authentication', 'login', 'token expired')) else
                        'transport' if any(t in messages for t in ('network', 'connection', 'stream', 'timeout')) else 'backend_failure')
            raise ModelError('模型调用失败，请检查 Codex 登录状态与网络。',
                             {'category': category, 'backend': 'codex-cli',
                              'exit_code': result.returncode,
                              'elapsed_seconds': round(time.monotonic() - started, 3)})
        raw = output.read_text(encoding='utf-8').strip()
        usage = [e.get('usage') for e in events if e.get('type') == 'turn.completed']
        return {'raw': raw, 'elapsed_seconds': round(time.monotonic() - started, 3),
                'usage': usage, 'events': events, 'backend': 'codex-cli',
                'requested_model': model_name or 'user-config-default'}


# This adapter is pinned to the tested DSH composition. Unknown versions fail
# closed until their tool catalog and isolation behavior have been verified.
DSH_VERSION = '0.2.1-rc.5'
DSH_DISABLED = ('tool-plugin-manager', 'tool-working-directory', 'tool-bash',
                'tool-pwsh', 'tool-jobs', 'tool-fs', 'tool-fs-search',
                'tool-skill', 'tool-subagent-control', 'tool-subagent-list-agents',
                'tool-subagent', 'tool-subagent-fork', 'tool-workflow',
                'tool-todo', 'tool-goal', 'tool-web', 'plan-mode')
DSH_MAC_BIN = '/Applications/DeepSeek Harness.app/Contents/Resources/runtime/cli/bin/dsh'


def _dsh_binary(config):
    name = config.get('dsh_bin') or 'dsh'
    return shutil.which(name) or (DSH_MAC_BIN if name == 'dsh' and Path(DSH_MAC_BIN).is_file() else None)


def _generate_dsh(prompt, timeout, config):
    binary = _dsh_binary(config)
    if not binary:
        raise ModelError('未找到 DeepSeek Harness CLI，请安装或在设置中填写路径。',
                         {'category': 'configuration', 'backend': 'dsh-cli'})
    key = config.get('api_key') or os.environ.get('DEEPSEEK_API_KEY', '')
    if not key:
        raise ModelError('DeepSeek Harness 工作台后端需要 API Key；桌面账号登录不等于 API 配置。',
                         {'category': 'authentication', 'backend': 'dsh-cli'})
    started = time.monotonic()
    try:
        check = subprocess.run([binary, '--version'], capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ModelError('无法启动 DeepSeek Harness CLI。', {'category': 'configuration', 'backend': 'dsh-cli'}) from exc
    if check.returncode or check.stdout.strip() != DSH_VERSION:
        raise ModelError('DeepSeek Harness 版本未经工作台验证；当前适配版本为 ' + DSH_VERSION + '。',
                         {'category': 'configuration', 'backend': 'dsh-cli'})
    model_name = config.get('model') or 'deepseek-flash'
    with tempfile.TemporaryDirectory(prefix='math-dsh-') as folder:
        root = Path(folder)
        patch = root / 'readonly.patch.yml'
        patch.write_text(''.join('- id: ' + name + '\n  disabled: true\n' for name in DSH_DISABLED)
                         + '- id: agent-default-model\n  config:\n    provider: deepseek-official\n    model: '
                         + json.dumps(model_name) + '\n', encoding='utf-8')
        env = os.environ.copy()
        env.update({'DSH_HOME': str(root / 'home'), 'DEEPSEEK_API_KEY': key,
                    'DSH_TELEMETRY_MODE': 'DISABLED'})
        # Do not silently send a workbench key to an inherited custom endpoint.
        env.pop('DEEPSEEK_BASE_URL', None)
        try:
            result = subprocess.run([binary, '--patch', str(patch), '--profile', 'headless', '--json', '-'],
                                    input=prompt, cwd=folder, env=env, capture_output=True, text=True,
                                    encoding='utf-8', errors='replace', timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise ModelError('DeepSeek Harness 调用超时；本次没有生成可交付结果。',
                             {'category': 'transport', 'backend': 'dsh-cli'}) from exc
        except OSError as exc:
            raise ModelError('无法启动 DeepSeek Harness CLI。',
                             {'category': 'configuration', 'backend': 'dsh-cli'}) from exc
        events = []
        for line in result.stdout.splitlines():
            try:
                event = json.loads(line)
                if isinstance(event, dict):
                    events.append(event)
            except ValueError:
                continue
        if (result.returncode or any(e.get('type') == 'tool_call' for e in events)
                or any(e.get('type') == 'status' and e.get('phase') == 'turn_end'
                       and isinstance(e.get('reason'), dict) and e['reason'].get('kind') != 'completed'
                       for e in events)):
            raise ModelError('DeepSeek Harness 调用失败，请检查密钥、网络和运行配置。',
                             {'category': 'backend_failure', 'backend': 'dsh-cli',
                              'exit_code': result.returncode, 'elapsed_seconds': round(time.monotonic()-started, 3)})
        finals = [e.get('text') for e in events if e.get('type') == 'final' and isinstance(e.get('text'), str)]
        if not finals or not finals[-1].strip():
            raise ModelError('DeepSeek Harness 未返回文本。', {'category': 'backend_failure', 'backend': 'dsh-cli'})
        return {'raw': finals[-1].strip(), 'elapsed_seconds': round(time.monotonic()-started, 3),
                'usage': None, 'events': [], 'backend': 'dsh-cli', 'requested_model': model_name}


def _http_style(config):
    style = (config.get('style') or 'chat').strip().lower()
    if style not in ('chat', 'responses'):
        raise ModelError('接口风格只能是 chat 或 responses。',
                         {'category': 'configuration', 'backend': 'http'})
    return style


def _http_model(config):
    model_name = (config.get('model') or '').strip()
    if not model_name:
        raise ModelError('HTTP 后端必须在设置中填写模型名。',
                         {'category': 'configuration', 'backend': 'http'})
    return model_name


def _http_endpoint(base, style):
    base = base.rstrip('/')
    if base.endswith('/chat/completions') or base.endswith('/responses'):
        return base
    return base + ('/responses' if style == 'responses' else '/chat/completions')


def _http_payload(prompt, style, model_name):
    if style == 'responses':
        return {'model': model_name, 'input': prompt}
    return {'model': model_name, 'messages': [{'role': 'user', 'content': prompt}]}


def _http_text(data, style):
    if not isinstance(data, dict):
        return ''
    if style == 'responses':
        text = data.get('output_text')
        if isinstance(text, str) and text.strip():
            return text
        chunks = []
        for item in data.get('output') or []:
            if not isinstance(item, dict):
                continue
            for part in item.get('content') or []:
                if isinstance(part, dict) and part.get('type') in ('output_text', 'text'):
                    if isinstance(part.get('text'), str):
                        chunks.append(part['text'])
        return ''.join(chunks)
    choices = data.get('choices') or []
    if not choices or not isinstance(choices[0], dict):
        return ''
    content = (choices[0].get('message') or {}).get('content')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(part.get('text', '') for part in content
                       if isinstance(part, dict) and isinstance(part.get('text'), str))
    return ''


def _http_category(status):
    if status == 429:
        return 'rate_limit'
    if status in (401, 403):
        return 'authentication'
    if status >= 500:
        return 'transport'
    return 'backend_failure'


def _http_message(category):
    return {
        'rate_limit': '模型服务限流或额度不足，请稍后重试。',
        'authentication': '模型服务鉴权失败，请检查 API Key。',
        'transport': '模型服务暂时不可用，请检查网络或服务状态。',
        'configuration': '模型接口配置不完整，请检查设置。',
    }.get(category, '模型调用失败，请检查接口配置与网络。')


def _generate_http(prompt, timeout, config):
    base = (config.get('base_url') or '').strip()
    if not base:
        raise ModelError('HTTP 后端尚未填写接口地址。',
                         {'category': 'configuration', 'backend': 'http'})
    style = _http_style(config)
    model_name = _http_model(config)
    url = _http_endpoint(base, style)
    body = json.dumps(_http_payload(prompt, style, model_name), ensure_ascii=False).encode('utf-8')
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    key = (config.get('api_key') or '').strip()
    if key:
        headers['Authorization'] = 'Bearer ' + key
    request = urllib.request.Request(url, data=body, headers=headers, method='POST')
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw_bytes = response.read(MAX_HTTP_RESPONSE_BYTES)
    except urllib.error.HTTPError as exc:
        category = _http_category(exc.code)
        raise ModelError(_http_message(category),
                         {'category': category, 'backend': 'http', 'status': exc.code,
                          'elapsed_seconds': round(time.monotonic() - started, 3)}) from exc
    except TimeoutError as exc:
        raise ModelError('模型调用超时；本次没有生成可交付结果。',
                         {'category': 'transport', 'backend': 'http',
                          'elapsed_seconds': round(time.monotonic() - started, 3)}) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise ModelError('模型服务连接失败，请检查网络与接口地址。',
                         {'category': 'transport', 'backend': 'http',
                          'elapsed_seconds': round(time.monotonic() - started, 3)}) from exc
    try:
        data = json.loads(raw_bytes.decode('utf-8'))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ModelError('模型服务返回了无法解析的响应。',
                         {'category': 'backend_failure', 'backend': 'http',
                          'elapsed_seconds': round(time.monotonic() - started, 3)}) from exc
    raw = _http_text(data, style).strip()
    if not raw:
        raise ModelError('模型服务没有返回文本内容。',
                         {'category': 'backend_failure', 'backend': 'http',
                          'elapsed_seconds': round(time.monotonic() - started, 3)})
    return {'raw': raw, 'elapsed_seconds': round(time.monotonic() - started, 3),
            'usage': data.get('usage'), 'events': [], 'backend': 'http',
            'requested_model': model_name}


def parse_json(raw):
    text = raw.strip()
    if text.startswith('```') and text.endswith('```'):
        text = '\n'.join(text.splitlines()[1:-1])
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError('输出必须为 JSON 对象')
    return value
