"""Loopback-only HTTP service with immutable submissions and async inference."""
import argparse
import importlib.util
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import sqlite3
import threading
import uuid

from .core import normalize, run, version
from .model import available, backend, probe
from . import settings
from . import uploads
from .lesson_studio import LessonStudio
from .teaching_loop import TeachingLoop
from .support import SupportLedger
from .math_widgets import evaluate as evaluate_widget
from .jobs import JobQueue

STATIC = Path(__file__).parent / 'static'


def now():
    return datetime.now(timezone.utc).isoformat()


def attachment_keys(data):
    keys = set()
    if not isinstance(data, dict):
        return keys
    for item in data.get('attachments') or []:
        if isinstance(item, dict) and item.get('sha256') and item.get('ext'):
            keys.add((item['sha256'], item['ext']))
    legacy = data.get('image')
    if isinstance(legacy, dict) and legacy.get('sha256') and legacy.get('ext'):
        keys.add((legacy['sha256'], legacy['ext']))
    return keys


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, title TEXT, created TEXT, archived INTEGER DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS submissions (id TEXT PRIMARY KEY, session_id TEXT, revision INTEGER, created TEXT, data TEXT, version TEXT, state TEXT, result TEXT, UNIQUE(session_id, revision))')
            db.execute('CREATE TABLE IF NOT EXISTS lessons (id TEXT PRIMARY KEY, title TEXT, created TEXT, data TEXT, outline TEXT, missing TEXT, questions TEXT, slides_markdown TEXT, figures_spec TEXT, status TEXT, result TEXT)')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(sessions)')}
            if 'archived' not in columns:
                db.execute('ALTER TABLE sessions ADD COLUMN archived INTEGER DEFAULT 0')

        self.support = SupportLedger(self)

    @contextmanager
    def connect(self):
        """Open one connection and close it on exit.

        The context manager keeps SQLite's commit/rollback semantics, but also
        releases the file handle so temporary databases can be removed on
        Windows, where an open handle blocks deletion.
        """
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_session(self, title='新的练习'):
        sid = uuid.uuid4().hex
        with self.connect() as db:
            db.execute('INSERT INTO sessions (id, title, created) VALUES (?,?,?)',
                       (sid, title[:80], now()))
        return sid

    def list_sessions(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM sessions ORDER BY created DESC')]

    def set_archived(self, sid, archived):
        with self.connect() as db:
            cursor = db.execute('UPDATE sessions SET archived=? WHERE id=?',
                                (1 if archived else 0, sid))
            if cursor.rowcount == 0:
                raise ValueError('练习不存在')
        return {'id': sid, 'archived': bool(archived)}

    def delete_session(self, sid):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT id FROM sessions WHERE id=?', (sid,)).fetchone():
                raise ValueError('练习不存在')
            try:
                bound = db.execute('SELECT id FROM teaching_items WHERE session_id=? LIMIT 1',
                                   (sid,)).fetchone()
            except sqlite3.OperationalError:
                bound = None
            if bound:
                raise ValueError('该练习已被师生任务引用，不能删除；请改为归档。')
            submission_ids={row['id'] for row in db.execute('SELECT id FROM submissions WHERE session_id=?',(sid,))}
            jobs=[]
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='durable_jobs'").fetchone():
                jobs=[row for row in db.execute("SELECT id,payload,state FROM durable_jobs WHERE kind='diagnose'") if json.loads(row['payload']).get('submission_id') in submission_ids]
                if any(row['state'] in ('queued','running') for row in jobs):raise ValueError('该练习仍有后台任务，请先完成或停止后再删除。')
            db.execute('DELETE FROM submission_support WHERE submission_id IN (SELECT id FROM submissions WHERE session_id=?)',(sid,))
            db.execute('DELETE FROM learning_support WHERE session_id=?',(sid,))
            for job in jobs:
                db.execute('DELETE FROM job_events WHERE job_id=?',(job['id'],))
                db.execute('DELETE FROM durable_jobs WHERE id=?',(job['id'],))
            removed = set()
            for row in db.execute('SELECT data FROM submissions WHERE session_id=?', (sid,)):
                try:
                    removed |= attachment_keys(json.loads(row['data']))
                except (TypeError, ValueError):
                    pass
            db.execute('DELETE FROM submissions WHERE session_id=?', (sid,))
            db.execute('DELETE FROM sessions WHERE id=?', (sid,))
            if removed:
                remaining = set()
                for row in db.execute('SELECT data FROM submissions'):
                    try:
                        remaining |= attachment_keys(json.loads(row['data']))
                    except (TypeError, ValueError):
                        pass
                for sha256, extension in removed - remaining:
                    path = uploads.path_for(sha256, extension)
                    if path:
                        try:
                            path.unlink()
                        except OSError:
                            pass
        return {'id': sid, 'deleted': True}

    def submit(self, sid, data, allow_mode_change=False):
        data = normalize(data)
        data = uploads.persist(data)
        data = normalize(data)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT id FROM sessions WHERE id=?', (sid,)).fetchone():
                raise ValueError('练习不存在')
            previous = db.execute('SELECT * FROM submissions WHERE session_id=? ORDER BY revision DESC LIMIT 1', (sid,)).fetchone()
            if previous and json.loads(previous['data'])['mode'] == 'hint' and not allow_mode_change:
                data['mode'] = 'hint'
                data = normalize(data)
            revision = previous['revision']+1 if previous else 1
            rid = uuid.uuid4().hex
            db.execute('INSERT INTO submissions VALUES (?,?,?,?,?,?,?,?)',
                       (rid, sid, revision, now(), json.dumps(data, ensure_ascii=False), version(data), 'queued', None))
            self.support.before_submit(db, sid, rid, data)
            if revision == 1:
                db.execute('UPDATE sessions SET title=? WHERE id=?', ((data['problem'] or data['draft'])[:40], sid))
        return rid

    def update(self, rid, state, result=None):
        with self.connect() as db:
            db.execute('UPDATE submissions SET state=?, result=? WHERE id=?',
                       (state, json.dumps(result, ensure_ascii=False) if result else None, rid))
            self.support.feedback_available(db, rid, state, result)

    @staticmethod
    def decode(row):
        out = dict(row)
        out['data'] = json.loads(out['data'])
        out['result'] = json.loads(out['result']) if out['result'] else None
        return out

    def history(self, sid):
        with self.connect() as db:
            rows = [self.decode(r) for r in db.execute('SELECT * FROM submissions WHERE session_id=? ORDER BY revision', (sid,))]
        for row in rows:
            row['support'] = self.support.snapshot(row['id'])
            row['is_current'] = row['id'] == rows[-1]['id']
        return rows

    def get(self, rid):
        with self.connect() as db:
            row = db.execute('SELECT * FROM submissions WHERE id=?', (rid,)).fetchone()
        if row is None:
            return None
        out = self.decode(row)
        out['support'] = self.support.snapshot(rid)
        out['is_current'] = self.history(out['session_id'])[-1]['id'] == rid
        return out

    def create_lesson(self, lesson_id, title, data, outline, missing, questions):
        with self.connect() as db:
            db.execute('INSERT INTO lessons VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                       (lesson_id, title[:120], now(), json.dumps(data, ensure_ascii=False), outline,
                        json.dumps(missing, ensure_ascii=False), json.dumps(questions, ensure_ascii=False),
                        None, None, 'outline_ready', None))
        return self.get_lesson(lesson_id)

    @staticmethod
    def decode_lesson(row):
        out = dict(row)
        for key in ('data', 'missing', 'questions', 'figures_spec', 'result'):
            out[key] = json.loads(out[key]) if out[key] else ([] if key in ('missing', 'questions') else None)
        out['missing_information'] = out['missing']
        return out

    def get_lesson(self, lesson_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM lessons WHERE id=?', (lesson_id,)).fetchone()
        return self.decode_lesson(row) if row else None

    def list_lessons(self):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM lessons ORDER BY created DESC LIMIT 20').fetchall()
        return [{key: value for key, value in self.decode_lesson(row).items()
                 if key not in ('data', 'outline', 'slides_markdown', 'figures_spec', 'result')}
                for row in rows]

    def save_lesson_source(self, lesson_id, outline, clarifications, slides_markdown, figures_spec):
        with self.connect() as db:
            row = db.execute('SELECT data FROM lessons WHERE id=?', (lesson_id,)).fetchone()
            if not row:
                raise ValueError('备课记录不存在。')
            data = json.loads(row['data'])
            data['clarifications'] = clarifications
            db.execute('UPDATE lessons SET data=?, outline=?, slides_markdown=?, figures_spec=?, status=?, result=NULL WHERE id=?',
                       (json.dumps(data, ensure_ascii=False), outline, slides_markdown,
                        json.dumps(figures_spec, ensure_ascii=False), 'source_ready', lesson_id))
        return self.get_lesson(lesson_id)

    def finish_lesson_render(self, lesson_id, status, result):
        with self.connect() as db:
            db.execute('UPDATE lessons SET status=?, result=? WHERE id=?',
                       (status, json.dumps(result, ensure_ascii=False), lesson_id))


class Application:
    def __init__(self, store, runner=run, lesson_studio=None):
        self.store = store
        self.runner = runner
        self.lesson_studio = lesson_studio or LessonStudio(store)
        self.lock = open(store.path+'.lock','a+b')
        try:
            if os.name=='nt':
                import msvcrt
                self.lock.seek(0);self.lock.write(b'0');self.lock.flush();self.lock.seek(0)
                msvcrt.locking(self.lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:
            self.lock.close()
            raise RuntimeError('这个练习数据库已由另一个工作台使用，请使用独立 --db 路径。') from exc
        self.teaching = TeachingLoop(store)
        self.submit_lock = threading.Lock()
        # A process restart cannot resume an inference handle; retain a truthful terminal record.
        with store.connect() as db:
            db.execute("UPDATE submissions SET state='interrupted' WHERE state IN ('queued','running')")
        self.jobs = JobQueue(store, {kind:(lambda payload,ctx,k=kind:self.job_work(k,payload,ctx)) for kind in ('diagnose','task-design','remedial-plan','lesson-outline','lesson-source','lesson-render')})

    def close(self):
        self.jobs.close()
        self.lock.close()

    def submit(self, sid, data, change_mode=False):
        with self.submit_lock:
            with self.store.connect() as db:
                if db.execute("SELECT COUNT(*) FROM durable_jobs WHERE state IN ('queued','running')").fetchone()[0]>=4:
                    raise ValueError('当前任务较多，请等待已有任务完成。')
            rid=self.store.submit(sid,data,change_mode)
            try:self.jobs.submit('diagnose',{'submission_id':rid},'diagnose-'+rid)
            except Exception:
                self.store.update(rid,'interrupted');raise
        return rid

    def work(self,rid):
        try:
            self.store.update(rid,'running')
            result=self.runner(self.store.get(rid)['data'])
            self.store.update(rid,result['status'],result)
            if result['status']=='error':raise ValueError('诊断失败，请继续任务重试。')
            return {'submission_id':rid}
        except Exception as exc:
            self.store.update(rid,'error',{'error':str(exc),'diagnostic':getattr(exc,'diagnostic',{})})
            raise

    def cancel_job(self,jid):
        result=self.jobs.cancel(jid)
        job=self.jobs.get(jid)
        if job['kind']=='diagnose' and job['state']=='cancelled':
            rid=job['payload']['submission_id']
            current=self.store.get(rid)
            if current and current['state'] in ('queued','running'):
                self.store.update(rid,'interrupted',{'status':'error','error':'任务已停止，可在任务中心继续。'})
        return result

    def check_lesson_source(self,lid):
        lesson=self.store.get_lesson(lid)
        if lesson and lesson['data'].get('teaching_source') is not None:self.teaching.require_current(lesson['data']['teaching_source'])

    def job_work(self,kind,payload,ctx):
        if kind=='diagnose':return ctx.step('diagnosis',lambda:self.work(payload['submission_id']))
        if kind=='task-design':
            # Never reuse a parent-bound draft after its evidence became stale.
            if payload.get('parent_id'):self.teaching.require_current({'assignment_id':payload['parent_id'],'evidence_version':payload.get('evidence_version')})
            return ctx.step('task_design',lambda:self.teaching.design(payload))
        if kind=='remedial-plan':return ctx.step('remedial_plan',lambda:self.teaching.plan(payload['assignment_id']),
            valid=lambda result:result['evidence_version']==self.teaching.report(payload['assignment_id'])['evidence_version'])
        if kind=='lesson-outline':
            if payload.get('teaching_source') is not None:self.teaching.require_current(payload['teaching_source'])
            return ctx.step('lesson_outline',lambda:self.lesson_studio.create_outline(payload,lesson_id=ctx.job['id']))
        lid=payload.get('lesson_id');self.check_lesson_source(lid)
        if kind=='lesson-source':return ctx.step('lesson_source',lambda:self.lesson_studio.generate_source(lid,payload))
        if kind=='lesson-render':
            result=self.lesson_studio.render(lid,payload,checkpoint=ctx.step)
            if result['status']!='ready':raise ValueError('；'.join(result['result'].get('errors',[])))
            return result
        raise ValueError('任务类型无效。')


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, value, status=200):
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/api/health':
                return self.send({'ok': True, 'backend': backend(), 'available': available(),
                                  'exact_verification_available':importlib.util.find_spec('sympy') is not None})
            if self.path == '/api/jobs':
                return self.send(app.jobs.list())
            if self.path.startswith('/api/jobs/'):
                try:return self.send(app.jobs.public(app.jobs.get(self.path.split('/')[3])))
                except ValueError as exc:return self.send({'error':str(exc)},404)
            if self.path == '/api/settings':
                return self.send(settings.public())
            attachment_match = re.fullmatch(
                r'/api/uploads/([0-9a-f]{64})\.(png|jpg|webp|pdf|docx|txt|md)', self.path)
            if attachment_match:
                extension = '.' + attachment_match.group(2)
                path = uploads.path_for(attachment_match.group(1), extension)
                if path is None:
                    return self.send({'error': '附件不存在'}, 404)
                content = path.read_bytes()
                mime = uploads.mime_for(extension)
                if extension in ('.txt', '.md'):
                    mime += '; charset=utf-8'
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(content)))
                if not uploads.is_inline(extension):
                    self.send_header('Content-Disposition',
                                     f'attachment; filename="attachment{extension}"')
                self.send_header('Cache-Control', 'private, max-age=31536000, immutable')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers()
                self.wfile.write(content)
                return
            if self.path == '/api/sessions':
                return self.send(app.store.list_sessions())
            if self.path.startswith('/api/sessions/'):
                return self.send(app.store.history(self.path.split('/')[3]))
            if self.path.startswith('/api/submissions/'):
                result = app.store.get(self.path.split('/')[3])
                return self.send(result or {'error': '提交不存在'}, 200 if result else 404)
            if self.path == '/api/teaching':
                return self.send(app.teaching.list())
            if self.path.startswith('/api/teaching/'):
                parts = self.path.split('/')
                try:
                    if len(parts) == 4:
                        return self.send(app.teaching.get(parts[3]))
                    if len(parts) == 6 and parts[4] == 'path':
                        return self.send(app.teaching.learning_path(parts[3], parts[5]))
                    if len(parts) == 5 and parts[4] == 'evidence':
                        return self.send(app.teaching.report(parts[3]))
                except ValueError as exc:
                    return self.send({'error': str(exc)}, 404)
            if self.path == '/api/lessons':
                return self.send(app.store.list_lessons())
            if self.path.startswith('/api/lessons/'):
                parts = self.path.split('/')
                if len(parts) == 4:
                    result = app.store.get_lesson(parts[3])
                    return self.send(result or {'error': '备课记录不存在'}, 200 if result else 404)
                if len(parts) == 6 and parts[4] == 'files':
                    path = app.lesson_studio.file_path(parts[3], parts[5])
                    if path is None:
                        return self.send({'error': '课件文件不存在'}, 404)
                    content = path.read_bytes()
                    from urllib.parse import quote
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.presentationml.presentation' if path.suffix == '.pptx' else 'text/markdown; charset=utf-8')
                    self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + quote(path.name))
                    self.send_header('Content-Length', str(len(content)))
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    self.end_headers()
                    self.wfile.write(content)
                    return
            name = {'/': 'index.html', '/style.css': 'style.css', '/glass.css':'glass.css', '/app.js': 'app.js', '/teaching.js': 'teaching.js', '/jobs.js':'jobs.js', '/interaction.js':'interaction.js', '/learning-path.js':'learning-path.js'}.get(self.path)
            if self.path.startswith('/vendor/katex/'):
                candidate=(STATIC/self.path.lstrip('/')).resolve()
                if candidate.is_relative_to((STATIC/'vendor/katex').resolve()) and candidate.is_file() and candidate.suffix in ('.js','.css','.woff2'):
                    content=candidate.read_bytes()
                    self.send_response(200)
                    self.send_header('Content-Type',mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream')
                    self.send_header('Content-Length',str(len(content)))
                    self.send_header('X-Content-Type-Options','nosniff')
                    self.end_headers();self.wfile.write(content)
                    return
            if name is None:
                return self.send({'error': '不存在'}, 404)
            content = (STATIC / name).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', {'html': 'text/html', 'css': 'text/css', 'js': 'text/javascript'}[name.split('.')[-1]]+'; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(content)

        def do_DELETE(self):
            origin = self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',
                                         f'http://localhost:{self.server.server_port}'):
                return self.send({'error': '来源不允许'}, 403)
            try:
                if self.path.startswith('/api/sessions/') and self.path.count('/') == 3:
                    return self.send(app.store.delete_session(self.path.split('/')[3]))
                return self.send({'error': '不存在'}, 404)
            except ValueError as exc:
                return self.send({'error': str(exc)}, 400)

        def do_POST(self):
            # Browser-origin protection; service only binds to loopback.
            origin = self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
                return self.send({'error': '来源不允许'}, 403)
            if not self.headers.get('Content-Type', '').startswith('application/json'):
                return self.send({'error': '需要 application/json'}, 415)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if self.path in ('/api/lessons/outline','/api/jobs'):
                    max_size = 8 * 1024 * 1024
                elif self.path.startswith('/api/sessions/') and self.path.endswith('/submissions'):
                    max_size = 25 * 1024 * 1024
                elif self.path == '/api/attachments/extract':
                    max_size = 8 * 1024 * 1024
                else:
                    max_size = 150000
                if not 0 < size <= max_size:
                    raise ValueError('请求大小非法')
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError('需要 JSON 对象')
                if self.path == '/api/jobs':
                    return self.send(app.jobs.public(app.jobs.submit(data.get('kind'),data.get('payload'),data.get('request_key'))),202)
                if self.path.startswith('/api/jobs/'):
                    parts=self.path.split('/')
                    if len(parts)==5 and parts[4]=='retry':return self.send(app.jobs.retry(parts[3]))
                    if len(parts)==5 and parts[4]=='cancel':return self.send(app.cancel_job(parts[3]))
                if self.path == '/api/settings':
                    return self.send(settings.save(data))
                if self.path == '/api/attachments/extract':
                    name = data.get('name')
                    encoded = data.get('base64')
                    if not isinstance(name, str) or not isinstance(encoded, str):
                        raise ValueError('需要附件名称与内容。')
                    return self.send(uploads.extract_text(name, encoded))
                if self.path == '/api/settings/test':
                    current = settings.resolve()
                    config = current if current['environment_locked'] else settings.candidate(data)
                    return self.send(probe(config))
                if self.path == '/api/sessions':
                    return self.send({'id': app.store.create_session()}, 201)
                if self.path == '/api/math-widget':
                    return self.send(evaluate_widget(data))
                if self.path == '/api/teaching/design':
                    return self.send(app.teaching.design(data))
                if self.path == '/api/teaching':
                    return self.send(app.teaching.create(data), 201)
                if self.path.startswith('/api/teaching/'):
                    parts = self.path.split('/')
                    if len(parts) == 5 and parts[4] == 'plan':
                        return self.send(app.teaching.plan(parts[3]))
                    if len(parts) == 6 and parts[4] == 'open':
                        return self.send(app.teaching.open_item(parts[3], parts[5]))
                if self.path == '/api/lessons/outline':
                    if data.get('teaching_source') is not None:
                        app.teaching.require_current(data['teaching_source'])
                    return self.send(app.lesson_studio.create_outline(data), 201)
                if self.path.startswith('/api/lessons/') and self.path.endswith('/source'):
                    lesson_id = self.path.split('/')[3]
                    lesson = app.store.get_lesson(lesson_id)
                    if lesson and lesson['data'].get('teaching_source') is not None:
                        app.teaching.require_current(lesson['data']['teaching_source'])
                    return self.send(app.lesson_studio.generate_source(lesson_id, data))
                if self.path.startswith('/api/lessons/') and self.path.endswith('/render'):
                    lesson_id = self.path.split('/')[3]
                    lesson = app.store.get_lesson(lesson_id)
                    if lesson and lesson['data'].get('teaching_source') is not None:
                        app.teaching.require_current(lesson['data']['teaching_source'])
                    return self.send(app.lesson_studio.render(lesson_id, data))
                if self.path.startswith('/api/sessions/') and self.path.endswith('/support'):
                    return self.send(app.store.support.record(self.path.split('/')[3], data), 201)
                if self.path.startswith('/api/sessions/') and self.path.endswith('/archive'):
                    parts = self.path.split('/')
                    if len(parts) == 5 and parts[4] == 'archive':
                        if type(data.get('archived')) is not bool:
                            raise ValueError('archived 必须为布尔值')
                        return self.send(app.store.set_archived(parts[3], data['archived']))
                if self.path.startswith('/api/sessions/') and self.path.endswith('/submissions'):
                    sid = self.path.split('/')[3]
                    rid = app.submit(sid, data, data.get('allow_mode_change') is True)
                    return self.send({'id': rid}, 202)
                return self.send({'error': '不存在'}, 404)
            except (ValueError, UnicodeError) as exc:
                return self.send({'error': str(exc)}, 400)
            except Exception as exc:
                from .model import ModelError
                if isinstance(exc, ModelError):
                    return self.send({'error': str(exc)}, 503)
                return self.send({'error': '备课服务暂时失败，请检查材料、依赖和本地模型状态。'}, 500)
    return Handler


def main():
    parser = argparse.ArgumentParser(description='高中数学练习工作台')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--db', default=os.environ.get('MATH_DB_PATH', '.local/workbench.sqlite3'))
    args = parser.parse_args()
    app = Application(Store(args.db))
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(app))
    print(f'数学练习工作台：http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.close()


if __name__ == '__main__':
    main()
