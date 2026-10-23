#!/usr/bin/env python3
"""Opt-in real-model interface smoke; diagnosis is an explicitly synthetic fixture."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import model
from app.server import Store
from app.teaching_loop import TeachingLoop


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--real-model',action='store_true',help='Authorize two real model calls through local Codex CLI')
    parser.add_argument('--out',type=Path,default=ROOT/'docs/delivery/evidence/teaching-loop-model-smoke.json')
    args=parser.parse_args()
    if not args.real_model:parser.error('This smoke makes model calls; pass --real-model to run it.')
    records=[]
    def generator(prompt):
        response=model.generate(prompt)
        records.append({key:response.get(key) for key in ('raw','elapsed_seconds','usage','backend','requested_model')})
        return response
    report={'executed_at':datetime.now(timezone.utc).isoformat(), 'scope':'Two real model interface calls; student diagnosis is a synthetic fixture. Not a teaching-effect or mathematical-accuracy evaluation.', 'calls':records, 'passed':False}
    try:
        with tempfile.TemporaryDirectory(prefix='teaching-model-smoke-') as folder:
            store=Store(Path(folder)/'smoke.sqlite')
            loop=TeachingLoop(store,generator=generator)
            draft=loop.design({'title':'高一等式逆运算','objective':'设计一道一元一次方程题，要求学生说明等式两边的同一运算并代回验根。只用高中及以前方法。'})
            report['generated_task_draft']=draft
            # Fixed known example keeps the student evidence distinct from generated tasks.
            task=loop.create({'title':'合成诊断用例','items':[{'problem':'解 x+1=2。','objective':'等式两边同时减去1并验根'}]})
            opened=loop.open_item(task['id'],task['items'][0]['id'])
            rid=store.submit(opened['session_id'],{'problem':opened['problem'],'solution':'x=3','mode':'check'})
            store.update(rid,'ready',{'status':'ready','output':{'reply':'代回检查。','result':{'judgment':'incorrect','first_error':{'step':1,'quote':'x=3','reason':'3+1不等于2。'}}}})
            report['remedial_plan']=loop.plan(task['id'])
            report['passed']=True
    except Exception as exc:
        report['error']=str(exc)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'calls':len(records),'path':str(args.out),'error':report.get('error')},ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__=='__main__':sys.exit(main())
