"""Local model-backend settings editable from the workbench.

Precedence: environment variables > saved UI settings > default Codex CLI.
The API key is stored only in the local settings file and is never returned
to the browser.
"""
import json
import os
from pathlib import Path
import shutil
import threading
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / '.local' / 'model_settings.json'
BACKENDS = {'codex-cli', 'http', 'dsh-cli'}
STYLES = {'chat', 'responses'}
_LOCK = threading.Lock()

# Ready-made choices for the first-run wizard. They only fill the same
# technical fields the advanced form already uses; the key is still stored
# locally and never returned to the browser.
PRESETS = (
    {
        'id': 'deepseek',
        'label': 'DeepSeek',
        'description': '国内访问方便，适合日常练习。',
        'backend': 'http',
        'base_url': 'https://api.deepseek.com/v1',
        'style': 'chat',
        'model': 'deepseek-flash',
        'models': ['deepseek-flash', 'deepseek-chat', 'deepseek-reasoner'],
        'requires_key': True,
    },
    {
        'id': 'zhipu',
        'label': '智谱 GLM',
        'description': '国内可用，有免费额度。',
        'backend': 'http',
        'base_url': 'https://open.bigmodel.cn/api/paas/v4',
        'style': 'chat',
        'model': 'glm-4-flash',
        'models': ['glm-4-flash', 'glm-4-air', 'glm-4-plus'],
        'requires_key': True,
    },
    {
        'id': 'openai',
        'label': 'OpenAI',
        'description': '需要可访问的国际网络。',
        'backend': 'http',
        'base_url': 'https://api.openai.com/v1',
        'style': 'chat',
        'model': 'gpt-4o-mini',
        'models': ['gpt-4o-mini', 'gpt-4o'],
        'requires_key': True,
    },
    {
        'id': 'ollama',
        'label': '本机 Ollama',
        'description': '免费离线，需先安装并下载模型。',
        'backend': 'http',
        'base_url': 'http://127.0.0.1:11434/v1',
        'style': 'chat',
        'model': 'qwen2.5:7b',
        'models': ['qwen2.5:7b', 'qwen2.5:14b', 'deepseek-r1:7b'],
        'requires_key': False,
    },
    {
        'id': 'custom',
        'label': '学校 / 其他接口',
        'description': '填写老师提供的地址和模型名。',
        'backend': 'http',
        'base_url': '',
        'style': 'chat',
        'model': '',
        'models': [],
        'requires_key': True,
    },
    {
        'id': 'codex-cli',
        'label': '本机 Codex CLI',
        'description': '已安装并登录 Codex 时使用。',
        'backend': 'codex-cli',
        'base_url': '',
        'style': 'chat',
        'model': '',
        'models': [],
        'requires_key': False,
    },
    {
        'id': 'dsh-cli',
        'label': 'DeepSeek Harness',
        'description': '已安装 DeepSeek Harness CLI 时使用。',
        'backend': 'dsh-cli',
        'base_url': '',
        'style': 'chat',
        'model': '',
        'models': [],
        'requires_key': True,
    },
)
PRESET_BY_ID = {preset['id']: preset for preset in PRESETS}


def settings_path():
    return Path(os.environ.get('MATH_SETTINGS_PATH', str(DEFAULT_PATH)))


def _text(value, limit=500):
    return value.strip()[:limit] if isinstance(value, str) else ''


