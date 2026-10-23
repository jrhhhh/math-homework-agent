"""Version-bound evidence aggregation; no mathematical judgment is performed here."""
import hashlib
import json
import sys


STATES = ('unsubmitted', 'pending', 'unavailable', 'binding_changed',
          'needs_input', 'correct', 'incorrect', 'gap', 'answer_only')


def summarize(items):
    rows = []
    for item in items:
        sub = item.get('submission')
        row = {key: item[key] for key in ('id', 'problem', 'objective')}
        row.update(state='unsubmitted', submission_id=None, revision=None, version=None,
                   first_error=None)
        if sub:
            row.update(submission_id=sub['id'], revision=sub['revision'], version=sub['version'])
            data = sub['data']
            if data.get('problem') != item['problem'] or data.get('source') != 'student' or data.get('grade_level') != '高中':
                row['state'] = 'binding_changed'
            elif sub['state'] in ('queued', 'running'):
                row['state'] = 'pending'
            elif sub['state'] != 'ready' or not sub.get('result') or sub['result'].get('status') != 'ready':
                row['state'] = 'unavailable'
            elif data.get('mode') == 'answer_check':
                row['state'] = 'answer_only'
            elif data.get('mode') not in ('check', 'full_correction'):
                row['state'] = 'needs_input'
            else:
                result = sub['result'].get('output', {}).get('result') or {}
                judgment = result.get('judgment')
                row['state'] = judgment if judgment in ('correct', 'incorrect', 'gap', 'answer_only') else 'needs_input'
                if row['state'] in ('incorrect', 'gap'):
                    row['first_error'] = result.get('first_error')
        rows.append(row)
    counts = {key: sum(row['state'] == key for row in rows) for key in STATES}
    fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {'items': rows, 'counts': counts, 'evidence_version': fingerprint,
            'scope': '仅本机任务当前提交的模型诊断；按任务项计数，不代表班级比例或长期掌握程度。'}


if __name__ == '__main__':
    with open(sys.argv[1], encoding='utf-8') as stream:
        payload = json.load(stream)
    print(json.dumps(summarize(payload['items']), ensure_ascii=False, indent=2))
