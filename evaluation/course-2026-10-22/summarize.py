"""Aggregate recorded generations and reviews; never invent missing scores."""
from collections import defaultdict
import json
import math
from pathlib import Path

HERE=Path(__file__).parent
ARMS=('baseline','skill','skill_gates')
FIELDS=('math_correct','first_error_correct','mode_obeyed','grounded','teaching_useful')


def wilson(wins,n):
    if not n:return None
    z=1.96;p=wins/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [round(mid-half,4),round(mid+half,4)]


def summarize(directory):
    stats={arm:{'completed':0,'errors':0,'gate_passed':0,'first_attempt_passed':0,
                'repaired':0,'calls':0,'elapsed_seconds':0,'input_tokens':0,'output_tokens':0,
                'model_review':{},'human_review':{}} for arm in ARMS}
    failures=[]
    for path in sorted(directory.glob('C*.json')):
        record=json.loads(path.read_text());arm=record['arm'];row=stats[arm]
        if 'result' not in record:
            row['errors']+=1;failures.append({'file':path.name,'error':record.get('error')});continue
        row['completed']+=1;result=record['result'];attempts=result['attempts']
        row['gate_passed']+=int(result['status']=='ready')
        row['first_attempt_passed']+=int(bool(attempts) and all(g['exit_code']==0 for g in attempts[0]['gates']))
        row['repaired']+=int(result['status']=='ready' and len(attempts)>1)
        row['calls']+=len(attempts)
        for attempt in attempts:
            response=attempt['response'];row['elapsed_seconds']+=response.get('elapsed_seconds',0)
            for usage in response.get('usage',[]):
                row['input_tokens']+=usage.get('input_tokens',0);row['output_tokens']+=usage.get('output_tokens',0)
        if result['status']!='ready':failures.append({'file':path.name,'gates':attempts[-1]['gates']})
    mapping_path=directory/'review'/'mapping.json'
    mapping=json.loads(mapping_path.read_text()) if mapping_path.exists() else {}
    assisted=defaultdict(list);human=defaultdict(list)
    for path in (directory/'review').glob('C*.model-review.json'):
        data=json.loads(path.read_text())
        cid=path.name.split('.')[0]
        for slot,rating in data['review']['ratings'].items():assisted[mapping[cid][slot]].append(rating)
    human_path=directory/'review'/'human.completed.json'
    if human_path.exists():
        data=json.loads(human_path.read_text())
        if data.get('source')!='human' or not all(data.get(k) for k in ('reviewer_name','reviewer_role','reviewed_at')):
            raise ValueError('人工评分缺少真实评审声明')
        for case in data['cases']:
            for slot,rating in case['ratings'].items():
                if rating.get('reason'):human[mapping[case['packet']['case_id']][slot]].append(rating)
    for arm,row in stats.items():
        row['elapsed_seconds']=round(row['elapsed_seconds'],3)
        for source,ratings in [('model_review',assisted[arm]),('human_review',human[arm])]:
            for field in FIELDS:
                values=[r[field] for r in ratings if type(r.get(field)) is bool]
                row[source][field]={'passed':sum(values),'n':len(values),'wilson95':wilson(sum(values),len(values))}
    human_available=any(human.values())
    summary={'arms':stats,'failures':failures,'human_review_available':human_available,
             'human_review_status':'available' if human_available else 'deferred_by_user_2026-10-22',
             'scope':'Saved single-run course cases; model-assisted review is same-model separate-context, not human or formal verification. Gate pass is not mathematical accuracy.',
             'cost':'Token usage recorded; no verified monetary billing data available.'}
    (directory/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    lines=['# 三组真实运行结果','',
           '| 条件 | 已完成/30 | 最终门通过 | 首次门通过 | 修正成功 | 模型调用数 | 累计调用秒数 |',
           '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for arm,row in stats.items():
        lines.append(f'| {arm} | {row["completed"]} | {row["gate_passed"]} | {row["first_attempt_passed"]} | {row["repaired"]} | {row["calls"]} | {row["elapsed_seconds"]} |')
    lines+=['','累计秒数为各调用时间之和，不是并发实验的墙钟时间。','',
            '## 匿名模型辅助复核','',
            '| 条件 | 数学正确 | 首错定位 | 模式遵守 | 有据不编造 | 教学可用 |',
            '| --- | ---: | ---: | ---: | ---: | ---: |']
    for arm,row in stats.items():
        metrics=[f'{row["model_review"][f]["passed"]}/{row["model_review"][f]["n"]}' for f in FIELDS]
        lines.append('| '+arm+' | '+' | '.join(metrics)+' |')
    lines+=['','不适用项不进分母；0/0 表示尚无评分。逐项 Wilson 95% 区间见 summary.json。',
            '同一模型不同上下文核验，不能作为人类、异模型或形式化验证。',
            '','## 未通过项与解释','',
            '| 案例 | 条件 | 门 | 含义 |',
            '| --- | --- | --- | --- |']
    for failure in failures:
        name=failure['file'];case_id=name.split('.')[0];arm=name.split('.')[1] if '.' in name else ''
        gates=failure.get('gates',[])
        labels=[]
        for gate in gates:
            if gate.get('exit_code')!=0:
                labels.append(gate['gate'])
        detail='；'.join(labels) or failure.get('error','模型调用失败')
        if case_id=='C25':detail='多题草稿走单题分析，严格门要求先分区并确认；当前工作台已修正路由，冻结结果保留'
        elif case_id=='C28':detail='草稿卡使用了评分措辞，越界审计拒绝'
        lines.append(f'| {case_id} | {arm} | {"、".join(labels) or "失败"} | {detail} |')
    lines+=['','本次最终门通过数差异（29/30 对 28/30）只来自 C28 基线输出被措辞门拒绝；三组模型辅助盲评汇总相同，不能据单次30题结果认定 Skill 带来准确率增益。C25 三组都失败，说明多题版面入口需要先做分区确认。重跑输出是对初始服务中断项的恢复，不是独立重复实验。',
            '','## 人工复核','',
            '已读取真实人员提交的评分。' if human_available else '用户于2026-10-22明确选择本次先交付模型辅助评测，真人复核列为后续工作。已提供匿名10题复核包，空模板不计分。',
            '','## 证据范围','',summary['scope'],summary['cost'],
            '每条件一次，案例为人工编写；不据此声称普遍准确率或稳定增益。']
    (directory/'report.md').write_text('\n'.join(lines)+'\n')
    return summary


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--run',type=Path,default=HERE/'runs'/'initial')
    args=parser.parse_args();print(json.dumps(summarize(args.run),ensure_ascii=False,indent=2))
