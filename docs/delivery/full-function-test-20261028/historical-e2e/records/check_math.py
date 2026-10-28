"""独立校核本次人工构造题目的标准解；不检查模型输出。"""
import json
from pathlib import Path
import sympy as s
x=s.symbols('x',real=True);domain=s.Interval.Ropen(0,2*s.pi)
expected=[s.FiniteSet(0,s.pi/3,s.pi,5*s.pi/3),s.FiniteSet(0,2*s.pi/3,s.pi,4*s.pi/3)]
rows=[]
for coefficient,answer in zip((1,-1),expected):
    expr=s.sin(2*x)-coefficient*s.sin(x)
    solved=s.solveset(expr,x,domain=domain)
    assert solved==answer,(solved,answer)
    residuals=[str(s.simplify(expr.subs(x,value))) for value in solved]
    assert all(value=='0' for value in residuals)
    rows.append({'equation':str(s.Eq(s.sin(2*x),coefficient*s.sin(x))),'domain':'[0,2π)',
                 'solveset':str(solved),'all_substitution_residuals':residuals,'matches_expected':True})
output={'tool':'SymPy '+s.__version__,'scope':'符号解集与逐一代入；不自动审查模型推理','cases':rows}
Path(__file__).with_name('math-check.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(output,ensure_ascii=False))
