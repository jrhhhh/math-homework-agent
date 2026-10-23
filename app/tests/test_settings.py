import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import settings


def clean_env(**values):
    env = {key: value for key, value in os.environ.items() if not key.startswith('MATH_')}
    env.update(values)
    return env


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'model_settings.json'

    def env(self, **values):
        values.setdefault('MATH_SETTINGS_PATH', str(self.path))
        return clean_env(**values)

    def test_save_round_trip_never_exposes_key(self):
        with patch.dict(os.environ, self.env(), clear=True):
            public = settings.save({
                'backend': 'http',
                'base_url': 'https://api.example.com/v1',
                'model': 'demo',
                'style': 'chat',
                'api_key': 'secret-value',
            })
            self.assertTrue(public['has_key'])
            self.assertNotIn('api_key', public)
            self.assertNotIn('secret-value', json.dumps(public))
            effective = settings.resolve()
            self.assertEqual(effective['backend'], 'http')
            self.assertEqual(effective['base_url'], 'https://api.example.com/v1')
            self.assertEqual(effective['model'], 'demo')
            self.assertEqual(effective['api_key'], 'secret-value')
            stored = self.path.read_text(encoding='utf-8')
            self.assertIn('secret-value', stored)

    def test_blank_key_keeps_existing_and_clear_key_removes_it(self):
        with patch.dict(os.environ, self.env(), clear=True):
            settings.save({'backend': 'http', 'base_url': 'https://a.example/v1',
                           'model': 'm', 'api_key': 'first'})
            settings.save({'backend': 'http', 'base_url': 'https://a.example/v1',
                           'model': 'm', 'api_key': ''})
            self.assertEqual(settings.resolve()['api_key'], 'first')
            settings.save({'backend': 'http', 'base_url': 'https://a.example/v1',
                           'model': 'm', 'clear_key': True})
            self.assertEqual(settings.resolve()['api_key'], '')

    def test_environment_overrides_saved_values_and_locks_saving(self):
        with patch.dict(os.environ, self.env(), clear=True):
            settings.save({'backend': 'http', 'base_url': 'https://saved.example/v1',
                           'model': 'saved-model', 'api_key': 'saved-key'})
        with patch.dict(os.environ, self.env(
                MATH_API_BASE='https://env.example/v1', MATH_MODEL='env-model',
                MATH_API_KEY='env-key', MATH_API_STYLE='responses'), clear=True):
            effective = settings.resolve()
            self.assertEqual(effective['source'], 'environment')
            self.assertTrue(effective['environment_locked'])
            self.assertEqual(effective['base_url'], 'https://env.example/v1')
            self.assertEqual(effective['model'], 'env-model')
            self.assertEqual(effective['api_key'], 'env-key')
            self.assertEqual(effective['style'], 'responses')
            with self.assertRaisesRegex(ValueError, '环境变量'):
                settings.save({'backend': 'http', 'base_url': 'https://new.example/v1',
                               'model': 'new'})

    def test_switching_to_codex_clears_stored_key(self):
        with patch.dict(os.environ, self.env(), clear=True):
            settings.save({'backend': 'http', 'base_url': 'https://a.example/v1',
                           'model': 'm', 'api_key': 'secret'})
            public = settings.save({'backend': 'codex-cli', 'codex_bin': '/opt/codex'})
            self.assertFalse(public['has_key'])
            self.assertEqual(settings.resolve()['api_key'], '')
            self.assertEqual(settings.resolve()['codex_bin'], '/opt/codex')

    def test_validation_rejects_incomplete_http_settings(self):
        with patch.dict(os.environ, self.env(), clear=True):
            for payload, message in [
                ({'backend': 'http', 'model': 'm'}, '接口地址'),
                ({'backend': 'http', 'base_url': 'ftp://x', 'model': 'm'}, 'http'),
                ({'backend': 'http', 'base_url': 'https://x/v1'}, '模型名'),
                ({'backend': 'other'}, '后端'),
                ({'backend': 'codex-cli', 'style': 'legacy'}, '接口风格'),
            ]:
                with self.subTest(payload=payload):
                    with self.assertRaisesRegex(ValueError, message):
                        settings.save(payload)

    def test_candidate_does_not_write_file(self):
        with patch.dict(os.environ, self.env(), clear=True):
            config = settings.candidate({'backend': 'http', 'base_url': 'https://a.example/v1',
                                         'model': 'm', 'api_key': 'candidate-key'})
            self.assertEqual(config['api_key'], 'candidate-key')
            self.assertFalse(self.path.exists())
            self.assertEqual(settings.resolve()['backend'], 'codex-cli')

    def test_default_is_codex_and_environment_model_overrides_ui_model(self):
        with patch.dict(os.environ, self.env(), clear=True):
            self.assertEqual(settings.resolve()['backend'], 'codex-cli')
            self.assertEqual(settings.resolve()['source'], 'default')
            settings.save({'backend': 'codex-cli', 'model': 'ui-model'})
        with patch.dict(os.environ, self.env(MATH_MODEL='env-model'), clear=True):
            self.assertEqual(settings.resolve()['model'], 'env-model')


if __name__ == '__main__':
    unittest.main()
