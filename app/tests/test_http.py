from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
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


if __name__=='__main__':unittest.main()
