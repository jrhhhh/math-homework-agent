#!/usr/bin/env python3
"""Verify frozen evaluation provenance, complete outputs, and model-review packets."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'evaluation/course-2026-10-22'
RUN=HERE/'runs/recovered'
ARMS=('baseline','skill','skill_gates')
FIELDS=('math_correct','first_error_correct','mode_obeyed','grounded','teaching_useful')


def main():
    manifest=json.loads((RUN/'manifest.json').read_text())
    snapshot=HERE/'runs/initial/frozen_source'
    assert manifest['frozen_files']
    for name,expected in manifest['frozen_files'].items():
        actual=hashlib.sha256((snapshot/name).read_bytes()).hexdigest()
        assert actual==expected,name
    case_ids=[json.loads(line)['id'] for line in (HERE/'cases.jsonl').read_text().splitlines()]
    outputs=0
    for case_id in case_ids:
        for arm in ARMS:
            record=json.loads((RUN/f'{case_id}.{arm}.r1.json').read_text())
            assert 'result' in record,(case_id,arm)
            outputs+=1
    review_dir=RUN/'review'
    mapping=json.loads((review_dir/'mapping.json').read_text())
    reviews=0
    for case_id in case_ids:
        record=json.loads((review_dir/f'{case_id}.model-review.json').read_text())
        assert record['source']=='same-model-separate-context'
        assert set(record['review']['ratings'])==set('ABC')
        assert set(mapping[case_id])==set('ABC')
        for rating in record['review']['ratings'].values():
            assert all(rating.get(field) is None or type(rating[field]) is bool for field in FIELDS)
            assert rating.get('reason')
        reviews+=1
    summary=json.loads((RUN/'summary.json').read_text())
    assert summary['human_review_status']=='deferred_by_user_2026-10-22'
    assert not summary['human_review_available']
    report=(RUN/'report.md').read_text()
    assert '不能据单次30题结果认定' in report and '真人复核列为后续工作' in report
    result={'frozen_source_files_verified':len(manifest['frozen_files']),
            'cases':len(case_ids),'generation_records':outputs,'model_reviews':reviews,
            'human_review_status':summary['human_review_status'],
            'recovery_is_independent_repeat':False,'passed':True}
    target=ROOT/'docs/delivery/evidence/course-artifacts.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
