"""Render an offline blinded review form. Ratings start empty, never model-filled."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).parent
TEMPLATE=HERE/'runs/recovered/review/human.template.json'


def main():
    template=Path(sys.argv[1]) if len(sys.argv)>1 else TEMPLATE
    data=json.loads(template.read_text())
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>匿名人工复核 · 数学作业智能体</title>
<style>body{font:15px/1.8 "PingFang SC","Microsoft YaHei",sans-serif;max-width:1050px;margin:40px auto;padding:0 22px;background:#f3f2ef;color:#333}h1,h2{color:#b70031}section{background:white;border:1px solid #e5dcde;padding:22px;margin:24px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;background:#faf8f8;padding:12px}label{display:block;margin:12px 0}input,textarea,select{font:inherit;padding:8px;border:1px solid #d6c9cd}textarea{display:block;width:95%;min-height:80px}.ratings{display:flex;gap:16px;flex-wrap:wrap}.ratings label{font-size:12px}.ratings select{display:block;font-size:12px}button{background:#b70031;color:white;border:0;padding:12px 22px;cursor:pointer;position:sticky;bottom:18px}summary{cursor:pointer}article{border-top:1px solid #eee;padding:18px 0}small{color:#76686d}</style>
<h1>匿名人工复核</h1><p>请先独立检查原题及学生过程，再比较 A/B/C。材料不显示条件标签；不要查看 mapping.json。题目为项目合成案例，评分用于课程实验，不评价真实学生能力。</p>
<p>这是<strong>人工填写</strong>的空表。同模型辅助评分不在此表中。可以只复核部分案例；未阅读的条目保持空白。</p>
<label>评审姓名 <input id="name" autocomplete="name"></label><label>评审身份（如数学教师／课程同学） <input id="role"></label>
<div id="cases"></div><button id="export">导出已填写的人工评分</button><p id="status" role="status"></p>
<script id="payload" type="application/json">PAYLOAD</script><script>
const data=JSON.parse(document.getElementById('payload').textContent);
const fields={math_correct:'数学正确',first_error_correct:'首错定位',mode_obeyed:'模式遵守',grounded:'有据不编造',teaching_useful:'反馈有用'};
function el(tag,text){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;}
for(const item of data.cases){const sec=el('section');sec.append(el('h2',item.packet.case_id));sec.append(el('pre',JSON.stringify(item.packet.input,null,2)));
for(const slot of ['A','B','C']){const article=el('article');article.append(el('h3','回答 '+slot));article.append(el('pre',item.packet.answers[slot]?.reply||'没有有效回答'));
const details=el('details');details.append(el('summary','完整结构化输出（提示模式也检查隐藏字段）'));details.append(el('pre',JSON.stringify(item.packet.answers[slot],null,2)));article.append(details);
const row=el('div');row.className='ratings';for(const [field,title] of Object.entries(fields)){const label=el('label',title);const select=el('select');for(const [value,text] of [['','未填写'],['true','通过'],['false','不通过'],['na','不适用']]){const op=el('option',text);op.value=value;select.append(op);}select.onchange=()=>{item.ratings[slot][field]=select.value==='true'?true:select.value==='false'?false:null;};label.append(select);row.append(label);}article.append(row);
const label=el('label','评分依据（指出具体步骤或措辞）');const reason=el('textarea');reason.oninput=()=>{item.ratings[slot].reason=reason.value;};label.append(reason);article.append(label);sec.append(article);}document.getElementById('cases').append(sec);}
document.getElementById('export').onclick=()=>{data.reviewer_name=document.getElementById('name').value.trim();data.reviewer_role=document.getElementById('role').value.trim();data.reviewed_at=new Date().toISOString();if(!data.reviewer_name||!data.reviewer_role){document.getElementById('status').textContent='请填写真实评审人和身份。';return;}const count=data.cases.reduce((n,c)=>n+Object.values(c.ratings).filter(r=>r.reason.trim()&&Object.keys(fields).some(k=>typeof r[k]==='boolean')).length,0);if(!count){document.getElementById('status').textContent='请至少实际复核一份回答并填写依据。';return;}const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=el('a');a.href=url;a.download='human.completed.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);document.getElementById('status').textContent='已导出 '+count+' 份已填写评分；请交回项目进行校验和汇总。';};
</script></html>'''.replace('PAYLOAD',payload)
    target=template.with_suffix('.html');target.write_text(html)
    print(target)


if __name__=='__main__':main()
