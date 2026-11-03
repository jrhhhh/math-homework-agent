import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from app import model, settings


class DshBackendTests(unittest.TestCase):
    def test_settings_select_dsh_without_exposing_key(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'MATH_SETTINGS_PATH': folder + '/settings.json'}, clear=True):
            result = settings.save({'backend': 'dsh-cli', 'api_key': 'test-secret', 'dsh_bin': '/test/dsh'})
            self.assertEqual(result['backend'], 'dsh-cli')
            self.assertTrue(result['has_key'])
            self.assertNotIn('test-secret', json.dumps(result))
            self.assertEqual(settings.resolve()['api_key'], 'test-secret')

    def test_isolated_call_disables_tools_and_parses_final(self):
        observed = {}
        def run(command, **kw):
            if '--version' in command:
                return subprocess.CompletedProcess(command, 0, model.DSH_VERSION + '\n', '')
            observed['input'] = kw['input']
            observed['patch'] = Path(command[command.index('--patch') + 1]).read_text()
            observed['env'] = kw['env']
            observed['cwd'] = kw['cwd']
            return subprocess.CompletedProcess(command, 0, json.dumps({'type':'final','text':'{"ok":true}'})+'\n', '')
        with patch('app.model._dsh_binary', return_value='/fake/dsh'), patch('app.model.subprocess.run', side_effect=run):
            result = model._generate_dsh('a prompt', 12, {'api_key':'test-secret', 'model':'deepseek-flash'})
        self.assertEqual(model.parse_json(result['raw']), {'ok': True})
        self.assertEqual(observed['input'], 'a prompt')
        self.assertEqual(observed['env']['DEEPSEEK_API_KEY'], 'test-secret')
        self.assertNotIn('DEEPSEEK_BASE_URL', observed['env'])
        self.assertEqual(Path(observed['env']['DSH_HOME']).parent, Path(observed['cwd']))
        self.assertTrue(all('- id: '+name+'\n  disabled: true\n' in observed['patch'] for name in model.DSH_DISABLED))
        self.assertEqual(result['events'], [])

    def test_unverified_version_and_tool_call_fail_closed(self):
        cfg = {'api_key': 'test-secret'}
        with patch('app.model._dsh_binary', return_value='/fake/dsh'), patch('app.model.subprocess.run', return_value=subprocess.CompletedProcess([],0,'unknown\n','')):
            with self.assertRaises(model.ModelError):
                model._generate_dsh('prompt', 12, cfg)
        events = json.dumps({'type':'tool_call','tool':'bash'})+'\n'+json.dumps({'type':'final','text':'{}'})
        outputs = [subprocess.CompletedProcess([],0,model.DSH_VERSION+'\n',''), subprocess.CompletedProcess([],0,events,'')]
        with patch('app.model._dsh_binary', return_value='/fake/dsh'), patch('app.model.subprocess.run', side_effect=outputs):
            with self.assertRaises(model.ModelError):
                model._generate_dsh('prompt', 12, cfg)


if __name__ == '__main__':
    unittest.main()
