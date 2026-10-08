"""固定案例数学核验；不是自动模型评测，不证明任意题目可靠性。"""
from fractions import Fraction as F
from pathlib import Path
import json
import math

checks = []


def check(name, condition, scope):
    if not condition:
        raise AssertionError(name)
    checks.append(dict(name=name, passed=True, scope=scope))


check('H01 正弦两解', all(math.isclose(math.sin(x), 0.5, abs_tol=1e-12)
      for x in (math.pi/6, 5*math.pi/6)), '候选角数值代入，不代替解集完备性证明')
check('H02 除法漏解', all(math.isclose(math.sin(2*x), math.sin(x), abs_tol=1e-12)
      for x in (0, math.pi/3, math.pi, 5*math.pi/3)), '四个候选角代入；穷尽性由因式分解和区间说明')
check('H03 椭圆参数', 3**2-2**2 == 5 and F(5,9) < 1,
      '焦距平方和离心率平方核验')
check('H04 抛物线焦点', F(4,2) == 2 and F(2,2) == 1,
      'y²=2px约定下p与焦点横坐标换算')
check('H05 联立退化', 1-1 == 0 and -2*(-1)-1 == 1
      and (-1)**2-0**2 == 1 and 0 == -1+1,
      '二次项抵消，一次方程候选交点代回两原式')
check('H06 驻点非极值', (-1)**3 < 0 < 1**3 and 3*0**2 == 0,
      '计算线索；任意邻域无极值由x³左右符号的一般推导说明')
samples = [F(21,10), F(3), F(10)]
check('H07 下界不可达', all(x+1/x > F(5,2)
      and x+1/x-F(5,2) == (2*x-1)*(x-2)/(2*x) for x in samples)
      and F(2)+F(1,2) == F(5,2),
      '有限样本及边界表达式；全区间正性和逼近由代数与连续性说明')
check('H08 首项修正', 1**2+1 == 2 and all(
      2+sum(2*k-1 for k in range(2,n+1)) == n*n+1 for n in range(1,21)),
      '前20项前缀和核验，不代替一般望远镜求和推导')
check('H09 公比为1', all(sum([2]*n) == 2*n for n in range(1,21)),
      '前20个部分和，通式来自n个常数2相加')
check('H11 互斥非独立', len(set((1,3,5)) & set((2,4,6))) == 0
      and F(3,6)*F(3,6) == F(1,4), '有限样本空间精确枚举')
check('H12 正确数列', 2*1+1 == 3 and all(
      (2*(n+1)+1)-(2*n+1) == 2 and sum(2*k+1 for k in range(1,n+1)) == n*(n+2)
      for n in range(1,21)), '前20项与和式；一般证明依等差公式')
result = dict(passed_groups=len(checks), checks=checks,
              limitation='固定计算事实核验，不是诊断模型准确率或独立盲测结果')
content = json.dumps(result, ensure_ascii=False, indent=2)+'\n'
Path(__file__).with_name('高中题型计算证据.json').write_text(content)
print(content)
