"""Deterministic, bounded high-school math visualizations (no generated scripts)."""
import math

TEMPLATES={'quadratic','unit_circle','derivative'}


def number(data,key,default,low,high):
    value=data.get(key,default)
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError(f'{key} 必须是 {low} 到 {high} 的有限数。')
    return float(value)


def evaluate(data):
    kind=data.get('template')
    if kind not in TEMPLATES:raise ValueError('请选择支持的数学活动模板。')
    if kind=='unit_circle':
        angle=number(data,'angle',45,-360,360);radians=math.radians(angle)
        x,y=math.cos(radians),math.sin(radians)
        return {'template':kind,'point':[x,y],'angle':angle,'identity':x*x+y*y,
                'formula':'P=(cos θ, sin θ)，cos²θ+sin²θ=1','question':'改变角度，观察横纵坐标的符号与零点。这个观察能支持什么结论？',
                'scope':'数值图示用于观察；不是一般性数学证明。'}
    if kind=='quadratic':
        a=number(data,'a',1,-3,3);b=number(data,'b',0,-5,5);c=number(data,'c',0,-5,5)
        points=[[x/20,a*(x/20)**2+b*(x/20)+c] for x in range(-80,81)]
        vertex=None if a==0 else [-b/(2*a),c-b*b/(4*a)]
        return {'template':kind,'points':points,'vertex':vertex,'parameters':{'a':a,'b':b,'c':c},
                'formula':f'y={a:g}x²+{b:g}x+{c:g}',
                'question':'一次只改变一个参数，说明开口、对称轴或位置发生了什么变化。a=0 时还是二次函数吗？',
                'scope':'a=0 时按一次或常数函数显示，不计算二次函数顶点。'}
    x0=number(data,'x0',1,-2,2);h=number(data,'h',1,-2,2)
    f=lambda x:x*x
    slope=2*x0+h if h!=0 else 2*x0
    points=[[x/20,f(x/20)] for x in range(-80,81)]
    line=[[x,f(x0)+slope*(x-x0)] for x in (-4,4)]
    return {'template':kind,'points':points,'line':line,'point':[x0,f(x0)],'second_point':[x0+h,f(x0+h)],
            'slope':slope,'h':h,'x0':x0,'mode':'secant' if h!=0 else 'tangent_limit',
            'formula':'f(x)=x²；h≠0 时割线斜率=2x₀+h；导数 f′(x₀)=2x₀',
            'question':'让 h 从两侧趋近0，斜率接近什么值？h=0 的图示与直接用差商相除有什么区别？',
            'scope':'h=0 显示已知导数给出的切线，不把 0/0 当作有效差商。'}
