from http.server import ThreadingHTTPServer
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from app.server import Application,Store,handler_for


class HttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        def runner(data):
            return {'status':'ready','output':{'reply':'实际测试后端','result':None},'attempts':[]}
        cls.app=Application(Store(Path(cls.tmp.name)/'data.db'),runner=runner)
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(cls.app))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.app.close();cls.tmp.cleanup()

    def delete(self,path):
        request=Request(self.base+path,method='DELETE')
        try:
            with urlopen(request,timeout=5) as response:return response.status,json.load(response)
        except HTTPError as exc:return exc.code,json.load(exc)

    def request(self,path,data=None,origin=None):
        headers={}
        if data is not None:headers['Content-Type']='application/json'
        if origin:headers['Origin']=origin
        request=Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            with urlopen(request,timeout=5) as response:return response.status,json.load(response)
        except HTTPError as exc:return exc.code,json.load(exc)

    def test_async_submission_reaches_result_and_is_queryable(self):
        status,session=self.request('/api/sessions',{})
        self.assertEqual(status,201)
        status,record=self.request(f'/api/sessions/{session["id"]}/submissions',{'problem':'x+1=2','solution':'x=1'})
        self.assertEqual(status,202)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            _,payload=self.request('/api/submissions/'+record['id'])
            if payload['state']=='ready':break
            time.sleep(.02)
        self.assertEqual(payload['state'],'ready')
        self.assertTrue(payload['is_current'])
        self.assertEqual(payload['data']['solution'],'x=1')

    def test_cross_origin_model_call_rejected(self):
        self.assertEqual(self.request('/api/sessions',{},origin='https://example.com')[0],403)

    def test_teacher_workspace_exposes_lesson_history_and_validates_outline(self):
        self.assertEqual(self.request('/api/lessons')[0],200)
        status,body=self.request('/api/lessons/outline',{'topic':'','grade':'高一'})
        self.assertEqual(status,400)
        self.assertIn('课题',body['error'])

    def test_teacher_task_publishes_and_student_session_returns_evidence(self):
        status,task=self.request('/api/teaching',{'title':'逆运算','items':[{'problem':'解 x+1=2。','objective':'逆运算'}]})
        self.assertEqual(status,201)
        self.assertEqual(self.request('/api/teaching/'+task['id'])[0],200)
        _,opened=self.request('/api/teaching/'+task['id']+'/open/'+task['items'][0]['id'],{})
        _,submission=self.request('/api/sessions/'+opened['session_id']+'/submissions',{'problem':opened['problem'],'solution':'x=1','mode':'check'})
        _,report=self.request('/api/teaching/'+task['id']+'/evidence')
        self.assertEqual(report['items'][0]['submission_id'],submission['id'])
        self.assertEqual(sum(report['counts'].values()),1)
        self.assertEqual(self.request('/api/teaching/missing/evidence')[0],404)
        self.assertEqual(self.request('/api/teaching/design',{},origin='https://example.com')[0],403)

    def test_stale_teaching_evidence_is_rejected_before_lesson_model_call(self):
        _,task=self.request('/api/teaching',{'title':'逆运算','items':[{'problem':'解 x+1=2。','objective':'逆运算'}]})
        _,report=self.request('/api/teaching/'+task['id']+'/evidence')
        source={'assignment_id':task['id'],'evidence_version':report['evidence_version']}
        self.app.teaching.require_current(source)
        _,opened=self.request('/api/teaching/'+task['id']+'/open/'+task['items'][0]['id'],{})
        self.request('/api/sessions/'+opened['session_id']+'/submissions',{'problem':opened['problem'],'solution':'x=1','mode':'check'})
        status,body=self.request('/api/lessons/outline',{'teaching_source':source})
        self.assertEqual(status,400)
        self.assertIn('过期',body['error'])
        self.app.store.create_lesson('b'*32,'测试',{'teaching_source':source},'大纲',[],[])
        for action in ('source','render'):
            status,body=self.request('/api/lessons/'+'b'*32+'/'+action,{})
            self.assertEqual(status,400)
            self.assertIn('过期',body['error'])

    def test_invalid_types_return_json_400(self):
        _,session=self.request('/api/sessions',{})
        for mode in ([],{},23,None):
            status,body=self.request(f'/api/sessions/{session["id"]}/submissions',{'problem':'x+1=2','mode':mode})
            self.assertEqual(status,400)
            self.assertIn('error',body)

    def test_unknown_session_and_oversized_text_rejected(self):
        self.assertEqual(self.request('/api/sessions/missing/submissions',{'problem':'x=1'})[0],400)
        _,session=self.request('/api/sessions',{})
        self.assertEqual(self.request(f'/api/sessions/{session["id"]}/submissions',{'problem':'x'*20001})[0],400)

    def test_restart_marks_unowned_running_handle_interrupted(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'restart.db');sid=store.create_session()
            rid=store.submit(sid,{'problem':'x=1','mode':'solve'})
            store.update(rid,'running')
            app=Application(store)
            self.assertEqual(store.get(rid)['state'],'interrupted')
            app.close()

    def test_second_owner_cannot_invalidate_live_tasks(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'live.db');app=Application(store)
            sid=store.create_session();rid=store.submit(sid,{'problem':'x=1','mode':'solve'})
            store.update(rid,'running')
            try:
                with self.assertRaises(RuntimeError):Application(store)
                self.assertEqual(store.get(rid)['state'],'running')
            finally:app.close()

    def test_attachments_are_stored_in_any_mode_and_served(self):
        png = b'\x89PNG\r\n\x1a\n' + b'0' * 24
        pdf = b'%PDF-1.4\n' + b'0' * 24
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'MATH_UPLOAD_DIR': folder}, clear=True):
                _, session = self.request('/api/sessions', {})
                status, record = self.request(
                    f'/api/sessions/{session["id"]}/submissions',
                    {'problem': '解 x+1=2', 'solution': 'x=1', 'mode': 'check',
                     'attachments': [
                         {'name': 'work.png', 'base64': base64.b64encode(png).decode()},
                         {'name': 'problem.pdf', 'base64': base64.b64encode(pdf).decode()},
                     ]})
                self.assertEqual(status, 202)
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    _, payload = self.request('/api/submissions/' + record['id'])
                    if payload['state'] != 'queued':
                        break
                    time.sleep(.02)
                attachments = payload['data']['attachments']
                self.assertEqual([item['ext'] for item in attachments], ['.png', '.pdf'])
                self.assertNotIn('name', attachments[0])
                self.assertNotIn('base64', json.dumps(payload))
                with urlopen(self.base + '/api/uploads/' + attachments[0]['sha256'] + '.png',
                             timeout=5) as response:
                    self.assertEqual(response.headers.get_content_type(), 'image/png')
                    self.assertEqual(response.read(), png)
                with urlopen(self.base + '/api/uploads/' + attachments[1]['sha256'] + '.pdf',
                             timeout=5) as response:
                    self.assertEqual(response.headers.get_content_type(), 'application/pdf')
                    self.assertEqual(response.read(), pdf)

    def test_attachment_without_text_is_rejected(self):
        png = b'\x89PNG\r\n\x1a\n' + b'0' * 24
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'MATH_UPLOAD_DIR': folder}, clear=True):
                _, session = self.request('/api/sessions', {})
                status, body = self.request(
                    f'/api/sessions/{session["id"]}/submissions',
                    {'mode': 'draft', 'attachments': [
                        {'name': 'draft.png',
                         'base64': base64.b64encode(png).decode()}]})
                self.assertEqual(status, 400)
                self.assertIn('草稿', body['error'])

    def test_attachment_text_extraction_endpoint(self):
        text = '第一行\n第二行'
        status, body = self.request('/api/attachments/extract', {
            'name': 'lesson.txt', 'base64': base64.b64encode(text.encode()).decode()})
        self.assertEqual(status, 200)
        self.assertEqual(body['text'], text)
        status, body = self.request('/api/attachments/extract', {
            'name': 'draft.png', 'base64': base64.b64encode(b'\x89PNG\r\n\x1a\n').decode()})
        self.assertEqual(status, 400)
        self.assertIn('文字识别', body['error'])

    def test_session_archive_and_delete(self):
        _, session = self.request('/api/sessions', {})
        self.request(f'/api/sessions/{session["id"]}/submissions',
                     {'problem': '解 x+1=2', 'solution': 'x=1'})
        status, body = self.request(f'/api/sessions/{session["id"]}/archive',
                                    {'archived': True})
        self.assertEqual(status, 200)
        self.assertTrue(body['archived'])
        _, rows = self.request('/api/sessions')
        self.assertEqual(next(row for row in rows if row['id'] == session['id'])['archived'], 1)
        status, body = self.request(f'/api/sessions/{session["id"]}/archive',
                                    {'archived': False})
        self.assertFalse(body['archived'])
        status, body = self.delete('/api/sessions/' + session['id'])
        self.assertEqual(status, 200)
        self.assertTrue(body['deleted'])
        _, rows = self.request('/api/sessions')
        self.assertFalse(any(row['id'] == session['id'] for row in rows))
        self.assertEqual(self.delete('/api/sessions/' + session['id'])[0], 400)

    def test_delete_session_removes_unreferenced_attachment_files(self):
        png = b'\x89PNG\r\n\x1a\n' + b'unique-delete-' * 2
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'MATH_UPLOAD_DIR': folder}, clear=True):
                _, session = self.request('/api/sessions', {})
                _, record = self.request(
                    f'/api/sessions/{session["id"]}/submissions',
                    {'problem': '解 x+1=2', 'solution': 'x=1',
                     'attachments': [{'name': 'work.png',
                                      'base64': base64.b64encode(png).decode()}]})
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    _, payload = self.request('/api/submissions/' + record['id'])
                    if payload['state'] != 'queued':
                        break
                    time.sleep(.02)
                meta = payload['data']['attachments'][0]
                path = Path(folder) / (meta['sha256'] + meta['ext'])
                self.assertTrue(path.exists())
                self.delete('/api/sessions/' + session['id'])
                self.assertFalse(path.exists())

    def test_bound_teaching_session_cannot_be_deleted_but_can_be_archived(self):
        _, task = self.request('/api/teaching', {
            'title': '逆运算', 'items': [{'problem': '解 x+1=2。', 'objective': '逆运算'}]})
        _, opened = self.request(
            f'/api/teaching/{task["id"]}/open/{task["items"][0]["id"]}', {})
        sid = opened['session_id']
        status, body = self.delete('/api/sessions/' + sid)
        self.assertEqual(status, 400)
        self.assertIn('师生任务', body['error'])
        status, body = self.request(f'/api/sessions/{sid}/archive', {'archived': True})
        self.assertEqual(status, 200)
        self.assertTrue(body['archived'])

    def test_settings_endpoint_saves_without_exposing_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            with patch.dict(os.environ, {'MATH_SETTINGS_PATH': str(path)}, clear=True):
                status, body = self.request('/api/settings')
                self.assertEqual(status, 200)
                self.assertNotIn('api_key', body)
                status, saved = self.request('/api/settings', {
                    'backend': 'http', 'base_url': 'https://api.example.com/v1',
                    'model': 'demo', 'api_key': 'secret-value'})
                self.assertEqual(status, 200)
                self.assertTrue(saved['has_key'])
                self.assertNotIn('secret-value', json.dumps(saved))
                status, body = self.request('/api/settings')
                self.assertTrue(body['has_key'])
                self.assertNotIn('secret-value', json.dumps(body))

    def test_settings_environment_overrides_and_rejects_ui_save(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            with patch.dict(os.environ, {
                    'MATH_SETTINGS_PATH': str(path),
                    'MATH_API_BASE': 'https://env.example.com/v1',
                    'MATH_MODEL': 'env-model'}, clear=True):
                status, body = self.request('/api/settings')
                self.assertEqual(status, 200)
                self.assertTrue(body['environment_locked'])
                self.assertEqual(body['source'], 'environment')
                self.assertEqual(body['base_url'], 'https://env.example.com/v1')
                status, error = self.request('/api/settings', {
                    'backend': 'http', 'base_url': 'https://new.example.com/v1', 'model': 'm'})
                self.assertEqual(status, 400)
                self.assertIn('环境变量', error['error'])

    def test_settings_test_endpoint_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            with patch.dict(os.environ, {'MATH_SETTINGS_PATH': str(path)}, clear=True):
                status, body = self.request('/api/settings/test', {
                    'backend': 'codex-cli', 'codex_bin': sys.executable})
                self.assertEqual(status, 200)
                self.assertFalse(body['ok'])
                self.assertEqual(body['backend'], 'codex-cli')


if __name__=='__main__':unittest.main()
