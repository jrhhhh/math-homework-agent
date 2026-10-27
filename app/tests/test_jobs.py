"""Durable recovery, cancellation and idempotency contracts."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from app.server import Store
from app.jobs import JobQueue


class JobsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'db.sqlite';self.store=Store(self.path)
    def tearDown(self):self.tmp.cleanup()
    def queue(self,handler):return JobQueue(self.store,{'test':handler},start=False)
    def test_retry_reuses_completed_step_and_hides_payload(self):
        calls=[]
        def handler(payload,ctx):
            value=ctx.step('first',lambda:calls.append('first') or {'ok':True})
            if len(calls)==1:calls.append('failed');raise ValueError('temporary failure')
            return ctx.step('second',lambda:calls.append('second') or value)
        q=self.queue(handler);job=q.submit('test',{'secret':'private'},'same');q.run_one()
        self.assertEqual(q.get(job['id'])['state'],'paused');q.retry(job['id']);q.run_one()
        self.assertEqual(calls,['first','failed','second']);self.assertEqual(q.get(job['id'])['state'],'completed')
        self.assertNotIn('payload',q.public(q.get(job['id'])));self.assertNotIn('checkpoints',q.public(q.get(job['id'])))
        self.assertIn('reused',[e['type'] for e in q.get(job['id'])['events']])
    def test_idempotency_capacity_and_queued_cancel(self):
        q=self.queue(lambda p,c:p);a=q.submit('test',{},'a')
        self.assertEqual(q.submit('test',{},'a')['id'],a['id'])
        with self.assertRaises(ValueError):q.submit('test',{'different':True},'a')
        for i in range(3):q.submit('test',{'i':i})
        with self.assertRaises(ValueError):q.submit('test',{})
        q.cancel(a['id']);self.assertEqual(q.get(a['id'])['state'],'cancelled');q.submit('test',{})
    def test_running_cancel_stops_at_boundary_and_keeps_receipt(self):
        q=None
        def handler(p,ctx):
            def first():q.cancel(ctx.job['id']);return {'saved':True}
            ctx.step('first',first)
            self.fail('must not run next stage')
        q=self.queue(handler);job=q.submit('test',{});q.run_one();saved=q.get(job['id'])
        self.assertEqual(saved['state'],'cancelled');self.assertEqual(saved['checkpoints']['first'],{'saved':True})
    def test_invalidated_receipt_recomputes(self):
        calls=[];valid=[True]
        def handler(p,ctx):
            ctx.step('artifact',lambda:calls.append('build') or {'sha':'old'},valid=lambda _:valid[0])
            raise ValueError('verify failed')
        q=self.queue(handler);job=q.submit('test',{});q.run_one();valid[0]=False;q.retry(job['id']);q.run_one()
        self.assertEqual(calls,['build','build'])
    def test_process_crash_then_manual_recovery(self):
        # A separate interpreter dies after persisting one step, before finalization.
        code='''import os,sys
from app.server import Store
from app.jobs import JobQueue
q=JobQueue(Store(sys.argv[1]),{'test':lambda p,c:(c.step('saved',lambda:{'value':7}),os._exit(17))},start=False)
q.submit('test',{},'crash');q.run_one()
'''
        result=subprocess.run([sys.executable,'-c',code,str(self.path)],cwd=Path(__file__).resolve().parents[2])
        self.assertEqual(result.returncode,17)
        def recover(p,c):return c.step('saved',lambda:self.fail('checkpoint was lost'))
        q=self.queue(recover);job=q.list()[0];self.assertEqual(job['state'],'paused');self.assertEqual(job['completed_steps'],['saved'])
        self.assertFalse(q.run_one());q.retry(job['id']);q.run_one();self.assertEqual(q.get(job['id'])['result'],{'value':7})


if __name__=='__main__':unittest.main()
