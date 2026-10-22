"""Independent symbolic checks of authored mathematical gold, not model behavior."""
import json
from pathlib import Path
import sympy as s

HERE=Path(__file__).parent
x=s.Symbol('x',real=True);a=s.Symbol('a',real=True);q=s.Symbol('q',real=True)
checks=[]


def check(cid, expression, expected, note):
    if expression != expected:
        raise AssertionError(f'{cid}: {expression} != {expected}')
    checks.append({'id':cid,'actual':str(expression),'expected':str(expected),'passed':True,'scope':note})


check('C01',s.solveset(s.sqrt(3*x+4)-x,x,domain=s.S.Reals),s.FiniteSet(4),'原无理方程实解，不是平方后候选集')
check('C02',s.Intersection(s.Interval(-3,s.oo),s.Interval.open(-s.oo,s.Rational(7,2))),s.Interval.Ropen(-3,s.Rational(7,2)),'定义域由两项约束交集给出')
check('C03',s.solve_univariate_inequality((x-3)/(x+2)>=0,x,relational=False),s.Union(s.Interval.open(-s.oo,-2),s.Interval(3,s.oo)),'零分母排除，分子零点保留')
check('C04',s.solve_univariate_inequality(2-4*a>=0,a,relational=False),s.Interval(-s.oo,s.Rational(1,2)),'导数在[1,3]的最小值位于左端；该条件等价于递增')
check('C05',s.solveset(s.sin(2*x)-s.cos(x),x,domain=s.Interval.Ropen(0,2*s.pi)),s.FiniteSet(s.pi/6,s.pi/2,5*s.pi/6,3*s.pi/2),'原三角方程在指定半开区间的完整解集')
check('C06',s.solveset(3*(1+q+q*q)-21,q,domain=s.S.Reals),s.FiniteSet(-3,2),'保留负公比分支')
check('C07',s.Rational(s.binomial(3,2),s.binomial(5,2)-s.binomial(2,2)),s.Rational(1,3),'无放回组合计数的条件概率')
check('C08',s.solve(2*x-4,x),[2],'数量积为零')
check('C09',s.expand(x*x-4*x+7-((x-2)**2+3)),0,'配方恒等式；x=2在x≥-1中，平方项非负')
check('C10',s.sqrt(25+49-2*5*7*s.cos(s.pi/3)),s.sqrt(39),'余弦定理')
check('C11',s.solveset(x*(x-5),x,domain=s.S.Reals),s.FiniteSet(0,5),'除以x会遗漏的分支')
check('C12',s.solveset(s.sqrt(x+6)-x,x,domain=s.S.Reals),s.FiniteSet(3),'平方是求候选根的合法步骤；负候选在代回阶段舍去')
check('C13',s.expand(9-a*(6-a)-(a-3)**2),0,'差值是完全平方，对任意实数a成立')
check('C14',s.solve_univariate_inequality((x+1)*(x-4)>0,x,relational=False),s.Union(s.Interval.open(-s.oo,-1),s.Interval.open(4,s.oo)),'原不等式严格端点')
p=s.Symbol('p',positive=True)
check('C15',s.simplify((s.sqrt(p)-2/s.sqrt(p))**2-(p+4/p-4)),0,'正数条件下展开恒等式；等号p=2')
check('C17',s.solveset(s.Abs(x-2)-3,x,domain=s.S.Reals),s.FiniteSet(-1,5),'绝对值方程两分支')
check('C18',(3*s.Integer(1)-1),s.Integer(2),'首项锚点；公差3给一般式3n-1')
check('C19',s.solveset((x-4)*(x+2),x,domain=s.S.Reals),s.FiniteSet(-2,4),'供评审检查提示是否泄露，不交给作答者')
check('C20',s.solve_univariate_inequality(-3*x>12,x,relational=False),s.Interval.open(-s.oo,-4),'负数相除不等号变向')
check('C21',s.solveset(x*x-10*x+9,x,domain=s.S.Reals),s.FiniteSet(1,9),'两个正根均保留')
n=s.Symbol('n',positive=True,integer=True);k=s.Symbol('k',positive=True,integer=True)
check('C22',s.simplify(s.summation(1/(k*(k+1)),(k,1,n))-(1-1/(n+1))),0,'对任意正整数n的裂项求和')
check('C23',s.solveset(x*x-16,x,domain=s.S.Reals),s.FiniteSet(-4,4),'只有答案时指出不完整，不推断学生过程')
check('C24',s.Integer(4)+2*(5-1),s.Integer(12),'等差数列第五项')

if __name__=='__main__':
    result={'engine':'sympy','version':s.__version__,'checks':checks,
            'not_symbolic':['C16:互斥事件定义直接给交集为空、概率0','C25-C30:版面事实与教学建议需语义复核，不用数学计算伪装验证'],
            'limitation':'只核验本批数学真值与关键锚点，不是模型行为评测或整篇学生过程自动证明。'}
    target=HERE/'gold-verification.json';target.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(f'{len(checks)} symbolic checks passed')
