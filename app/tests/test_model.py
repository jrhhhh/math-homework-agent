import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from app import model


def clean_env(**values):
    env = {key: value for key, value in os.environ.items() if not key.startswith('MATH_')}
    env.update(values)
    return env


class ApiHandler(BaseHTTPRequestHandler):
    status = 200
    payload = {}
    received = []

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        raw = self.rfile.read(length)
        type(self).received.append({
            'path': self.path,
            'body': json.loads(raw.decode('utf-8')),
            'authorization': self.headers.get('Authorization'),
        })
        body = json.dumps(type(self).payload, ensure_ascii=False).encode('utf-8')
        self.send_response(type(self).status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class HttpBackendTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), ApiHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}/v1'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        ApiHandler.status = 200
        ApiHandler.payload = {}
        ApiHandler.received = []
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings_path = Path(self.tmp.name) / 'settings.json'

    def env(self, **values):
        values.setdefault('MATH_SETTINGS_PATH', str(self.settings_path))
        return clean_env(**values)

    def test_backend_selection_prefers_http_when_configured(self):
        with patch.dict(os.environ, self.env(), clear=True), patch('app.model.shutil.which', return_value=None):
            self.assertEqual(model.backend(), 'none')
            self.assertFalse(model.available())
        with patch.dict(os.environ, self.env(MATH_API_BASE=self.base), clear=True):
            self.assertEqual(model.backend(), 'http')
            self.assertTrue(model.available())

    def test_chat_backend_posts_openai_compatible_request(self):
        ApiHandler.payload = {
            'choices': [{'message': {'content': '{"reply":"ok","result":{}}'}}],
            'usage': {'total_tokens': 7},
        }
        with patch.dict(os.environ, self.env(
                MATH_API_BASE=self.base, MATH_API_KEY='secret', MATH_MODEL='m1'), clear=True):
            result = model.generate('题目')
        self.assertEqual(result['backend'], 'http')
        self.assertEqual(result['raw'], '{"reply":"ok","result":{}}')
        self.assertEqual(result['usage'], {'total_tokens': 7})
        self.assertEqual(result['requested_model'], 'm1')
        record = ApiHandler.received[0]
        self.assertEqual(record['path'], '/v1/chat/completions')
        self.assertEqual(record['authorization'], 'Bearer secret')
        self.assertEqual(record['body']['model'], 'm1')
        self.assertEqual(record['body']['messages'], [{'role': 'user', 'content': '题目'}])

    def test_responses_style_reads_output_text(self):
        ApiHandler.payload = {
            'output': [{'type': 'message', 'content': [
                {'type': 'output_text', 'text': '第一段'},
                {'type': 'output_text', 'text': '第二段'},
            ]}],
            'usage': {'input_tokens': 1, 'output_tokens': 2},
        }
        with patch.dict(os.environ, self.env(
                MATH_API_BASE=self.base, MATH_MODEL='m2', MATH_API_STYLE='responses'), clear=True):
            result = model.generate('题目')
        self.assertEqual(result['raw'], '第一段第二段')
        record = ApiHandler.received[0]
        self.assertEqual(record['path'], '/v1/responses')
        self.assertEqual(record['body']['input'], '题目')
        self.assertIsNone(record['authorization'])

    def test_full_endpoint_is_not_duplicated(self):
        ApiHandler.payload = {'choices': [{'message': {'content': 'ok'}}]}
        with patch.dict(os.environ, self.env(
                MATH_API_BASE=self.base + '/chat/completions', MATH_MODEL='m3'), clear=True):
            model.generate('题目')
        self.assertEqual(ApiHandler.received[0]['path'], '/v1/chat/completions')

    def test_authentication_error_is_classified(self):
        ApiHandler.status = 401
        ApiHandler.payload = {'error': {'message': 'invalid key'}}
        with patch.dict(os.environ, self.env(
                MATH_API_BASE=self.base, MATH_API_KEY='bad', MATH_MODEL='m4'), clear=True):
            with self.assertRaises(model.ModelError) as caught:
                model.generate('题目')
        self.assertEqual(caught.exception.diagnostic['category'], 'authentication')
        self.assertIn('API Key', str(caught.exception))

    def test_probe_reports_http_success_and_authentication_failure(self):
        config = {'backend': 'http', 'base_url': self.base, 'model': 'probe-model',
                  'style': 'chat', 'api_key': ''}
        ApiHandler.payload = {'choices': [{'message': {'content': '{"ok": true}'}}]}
        result = model.probe(config)
        self.assertTrue(result['ok'])
        self.assertEqual(result['backend'], 'http')
        ApiHandler.status = 401
        ApiHandler.payload = {'error': {'message': 'bad key'}}
        result = model.probe(config)
        self.assertFalse(result['ok'])
        self.assertEqual(result['diagnostic']['category'], 'authentication')

    def test_missing_model_and_invalid_style_are_configuration_errors(self):
        with patch.dict(os.environ, self.env(MATH_API_BASE=self.base), clear=True):
            with self.assertRaises(model.ModelError) as caught:
                model.generate('题目')
        self.assertEqual(caught.exception.diagnostic['category'], 'configuration')
        self.assertIn('模型名', str(caught.exception))
        with patch.dict(os.environ, self.env(
                MATH_API_BASE=self.base, MATH_MODEL='m5', MATH_API_STYLE='legacy'), clear=True):
            with self.assertRaises(model.ModelError) as caught:
                model.generate('题目')
        self.assertEqual(caught.exception.diagnostic['category'], 'configuration')


if __name__ == '__main__':
    unittest.main()
