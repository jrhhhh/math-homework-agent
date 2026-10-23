#!/usr/bin/env python3
"""Run current suites in separate processes and retain actual outputs."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/delivery/evidence'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    suites=[('root-tests',ROOT,['-m','unittest','discover','-s','tests','-p','test_*.py']),
            ('solver-gates',ROOT,['-m','unittest','discover','-s','math-solver/tests','-p','test_*.py']),
            ('draft-gates',ROOT,['-m','unittest','discover','-s','draft-coach/tests','-p','test_*.py']),
            ('solver-bench',ROOT/'math-solver/bench',['-m','unittest','discover','-s','tests','-p','test_*.py']),
            ('draft-bench',ROOT/'draft-coach/bench',['-m','unittest','discover','-s','tests','-p','test_*.py']),
            ('workbench',ROOT,['-m','unittest','discover','-s','app/tests','-p','test_*.py']),
            ('lesson-builder-regression',ROOT/'lesson-materials-builder',['scripts/bench.py','regress']),
            ('exact-verification',ROOT,['-m','unittest','verification.test_exact']),
            ('solver-schema',ROOT/'math-solver/bench',['schema_check.py']),
            ('draft-schema',ROOT/'draft-coach/bench',['schema_check.py']),
            ('math-facts-10',ROOT,['tests/核验测试数学.py']),
            ('math-facts-6',ROOT,['tests/新例计算核验.py']),
            ('math-facts-11',ROOT,['tests/高中题型计算核验.py'])]
    def execute(suite):
        name,cwd,args=suite
        result=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,timeout=120)
        output=result.stdout+result.stderr
        (OUT/f'{name}.txt').write_text(output)
        count=re.search(r'Ran (\d+) tests?',output)
        return {'suite':name,'cwd':str(cwd.relative_to(ROOT)),'args':args,
                'exit_code':result.returncode,'tests':int(count[1]) if count else None}
    with ThreadPoolExecutor(max_workers=3) as pool:
        records=list(pool.map(execute,suites))
    summary={'executed_at':datetime.now(timezone.utc).isoformat(),'python':sys.version,
             'records':records,'unit_tests':sum(r['tests'] or 0 for r in records),
             'lesson_builder_privacy_identifier_count':sum(
                 len(x.strip()) >= 2 for x in os.environ.get('BENCH_IDENTIFIERS','').split(',')),
             'all_passed':all(r['exit_code']==0 for r in records)}
    (OUT/'verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0 if summary['all_passed'] else 1


if __name__=='__main__':sys.exit(main())
