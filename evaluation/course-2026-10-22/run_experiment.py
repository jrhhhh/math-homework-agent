"""Frozen three-arm real inference, per-case files and resumable progress.

Workers are inference requests only; no development delegation. Ground truth is
never loaded by this runner. It never treats fixtures as generated responses.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

HERE=Path(__file__).parent
ARMS=('baseline','skill','skill_gates')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(source=ROOT):
    files=[p for directory in ('app','math-solver','math-error-diagnosis','draft-coach')
           for p in (source/directory).rglob('*') if p.is_file() and
           ('__pycache__' not in p.parts) and p.suffix in ('.py','.md','.json') and
           not any(x in p.parts for x in ('bench','evals','example','tests','static'))]
    files += [source/'evaluation/course-2026-10-22/cases.jsonl',source/'evaluation/course-2026-10-22/gold.jsonl']
    return {str(p.relative_to(source)):digest(p) for p in sorted(files)}


def one(case, arm, repeat, directory):
    from app.core import run
    path=directory/f'{case["id"]}.{arm}.r{repeat}.json'
    if path.exists():
        existing=json.loads(path.read_text())
        if 'result' in existing:
            return path.name,'saved'
        raise RuntimeError(f'{path.name} 有失败记录；确认原因后用新的运行目录重试，不能覆盖原始记录')
    payload={'case_id':case['id'],'arm':arm,'repeat':repeat,'input':case['input'],
             'started_at':datetime.now(timezone.utc).isoformat()}
    try:
        payload['result']=run(case['input'],arm=arm)
    except Exception as exc:
        payload['error']=str(exc)
    payload['completed_at']=datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    return path.name,payload.get('result',{}).get('status','error')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',default=str(HERE/'runs'/'initial'))
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--repeats',type=int,default=1)
    parser.add_argument('--frozen-source',action='store_true',help='Use the archived evaluated source instead of current workbench code')
    args=parser.parse_args()
    directory=Path(args.out);directory.mkdir(parents=True,exist_ok=True)
    source=directory.resolve()/'frozen_source' if args.frozen_source else ROOT
    sys.path.insert(0,str(source))
    current=freeze(source);manifest=directory/'manifest.json'
    if manifest.exists():
        old=json.loads(manifest.read_text())
        if old['frozen_files'] != current:
            raise RuntimeError('冻结文件发生变化；请恢复文件或创建新的实验，不能混入旧运行')
    else:
        meta={'created_at':datetime.now(timezone.utc).isoformat(),'frozen_files':current,
              'git_base':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'cli_version':subprocess.check_output(['codex','--version'],text=True).strip(),
              'arms':list(ARMS),'repeats':args.repeats,'workers':args.workers,
              'protocol':'Same configured model, per-case fresh context, same output contract; gold hidden. Only skill_gates receives measured gate errors and up to 2 repairs. All arms are scored by the same gates after generation.',
              'limitations':['CLI global instructions and model reasoning defaults are shared across arms; exact server snapshot may be unavailable.','Authored held-out cases, not an external independently sampled test set.','One run per condition cannot establish stable superiority.','Human reviews must be supplied by real reviewers.']}
        manifest.write_text(json.dumps(meta,ensure_ascii=False,indent=2))
    cases=[json.loads(line) for line in (HERE/'cases.jsonl').read_text().splitlines()]
    # Rotate arm order per case to reduce monotonic time/order confounding.
    jobs=[]
    for repeat in range(1,args.repeats+1):
        for i,case in enumerate(cases):
            arms=ARMS[i%3:]+ARMS[:i%3]
            jobs += [(case,arm,repeat,directory) for arm in arms]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(one,*job) for job in jobs]
        for done,future in enumerate(as_completed(futures),1):
            name,status=future.result();print(f'{done}/{len(jobs)} {name} {status}',flush=True)


if __name__=='__main__':
    main()