def _read_file():
    try:
        data = json.loads(settings_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_file(data):
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    # Create with owner-only permissions before writing the secret.
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def resolve():
    """Effective configuration after applying environment overrides."""
    with _LOCK:
        saved = _read_file()
    env_base = _text(os.environ.get('MATH_API_BASE'))
    saved_backend = saved.get('backend') if saved.get('backend') in BACKENDS else 'codex-cli'
    saved_base = _text(saved.get('base_url'))
    if env_base:
        backend = 'http'
        base_url = env_base
        source = 'environment'
    elif saved_backend == 'http':
        backend = 'http'
        base_url = saved_base
        source = 'ui'
    else:
        backend = saved_backend
        base_url = ''
        source = 'ui' if saved else 'default'
    model = _text(os.environ.get('MATH_MODEL')) or _text(saved.get('model'))
    style = (_text(os.environ.get('MATH_API_STYLE')).lower()
             or _text(saved.get('style')).lower() or 'chat')
    api_key = _text(os.environ.get('MATH_API_KEY'), 2000) or _text(saved.get('api_key'), 2000)
    codex_bin = (_text(os.environ.get('MATH_CODEX_BIN'))
                 or _text(saved.get('codex_bin')) or 'codex')
    dsh_bin = _text(os.environ.get('MATH_DSH_BIN')) or _text(saved.get('dsh_bin')) or 'dsh'
    saved_provider = _text(saved.get('provider'), 40)
    if env_base:
        provider = 'custom'
    elif saved_provider in PRESET_BY_ID and PRESET_BY_ID[saved_provider]['backend'] == backend:
        provider = saved_provider
    else:
        provider = backend if backend in ('codex-cli', 'dsh-cli') else 'custom'
    return {
        'backend': backend,
        'dsh_bin': dsh_bin,
        'base_url': base_url,
        'model': model,
        'style': style,
        'api_key': api_key,
        'codex_bin': codex_bin,
        'provider': provider,
        'source': source,
        'environment_locked': bool(env_base),
    }


def presets():
    """Public preset list used by the first-run wizard."""
    return [dict(preset) for preset in PRESETS]


def _is_local_base(base):
    try:
        host = (urllib.parse.urlparse(base).hostname or '').lower()
    except ValueError:
        return False
    return host in {'127.0.0.1', 'localhost', '::1', '0.0.0.0'}


def _setup(required, backend, provider, reason, message):
    return {
        'required': required,
        'configured': not required,
        'backend': backend,
        'provider': provider,
        'reason': reason,
        'message': message,
    }


def setup_status():
    """Actionable, browser-safe answer to 'can this workbench call a model?'.

    This checks only whether the required fields and executable are present;
    reachability and key validity still need the explicit connection test.
    """
    config = resolve()
    backend = config['backend']
    provider = config['provider']
    if config['environment_locked']:
        return _setup(False, backend, provider, 'environment',
                      '模型由环境变量统一配置，无需在网页修改。')
    if backend == 'http':
        if not config['base_url']:
            return _setup(True, backend, provider, 'base_url_missing',
                          '还没有填写接口地址。请选择服务商，或填写老师提供的地址。')
        if not config['model']:
            return _setup(True, backend, provider, 'model_missing',
                          '还没有填写模型名。请选择服务商，或填写老师提供的模型名。')
        preset = PRESET_BY_ID.get(provider)
        key_required = True if preset is None else preset['requires_key']
        if key_required and not config['api_key'] and not _is_local_base(config['base_url']):
            return _setup(True, backend, provider, 'key_missing',
                          '还没有填写 API Key。它只保存在这台电脑上。')
        return _setup(False, backend, provider, 'ready', '模型服务已配置。')
    if backend == 'codex-cli':
        if not shutil.which(config['codex_bin'] or 'codex'):
            if config['source'] == 'default':
                return _setup(True, backend, provider, 'not_configured',
                              '还没有配置模型服务。请选择服务商并填写 API Key。')
            return _setup(True, backend, provider, 'binary_missing',
                          '没有找到 Codex CLI。可安装后重启，或在高级设置中改用 HTTP 接口。')
        return _setup(False, backend, provider, 'ready', '已找到本机 Codex CLI。')
    if backend == 'dsh-cli':
        if not shutil.which(config['dsh_bin'] or 'dsh'):
            return _setup(True, backend, provider, 'binary_missing',
                          '没有找到 DeepSeek Harness CLI。可安装后重启，或在高级设置中改用 HTTP 接口。')
        return _setup(False, backend, provider, 'ready', '已找到 DeepSeek Harness。')
    return _setup(True, backend, provider, 'backend_missing', '请选择模型服务。')


def public():
    """Configuration safe to return to the browser (no secret)."""
    config = resolve()
    return {
        'backend': config['backend'],
        'dsh_bin': config['dsh_bin'],
        'base_url': config['base_url'],
        'model': config['model'],
        'style': config['style'],
        'codex_bin': config['codex_bin'],
        'provider': config['provider'],
        'has_key': bool(config['api_key']),
        'source': config['source'],
        'environment_locked': config['environment_locked'],
    }


def _validate(payload):
    if not isinstance(payload, dict):
        raise ValueError('设置必须为对象。')
    backend = payload.get('backend', 'codex-cli')
    if backend not in BACKENDS:
        raise ValueError('后端只能是 codex-cli、dsh-cli 或 http。')
    base_url = _text(payload.get('base_url'))
    model = _text(payload.get('model'), 200)
    style = _text(payload.get('style'), 20).lower()
    codex_bin = _text(payload.get('codex_bin'))
    dsh_bin = _text(payload.get('dsh_bin'))
    provider = _text(payload.get('provider'), 40)
    if provider not in PRESET_BY_ID:
        provider = backend if backend in ('codex-cli', 'dsh-cli') else 'custom'
    preset = PRESET_BY_ID.get(provider)
    if preset and preset['backend'] == backend and backend == 'http':
        base_url = base_url or preset['base_url']
        model = model or preset['model']
        style = style or preset['style']
    elif preset and preset['backend'] != backend:
        provider = backend if backend in ('codex-cli', 'dsh-cli') else 'custom'
    style = style or 'chat'
    if style not in STYLES:
        raise ValueError('接口风格只能是 chat 或 responses。')
    if backend == 'http':
        if not base_url:
            raise ValueError('HTTP 后端需要填写接口地址。')
        if not (base_url.startswith('http://') or base_url.startswith('https://')):
            raise ValueError('接口地址必须以 http:// 或 https:// 开头。')
        if not model:
            raise ValueError('HTTP 后端需要填写模型名。')
    return {
        'backend': backend,
        'base_url': base_url if backend == 'http' else '',
        'model': model,
        'style': style,
        'codex_bin': codex_bin,
        'dsh_bin': dsh_bin,
        'provider': provider,
    }


def _with_key(settings, payload):
    with _LOCK:
        existing = _read_file()
    key = _text(existing.get('api_key'), 2000)
    previous_backend = existing.get('backend') or 'codex-cli'
    previous_base = _text(existing.get('base_url'))
    supplied = payload.get('api_key')
    if payload.get('clear_key') is True:
        key = ''
    elif isinstance(supplied, str) and supplied.strip():
        key = _text(supplied, 2000)
    elif (settings['backend'] != previous_backend
          or (settings['backend'] == 'http' and settings.get('base_url') != previous_base)):
        # Never carry a stored credential to a different backend or endpoint.
        key = ''
    if settings['backend'] == 'codex-cli':
        key = ''
    settings['api_key'] = key
    return settings


def save(payload):
    if resolve()['environment_locked']:
        raise ValueError('当前由 MATH_API_BASE 环境变量覆盖，请先移除该变量再在网页中修改。')
    settings = _with_key(_validate(payload), payload)
    with _LOCK:
        _write_file(settings)
    return public()


def candidate(payload):
    """Build a configuration for testing without saving it."""
    if resolve()['environment_locked']:
        return resolve()
    return _with_key(_validate(payload), payload)
