"""Local model-backend settings editable from the workbench.

Precedence: environment variables > saved UI settings > default Codex CLI.
The API key is stored only in the local settings file and is never returned
to the browser.
"""
import json
import os
from pathlib import Path
import threading

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / '.local' / 'model_settings.json'
BACKENDS = {'codex-cli', 'http'}
STYLES = {'chat', 'responses'}
_LOCK = threading.Lock()


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
    elif saved_backend == 'http' and saved_base:
        backend = 'http'
        base_url = saved_base
        source = 'ui'
    else:
        backend = 'codex-cli'
        base_url = ''
        source = 'ui' if saved else 'default'
    model = _text(os.environ.get('MATH_MODEL')) or _text(saved.get('model'))
    style = (_text(os.environ.get('MATH_API_STYLE')).lower()
             or _text(saved.get('style')).lower() or 'chat')
    api_key = _text(os.environ.get('MATH_API_KEY'), 2000) or _text(saved.get('api_key'), 2000)
    codex_bin = (_text(os.environ.get('MATH_CODEX_BIN'))
                 or _text(saved.get('codex_bin')) or 'codex')
    return {
        'backend': backend,
        'base_url': base_url,
        'model': model,
        'style': style,
        'api_key': api_key,
        'codex_bin': codex_bin,
        'source': source,
        'environment_locked': bool(env_base),
    }


def public():
    """Configuration safe to return to the browser (no secret)."""
    config = resolve()
    return {
        'backend': config['backend'],
        'base_url': config['base_url'],
        'model': config['model'],
        'style': config['style'],
        'codex_bin': config['codex_bin'],
        'has_key': bool(config['api_key']),
        'source': config['source'],
        'environment_locked': config['environment_locked'],
    }


def _validate(payload):
    if not isinstance(payload, dict):
        raise ValueError('设置必须为对象。')
    backend = payload.get('backend', 'codex-cli')
    if backend not in BACKENDS:
        raise ValueError('后端只能是 codex-cli 或 http。')
    base_url = _text(payload.get('base_url'))
    model = _text(payload.get('model'), 200)
    style = (_text(payload.get('style'), 20).lower() or 'chat')
    codex_bin = _text(payload.get('codex_bin'))
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
    }


def _with_key(settings, payload):
    with _LOCK:
        existing = _read_file()
    key = _text(existing.get('api_key'), 2000)
    if payload.get('clear_key') is True:
        key = ''
    elif isinstance(payload.get('api_key'), str) and payload['api_key'].strip():
        key = _text(payload['api_key'], 2000)
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
