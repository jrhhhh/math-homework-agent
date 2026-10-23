"""Loopback-only HTTP service with immutable submissions and async inference."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import threading
import uuid

from .core import normalize, run, version
from .model import available

STATIC = Path(__file__).parent / 'static'


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, title TEXT, created TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS submissions (id TEXT PRIMARY KEY, session_id TEXT, revision INTEGER, created TEXT, data TEXT, version TEXT, state TEXT, result TEXT, UNIQUE(session_id, revision))')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def create_session(self, title='新的练习'):
        sid = uuid.uuid4().hex
        with self.connect() as db:
            db.execute('INSERT INTO sessions VALUES (?,?,?)', (sid, title[:80], now()))
        return sid

    def list_sessions(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM sessions ORDER BY created DESC')]

    def submit(self, sid, data, allow_mode_change=False):
        data = normalize(data)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT id FROM sessions WHERE id=?', (sid,)).fetchone():
                raise ValueError('练习不存在')
            previous = db.execute('SELECT * FROM submissions WHERE session_id=? ORDER BY revision DESC LIMIT 1', (sid,)).fetchone()
            if previous and json.loads(previous['data'])['mode'] == 'hint' and not allow_mode_change:
                data['mode'] = 'hint'
            revision = previous['revision']+1 if previous else 1
            rid = uuid.uuid4().hex
            db.execute('INSERT INTO submissions VALUES (?,?,?,?,?,?,?,?)',
                       (rid, sid, revision, now(), json.dumps(data, ensure_ascii=False), version(data), 'queued', None))
            if revision == 1:
                db.execute('UPDATE sessions SET title=? WHERE id=?', ((data['problem'] or data['draft'])[:40], sid))
        return rid

    def update(self, rid, state, result=None):
        with self.connect() as db:
            db.execute('UPDATE submissions SET state=?, result=? WHERE id=?',
                       (state, json.dumps(result, ensure_ascii=False) if result else None, rid))

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
            row['is_current'] = row['id'] == rows[-1]['id']
        return rows

    def get(self, rid):
        with self.connect() as db:
            row = db.execute('SELECT * FROM submissions WHERE id=?', (rid,)).fetchone()
        if row is None:
            return None
        out = self.decode(row)
        out['is_current'] = self.history(out['session_id'])[-1]['id'] == rid
        return out


class Application:
    def __init__(self, store, runner=run):
        self.store = store
        self.runner = runner
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.capacity = threading.BoundedSemaphore(4)
        # A process restart cannot resume an inference handle; retain a truthful terminal record.
        with store.connect() as db:
            db.execute("UPDATE submissions SET state='interrupted' WHERE state IN ('queued','running')")

    def submit(self, sid, data, change_mode=False):
        if not self.capacity.acquire(blocking=False):
            raise ValueError('当前任务较多，请等待已有任务完成。')
        try:
            rid = self.store.submit(sid, data, change_mode)
        except Exception:
            self.capacity.release()
            raise
        self.pool.submit(self.work, rid)
        return rid

    def work(self, rid):
        try:
            self.store.update(rid, 'running')
            result = self.runner(self.store.get(rid)['data'])
            self.store.update(rid, result['status'], result)
        except Exception as exc:
            self.store.update(rid, 'error', {'error': str(exc)})
        finally:
            self.capacity.release()


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
                return self.send({'ok': True, 'backend': 'codex-cli', 'available': available()})
            if self.path == '/api/sessions':
                return self.send(app.store.list_sessions())
            if self.path.startswith('/api/sessions/'):
                return self.send(app.store.history(self.path.split('/')[3]))
            if self.path.startswith('/api/submissions/'):
                result = app.store.get(self.path.split('/')[3])
                return self.send(result or {'error': '提交不存在'}, 200 if result else 404)
            name = {'/': 'index.html', '/style.css': 'style.css', '/app.js': 'app.js'}.get(self.path)
            if name is None:
                return self.send({'error': '不存在'}, 404)
            content = (STATIC / name).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', {'html': 'text/html', 'css': 'text/css', 'js': 'text/javascript'}[name.split('.')[-1]]+'; charset=utf-8')
            self.send_header('Content-Length', str(len(content)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            # Browser-origin protection; service only binds to loopback.
            origin = self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'):
                return self.send({'error': '来源不允许'}, 403)
            if not self.headers.get('Content-Type', '').startswith('application/json'):
                return self.send({'error': '需要 application/json'}, 415)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 150000:
                    raise ValueError('请求大小非法')
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError('需要 JSON 对象')
                if self.path == '/api/sessions':
                    return self.send({'id': app.store.create_session()}, 201)
                if self.path.startswith('/api/sessions/') and self.path.endswith('/submissions'):
                    sid = self.path.split('/')[3]
                    rid = app.submit(sid, data, data.get('allow_mode_change') is True)
                    return self.send({'id': rid}, 202)
                return self.send({'error': '不存在'}, 404)
            except (ValueError, UnicodeError) as exc:
                return self.send({'error': str(exc)}, 400)
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
        app.pool.shutdown(wait=True)


if __name__ == '__main__':
    main()
