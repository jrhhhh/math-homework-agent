"""AST-to-SymPy arithmetic, with explicit scope and no eval/parse_expr.

Supported requests: substitute(left,right,variable,values) and
polynomial_identity(left,right,variable). A passed point check never establishes
solution completeness or the conditions of an entire mathematical problem.
"""
import ast
from datetime import datetime, timezone
import hashlib
import json
import re
import time


def parse(text, variable, sp, substitute=None):
    if not isinstance(text,str) or not 0 < len(text) <= 512:
        raise ValueError('表达式必须为1–512字的文本')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,15}',variable):
        raise ValueError('变量名非法')
    tree=ast.parse(text,mode='eval')
    if sum(1 for _ in ast.walk(tree))>100:
        raise ValueError('表达式过于复杂')
    symbol=sp.Symbol(variable,real=True)
    functions={'sqrt':sp.sqrt,'sin':sp.sin,'cos':sp.cos,'log':sp.log,'abs':sp.Abs}

    def visit(node, depth=0):
        if depth>16:raise ValueError('表达式嵌套过深')
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):
            if abs(node.value)>10**12:raise ValueError('常数超出允许范围')
            literal=ast.get_source_segment(text,node).replace('_','')
            exponent=re.search(r'[eE]([+-]?\d+)$',literal)
            if exponent and abs(int(exponent[1]))>100:raise ValueError('科学计数指数超出允许范围')
            return sp.Rational(str(node.value) if type(node.value) is int else literal)
        if isinstance(node,ast.Name):
            if node.id==variable:return symbol if substitute is None else substitute
            if node.id=='pi':return sp.pi
            raise ValueError('未允许的符号')
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            value=visit(node.operand,depth+1)
            return value if isinstance(node.op,ast.UAdd) else -value
        if isinstance(node,ast.BinOp):
            left,right=visit(node.left,depth+1),visit(node.right,depth+1)
            if isinstance(node.op,ast.Add):return left+right
            if isinstance(node.op,ast.Sub):return left-right
            if isinstance(node.op,ast.Mult):return left*right
            if isinstance(node.op,ast.Div):
                if right==0:raise ValueError('除数为零')
                return left/right
            if isinstance(node.op,ast.Pow):
                if not right.is_Integer or abs(right)>20:raise ValueError('幂指数必须为-20至20的整数')
                if isinstance(left,sp.Pow) and left.exp.is_Integer and abs(left.exp*right)>100:
                    raise ValueError('复合幂次数过高')
                if left.is_Rational:
                    numerator,denominator=left.as_numer_denom()
                    if max(int(numerator).bit_length(),int(denominator).bit_length())*abs(int(right))>4096:
                        raise ValueError('数值幂结果过大')
                return left**right
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in functions and len(node.args)==1 and not node.keywords:
            argument=visit(node.args[0],depth+1)
            if substitute is not None:
                if node.func.id=='sqrt' and argument.is_nonnegative is not True:
                    raise ValueError('实数平方根的被开方数必须非负')
                if node.func.id=='log' and argument.is_positive is not True:
                    raise ValueError('实数对数的真数必须为正')
            return functions[node.func.id](argument)
        raise ValueError('不允许的表达式语法')
    domain_sensitive=False
    for node in ast.walk(tree):
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Div):
            domain_sensitive |= any(isinstance(n,ast.Name) and n.id==variable for n in ast.walk(node.right))
        if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Pow):
            domain_sensitive |= isinstance(node.right,ast.UnaryOp) and isinstance(node.right.op,ast.USub)
        if isinstance(node,ast.Call):
            domain_sensitive |= any(isinstance(n,ast.Name) and n.id==variable for arg in node.args for n in ast.walk(arg))
    return visit(tree.body),symbol,domain_sensitive


def verify(request):
    started=time.monotonic()
    record={'request':request,'executed_at':datetime.now(timezone.utc).isoformat(),
            'engine':'sympy','status':'error','scope':''}
    try:
        import sympy as sp
        record['engine_version']=sp.__version__
        if not isinstance(request,dict):raise ValueError('核验请求必须为对象')
        if set(request)-{'kind','left','right','variable','values'}:raise ValueError('核验请求含未知字段')
        variable=request.get('variable','x')
        if not isinstance(variable,str):raise ValueError('变量必须为字符串')
        left,x,left_domain=parse(request.get('left'),variable,sp)
        right,_,right_domain=parse(request.get('right'),variable,sp)
        if request.get('kind')=='polynomial_identity':
            if left_domain or right_domain or not left.is_polynomial(x) or not right.is_polynomial(x):
                raise ValueError('只支持多项式恒等式，不自动取消分母条件')
            difference=sp.expand(left-right)
            record.update(status='passed' if difference==0 else 'failed', residual=str(difference),
                          scope='只验证请求中两个多项式恒等；不证明请求与原题等价或整题正确。')
        elif request.get('kind')=='substitute':
            values=request.get('values')
            if not isinstance(values,list) or not 1<=len(values)<=10:raise ValueError('候选值需为1–10项列表')
            checks=[]
            for value in values:
                value,_,_=parse(str(value),variable,sp)
                if value.free_symbols:raise ValueError('候选值不能含变量')
                # Evaluate the original AST at each point before symbolic cancellation.
                try:
                    lv,_,_=parse(request['left'],variable,sp,substitute=value)
                    rv,_,_=parse(request['right'],variable,sp,substitute=value)
                except (ValueError,ArithmeticError) as exc:
                    checks.append({'value':str(value),'passed':False,'error':str(exc)})
                    continue
                finite=lv.is_finite is True and rv.is_finite is True and lv.is_real is True and rv.is_real is True
                residual=sp.simplify(lv-rv) if finite else None
                checks.append({'value':str(value),'left':str(lv),'right':str(rv),
                               'residual':str(residual),'passed':bool(finite and residual==0)})
            record.update(status='passed' if all(c['passed'] for c in checks) else 'failed',checks=checks,
                          scope='仅代入所列候选值检查指定等式；不证明解集完备、区间条件或整个推导。')
        else:raise ValueError('核验类型非法')
    except ImportError:
        record['error']='未安装 sympy；没有执行数学核验。'
    except (ValueError,TypeError,SyntaxError,ArithmeticError) as exc:
        record['error']=str(exc)
    record['elapsed_seconds']=round(time.monotonic()-started,6)
    record['request_sha256']=hashlib.sha256(json.dumps(request,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return record


if __name__=='__main__':
    import sys
    result=verify(json.load(sys.stdin))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit({'passed':0,'failed':1,'error':2}[result['status']])
