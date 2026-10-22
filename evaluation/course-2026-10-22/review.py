"""Blinded model-assisted review and genuine human-review packet support."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app.model import generate, parse_json  # noqa: E402

HERE=Path(__file__).parent
FIELDS=('math_correct','first_error_correct','mode_obeyed','grounded','teaching_useful')


def packets(run_dir, require_complete=True):
    destination=run_dir/'review';destination.mkdir(exist_ok=True)
    cases=[json.loads(line) for line in (HERE/'cases.jsonl').read_text().splitlines()]
    mapping={}
    ready=[]
    for case in cases:
        if any(not (run_dir/f'{case["id"]}.{arm}.r1.json').exists() for arm in ('baseline','skill','skill_gates')):
            if require_complete:raise ValueError(f'尚未完成 {case["id"]} 的三组输出')
            continue
        outputs=[]
        for arm in ('baseline','skill','skill_gates'):
            path=run_dir/f'{case["id"]}.{arm}.r1.json'
            if not path.exists():
                raise ValueError(f'尚未完成 {path.name}')
            result=json.loads(path.read_text()).get('result',{})
            outputs.append((arm,result.get('output')))
        rng=random.Random(int(hashlib.sha256(case['id'].encode()).hexdigest(),16))
        rng.shuffle(outputs)
        mapping[case['id']]={chr(65+i):arm for i,(arm,_) in enumerate(outputs)}
        packet={'case_id':case['id'],'input':case['input'],
                'answers':{chr(65+i):answer for i,(_,answer) in enumerate(outputs)}}
        (destination/f'{case["id"]}.packet.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2))
        ready.append(case)
    (destination/'mapping.json').write_text(json.dumps(mapping,indent=2))
    # Small genuine-human bundle; never prefill ratings with a model's scores.
    sample=('C01','C05','C07','C11','C12','C13','C17','C19','C23','C26')
    human={'reviewer_name':None,'reviewer_role':None,'reviewed_at':None,'source':'human',
           'instructions':'先独立检查原题与学生过程，再逐条评估A/B/C。只填你实际阅读的条目；不适用填null，布尔值必须有理由。不要查看mapping.json。',
           'cases':[]}
    for cid in sample:
        if not (destination/f'{cid}.packet.json').exists():continue
        packet=json.loads((destination/f'{cid}.packet.json').read_text())
        human['cases'].append({'packet':packet,'ratings':{slot:{**{f:None for f in FIELDS},'reason':''} for slot in 'ABC'}})
    target=destination/'human.template.json'
    if len(ready)==len(cases) and not target.exists():target.write_text(json.dumps(human,ensure_ascii=False,indent=2))
    return ready


def assisted(run_dir, partial=False):
    cases=packets(run_dir, require_complete=not partial)
    for i,case in enumerate(cases,1):
        destination=run_dir/'review'/f'{case["id"]}.model-review.json'
        if destination.exists():continue
        packet=(run_dir/'review'/f'{case["id"]}.packet.json').read_text()
        prompt='''你是独立上下文的高中数学与教学反馈核验者。不调用工具，不访问文件。
你只能看到原始输入与随机顺序的A/B/C回答，不知道哪个条件生成。
先自己求解/核验原题及学生过程，再分别评价全部三个回答。不能以格式长度或措辞偏好评分。
完整输出也要检查，不只看reply。hint模式任何字段泄露完整答案都算mode_obeyed=false；
first_error中指出需检查的步骤本身不是答案泄露，但直接写出缺失根/完整答案属于泄露。
只有最终答案时，不得编造学生推理；有效但非常规解法不能强判错误。
草稿只评版面依据，不得从未提供的字符推断数学计算或长期能力。
math_correct对草稿为null；first_error_correct对求解、草稿、仅答案与无首错要求的提示可为null。
teaching_useful评反馈是否具体且帮助下一步，不评是否文采好。
只输出JSON：{"independent_check":"自己的可复核结论与依据", "ratings":{
"A":{"math_correct":true或false或null,"first_error_correct":true或false或null,
"mode_obeyed":true或false,"grounded":true或false,"teaching_useful":true或false,"reason":"具体依据"},
"B":同样字段,"C":同样字段}}。
材料：\n'''+packet
        response=generate(prompt)
        review=parse_json(response['raw'])
        if set(review.get('ratings',{})) != set('ABC'):
            raise ValueError('评审缺少回答')
        for rating in review['ratings'].values():
            if any(rating.get(f) is not None and type(rating[f]) is not bool for f in FIELDS):
                raise ValueError('评分必须为布尔值或null')
            if not rating.get('reason'):
                raise ValueError('缺少评审依据')
        destination.write_text(json.dumps({'source':'same-model-separate-context','prompt':prompt,
                                           'response':response,'review':review},ensure_ascii=False,indent=2))
        print(f'{i}/{len(cases)} {case["id"]} reviewed',flush=True)


def validate_human(path):
    data=json.loads(path.read_text())
    if data.get('source')!='human' or not all(data.get(k) for k in ('reviewer_name','reviewer_role','reviewed_at')):
        raise ValueError('需要真实评审人姓名、身份与时间；空模板不算人工评审')
    n=0
    for case in data['cases']:
        for rating in case['ratings'].values():
            if not rating.get('reason'):continue
            if any(rating.get(f) is not None and type(rating[f]) is not bool for f in FIELDS):
                raise ValueError('人工评分必须为布尔值或null')
            if all(rating.get(f) is None for f in FIELDS):
                raise ValueError('有理由但没有实际评分')
            n+=1
    if not n:raise ValueError('没有已完成的人工评分')
    print(f'可读取 {n} 份真实人员提交的评分；脚本不能认证评审人身份。')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=('packets','assisted','human'))
    parser.add_argument('--run',type=Path,default=HERE/'runs'/'initial')
    parser.add_argument('--file',type=Path)
    parser.add_argument('--watch',action='store_true',help='Incrementally review complete A/B/C triples, up to one hour')
    args=parser.parse_args()
    if args.command=='human':validate_human(args.file)
    elif args.command=='assisted':
        if args.watch:
            started=time.monotonic()
            while time.monotonic()-started<3600:
                assisted(args.run,partial=True)
                if len(list((args.run/'review').glob('C*.model-review.json')))==30:break
                time.sleep(10)
        else:assisted(args.run)
    else:packets(args.run)
