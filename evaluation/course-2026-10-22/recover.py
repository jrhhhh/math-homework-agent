"""Recover model invocation failures without overwriting the initial experiment.

Successful initial outputs are reused byte-for-byte. Failed outputs are retained
in the initial directory and retried serially against its frozen source. This is
a resumed run across a service interruption, not an independent repetition.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

HERE=Path(__file__).parent
INITIAL=HERE/'runs/initial'
OUT=HERE/'runs/recovered'
SNAPSHOT=INITIAL/'frozen_source'


def main():
    sys.path.insert(0,str(SNAPSHOT))
    from app.core import run
    OUT.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((INITIAL/'manifest.json').read_text())
    for name,sha in manifest['frozen_files'].items():
        assert hashlib.sha256((SNAPSHOT/name).read_bytes()).hexdigest()==sha,name
    provenance={'initial_run':'../initial','source_snapshot':'../initial/frozen_source',
                'description':'Serial recovery of model invocation failures; successful initial records reused verbatim; not independent repeats.',
                'created_at':datetime.now(timezone.utc).isoformat(),'files':{}}
    for path in sorted(INITIAL.glob('C*.json')):
        old=json.loads(path.read_text());target=OUT/path.name
        if 'result' in old:
            if not target.exists():shutil.copy2(path,target)
            provenance['files'][path.name]={'source':'initial-success','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    for name in ('model-configuration.json',):
        if (INITIAL/name).exists():shutil.copy2(INITIAL/name,OUT/name)
    (OUT/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2))
    remaining=[p for p in sorted(INITIAL.glob('C*.json')) if 'result' not in json.loads(p.read_text())]
    for index,path in enumerate(remaining,1):
        target=OUT/path.name
        if target.exists():
            existing=json.loads(target.read_text())
            if 'result' in existing:continue
            raise RuntimeError('补跑失败已有记录；先调查原因，不静默覆盖。')
        old=json.loads(path.read_text())
        payload={k:old[k] for k in ('case_id','arm','repeat','input')}
        payload.update(started_at=datetime.now(timezone.utc).isoformat(),recovery_of=str(path.relative_to(HERE)))
        try:payload['result']=run(old['input'],arm=old['arm'])
        except Exception as exc:payload['error']=str(exc)
        payload['completed_at']=datetime.now(timezone.utc).isoformat()
        target.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
        provenance['files'][path.name]={'source':'recovered','initial_failure':str(path.relative_to(HERE))}
        (OUT/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2))
        print(f'{index}/{len(remaining)} {path.name} '+payload.get('result',{}).get('status','error'),flush=True)
        if 'error' in payload:raise RuntimeError('模型调用仍失败，已停止后续调用，避免连续空跑。')


if __name__=='__main__':main()
