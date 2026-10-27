"""Deterministic browser-test server only. Never use its fake inference as product evidence."""
import argparse
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from app.server import Application, Store, handler_for


def runner(data):
    correct=data['solution'].strip()=='x=1'
    return {'status':'ready','output':{'reply':'当前过程正确。' if correct else '先用逆运算，再代回原式。','result':{'judgment':'correct' if correct else 'incorrect','first_error':None if correct else {'step':1,'quote':data['solution'].splitlines()[0],'reason':'代回原式不成立。'},'minimal_fix':'','hint':'','evidence':[]}},'attempts':[]}


def generator(prompt):
    if '补救教学规划' in prompt:
        report=json.loads(prompt.rsplit('\n',1)[1])
        refs='、'.join(row['submission_id'] for row in report['items'] if row['submission_id'])
        value={'draft_markdown':'# 逆运算补救课\n依据当前提交 '+refs+'。\n教师提问：等式两边怎样同时减去1？\n学生动作：修订原题并代回。\n再练习目标：观察逆运算和验根过程。'}
    else:
        value={'title':'逆运算练习','items':[{'problem':'解 x+1=2。','objective':'等式两边同时减去1并验根','success_criteria':'写出同一运算并代回验根','interactive_template':'unit_circle'}]}
    return {'raw':json.dumps(value,ensure_ascii=False)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8767)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='teaching-browser-fixture-') as folder:
        os.environ['MATH_UPLOAD_DIR']=str(Path(folder)/'uploads')
        os.environ['MATH_SETTINGS_PATH']=str(Path(folder)/'settings.json')
        app=Application(Store(Path(folder)/'fixture.sqlite'),runner=runner)
        app.teaching.generator=generator
        server=ThreadingHTTPServer(('127.0.0.1',args.port),handler_for(app))
        print(f'FIXTURE ONLY — fake inference: http://127.0.0.1:{args.port}/',flush=True)
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close();app.close()


if __name__=='__main__':main()
