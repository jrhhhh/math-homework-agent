"""SQLite-backed, bounded background jobs with durable step receipts and manual retry."""
import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone


def now():return datetime.now(timezone.utc).isoformat()

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


class StopRequested(RuntimeError):pass


class JobContext:
    def __init__(self,queue,job):self.queue=queue;self.job=job
    def step(self,name,operation,valid=None):
        current=self.queue.get(self.job['id'])
        if current['cancel_requested']:raise StopRequested('任务已停止；已完成步骤保留。')
        receipt=current['checkpoints'].get(name)
        if receipt is not None and (valid is None or valid(receipt)):
            self.queue.event(self.job['id'],'reused',name);return receipt
        self.queue.event(self.job['id'],'step',name)
        result=operation()
        # A requested stop takes effect only at a boundary; a completed receipt is retained.
        with self.queue.store.connect() as db:
            current=json.loads(db.execute('SELECT checkpoints FROM durable_jobs WHERE id=?',(self.job['id'],)).fetchone()[0])
            current[name]=result
            db.execute('UPDATE durable_jobs SET checkpoints=?,updated=? WHERE id=?',(json.dumps(current,ensure_ascii=False),now(),self.job['id']))
        self.queue.event(self.job['id'],'checkpoint',name)
        if self.queue.get(self.job['id'])['cancel_requested']:raise StopRequested('当前步骤已完成，任务按请求停止。')
        return result


