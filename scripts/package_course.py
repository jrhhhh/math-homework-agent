#!/usr/bin/env python3
"""Package current sources and course evidence, excluding unrelated local work."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=ROOT/'delivery/math-homework-agent-course-20261022.zip')
    args=parser.parse_args()
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    files={ROOT/name for name in tracked if name and (ROOT/name).is_file()}
    for directory in ('app','docs/delivery','evaluation','verification','scripts','solution-refiner','high-school-math-teacher-agent','lesson-materials-builder','learning-task-designer','learning-evidence-bridge','remedial-lesson-planner'):
        files.update(p for p in (ROOT/directory).rglob('*') if p.is_file())
    files.update([ROOT/'run.py',ROOT/'requirements-verify.txt',ROOT/'tests/test_handoff.py',ROOT/'tests/test_teacher_agent.py',ROOT/'docs/teaching-loop.md'])
    files={p for p in files if not any(part in ('__pycache__','.local','.venv','.git') for part in p.relative_to(ROOT).parts)
           and p.suffix not in ('.pyc','.zip')}
    manifest={'created_at':datetime.now(timezone.utc).isoformat(),
              'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'scope':'Current project sources and course delivery evidence. Excludes local student database, credentials and pre-existing untracked RSI experiments.',
              'files':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in sorted(files):archive.write(p,'math-homework-agent/'+str(p.relative_to(ROOT)))
        archive.writestr('math-homework-agent/DELIVERY-MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(args.out) as archive:
        bad=archive.testzip()
        if bad:raise RuntimeError('Archive CRC failed: '+bad)
        for name,sha in manifest['files'].items():
            if hashlib.sha256(archive.read('math-homework-agent/'+name)).hexdigest()!=sha:
                raise RuntimeError('Archive content mismatch: '+name)
    result={'archive':str(args.out.resolve()),'files':len(files),'bytes':args.out.stat().st_size,
            'sha256':hashlib.sha256(args.out.read_bytes()).hexdigest(),'crc_and_all_content_hashes_verified':True}
    # Keep this outside the archived source manifest to avoid a self-referential hash.
    args.out.with_suffix('.verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