class JobQueue:
    def __init__(self,store,handlers,workers=2,start=True):
        self.store=store;self.handlers=handlers;self.stop=threading.Event();self.wake=threading.Event();self.threads=[]
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS durable_jobs (id TEXT PRIMARY KEY, kind TEXT, payload TEXT, state TEXT, created TEXT, updated TEXT, checkpoints TEXT, result TEXT, error TEXT, cancel_requested INTEGER, request_key TEXT UNIQUE, input_hash TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS job_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, type TEXT, detail TEXT, created TEXT)')
            rows=db.execute("SELECT id FROM durable_jobs WHERE state='running'").fetchall()
            db.execute("UPDATE durable_jobs SET state='paused',error='服务重启；已完成步骤已保存，请选择继续。',updated=? WHERE state='running'",(now(),))
            for row in rows:db.execute('INSERT INTO job_events(job_id,type,detail,created) VALUES (?,?,?,?)',(row['id'],'paused','server_restart',now()))
        if start:
            for index in range(workers):
                thread=threading.Thread(target=self.worker,daemon=True,name=f'math-job-{index}');thread.start();self.threads.append(thread)

    def submit(self,kind,payload,request_key=None):
        if kind not in self.handlers or not isinstance(payload,dict):raise ValueError('任务类型或参数无效。')
        if request_key is not None and (not isinstance(request_key,str) or not 1<=len(request_key)<=120):raise ValueError('请求编号无效。')
        fingerprint=digest({'kind':kind,'payload':payload})
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM durable_jobs WHERE request_key=?',(request_key,)).fetchone() if request_key else None
            if old:
                if old['input_hash']!=fingerprint:raise ValueError('同一请求编号不能用于不同任务。')
                jid=old['id']
            else:
                if db.execute("SELECT COUNT(*) FROM durable_jobs WHERE state IN ('queued','running')").fetchone()[0]>=4:raise ValueError('当前任务较多，请等待或停止已有任务。')
                if payload.get('lesson_id'):
                    active=db.execute("SELECT payload FROM durable_jobs WHERE state IN ('queued','running')").fetchall()
                    if any(json.loads(row['payload']).get('lesson_id')==payload['lesson_id'] for row in active):raise ValueError('这份备课已有任务正在运行，请先完成或停止。')
                jid=uuid.uuid4().hex
                db.execute('INSERT INTO durable_jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(jid,kind,json.dumps(payload,ensure_ascii=False),'queued',now(),now(),'{}',None,None,0,request_key,fingerprint))
                db.execute('INSERT INTO job_events(job_id,type,detail,created) VALUES (?,?,?,?)',(jid,'queued',kind,now()))
        self.wake.set();return self.get(jid)

    def get(self,jid):
        with self.store.connect() as db:
            row=db.execute('SELECT * FROM durable_jobs WHERE id=?',(jid,)).fetchone()
            events=[dict(item) for item in db.execute('SELECT seq,type,detail,created FROM job_events WHERE job_id=? ORDER BY seq',(jid,))]
        if not row:raise ValueError('任务不存在。')
        out=dict(row)
        for key in ('payload','checkpoints','result'):out[key]=json.loads(out[key]) if out[key] else None
        out['events']=events;return out

    def list(self):
        with self.store.connect() as db:ids=[row['id'] for row in db.execute('SELECT id FROM durable_jobs ORDER BY created DESC LIMIT 100')]
        return [self.public(self.get(jid)) for jid in ids]

    @staticmethod
    def public(job):
        return {key:job[key] for key in ('id','kind','state','created','updated','result','error','cancel_requested','events')} | {'completed_steps':list(job['checkpoints'] or {})}

    def event(self,jid,kind,detail):
        with self.store.connect() as db:db.execute('INSERT INTO job_events(job_id,type,detail,created) VALUES (?,?,?,?)',(jid,kind,detail,now()))

    def retry(self,jid):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM durable_jobs WHERE id=?',(jid,)).fetchone()
            if not row or row['state'] not in ('paused','cancelled'):raise ValueError('只有暂停或停止的任务可以继续。')
            if db.execute("SELECT COUNT(*) FROM durable_jobs WHERE state IN ('queued','running')").fetchone()[0]>=4:raise ValueError('请等待已有任务完成后继续。')
            payload=json.loads(row['payload'])
            if payload.get('lesson_id'):
                active=db.execute("SELECT payload FROM durable_jobs WHERE state IN ('queued','running')").fetchall()
                if any(json.loads(item['payload']).get('lesson_id')==payload['lesson_id'] for item in active):raise ValueError('这份备课已有任务正在运行，请等待后继续。')
            db.execute("UPDATE durable_jobs SET state='queued',cancel_requested=0,error=NULL,updated=? WHERE id=?",(now(),jid))
        self.event(jid,'retried','保留已完成步骤');self.wake.set();return self.public(self.get(jid))

    def cancel(self,jid):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT state FROM durable_jobs WHERE id=?',(jid,)).fetchone()
            if not row or row['state'] not in ('queued','running','paused'):raise ValueError('任务已结束或不存在。')
            state='running' if row['state']=='running' else 'cancelled'
            db.execute('UPDATE durable_jobs SET state=?,cancel_requested=1,updated=? WHERE id=?',(state,now(),jid))
        self.event(jid,'stop_requested','当前调用返回后在步骤边界停止');return self.public(self.get(jid))

    def run_one(self):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute("SELECT * FROM durable_jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
            if not row:return False
            db.execute("UPDATE durable_jobs SET state='running',updated=? WHERE id=?",(now(),row['id']))
        job=self.get(row['id']);ctx=JobContext(self,job)
        try:
            result=self.handlers[job['kind']](job['payload'],ctx)
            state='cancelled' if self.get(job['id'])['cancel_requested'] else 'completed';error=None
        except StopRequested as exc:result=None;state='cancelled';error=str(exc)
        except Exception as exc:result=None;state='paused';error=str(exc)[:1000]
        with self.store.connect() as db:db.execute('UPDATE durable_jobs SET state=?,result=?,error=?,updated=? WHERE id=?',(state,json.dumps(result,ensure_ascii=False) if result is not None else None,error,now(),job['id']))
        self.event(job['id'],state,error or '完成');return True

    def worker(self):
        while not self.stop.is_set():
            if not self.run_one():self.wake.wait(.25);self.wake.clear()

    def close(self):
        self.stop.set();self.wake.set()
        for thread in self.threads:thread.join()
