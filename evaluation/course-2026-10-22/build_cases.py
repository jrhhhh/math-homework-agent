"""One-time authored course evaluation cases, never passed with gold to producers."""
import json
from pathlib import Path

HERE=Path(__file__).parent
cases=[]
gold=[]


def add(mode, problem='', solution='', draft='', expected='', first_error=None, note=''):
    cid=f'C{len(cases)+1:02}'
    cases.append({'id':cid,'input':{'mode':mode,'problem':problem,'solution':solution,'draft':draft,'grade_level':'高中','request':''}})
    gold.append({'id':cid,'expected':expected,'first_error_step':first_error,'rationale':note})


add('solve','解实数方程 √(3x+4)=x。',expected='x=4',note='x≥0，平方得(x-4)(x+1)=0，排除-1。')
add('solve','求函数 f(x)=ln(7-2x)+√(x+3) 的定义域。',expected='[-3,7/2)',note='x≥-3 且 x<7/2。')
add('solve','解不等式 (x-3)/(x+2)≥0。',expected='(-∞,-2)∪[3,+∞)',note='-2 无定义，3 可以取。')
add('solve','已知 f(x)=x²-4ax+5 在闭区间 [1,3] 上单调递增，求实数 a 的范围。',expected='a≤1/2',note='f′=2x-4a，区间左端导数非负即可；等号时函数仍严格递增。')
add('solve','在 0≤x<2π 内解 sin(2x)=cos(x)。',expected='π/6,π/2,5π/6,3π/2',note='cos x(2sin x-1)=0，两个因子分别求解。')
add('solve','等比数列首项为3，前三项和为21，公比为实数，求全部公比。',expected='q=2 或 q=-3',note='q²+q-6=0，不预设公比正数。')
add('solve','袋中有3个红球和2个蓝球，无放回随机取2个，已知至少取到1个红球，求两球均红的条件概率。',expected='1/3',note='条件样本9种，两红3种。')
add('solve','向量 a=(2,-1)，b=(t,4)。若 a 与 b 垂直，求 t。',expected='t=2',note='数量积2t-4=0。')
add('solve','求实数 x 满足 x≥-1 时，x²-4x+7 的最小值及取得最小值的 x。',expected='最小值3，x=2',note='配方(x-2)²+3，顶点在定义域内。')
add('solve','三角形 ABC 中 AB=5，AC=7，∠BAC=60°，求 BC。',expected='√39',note='余弦定理25+49-35=39。')

add('check','在实数范围内解 x(x-5)=0。','两边除以 x，得到 x-5=0。\n所以唯一的解为 x=5。',expected='incorrect',first_error=1,note='除以x漏掉x=0。')
add('check','解实数方程 √(x+6)=x。','平方得到 x+6=x²。\n因式分解得 x=3 或 x=-2。\n两个根都满足原方程。',expected='incorrect',first_error=3,note='平方求候选根合法；-2代回不成立，首错在第3行。')
add('check','证明：若实数 a,b 满足 a+b=6，则 ab≤9。','由 (a-b)²≥0，得 (a+b)²≥4ab。\n代入 a+b=6，得 36≥4ab，所以 ab≤9。',expected='correct',note='无正数前提也成立，不能错用基本不等式条件否定。')
add('check','解不等式 (x+1)(x-4)>0。','令 y=x-3/2，则原式等于 y²-25/4。\n所以 y<-5/2 或 y>5/2。\n得到 x<-1 或 x>4。',expected='correct',note='平移后平方差方法有效。')
add('check','已知 a>0，证明 a+4/a≥4。','因为 a>0，故 (√a-2/√a)²≥0。\n展开得到 a+4/a-4≥0。\n所以 a+4/a≥4，当且仅当 a=2 时等号成立。',expected='correct',note='等号平方项为零给a=2。')
add('check','已知事件 A、B 互斥，P(A)=0.2，P(B)=0.3，求 P(A∩B)。','因为 A、B 互斥，所以 A、B 独立。\n故 P(A∩B)=0.2×0.3=0.06。',expected='incorrect',first_error=1,note='互斥非独立，交集概率0。')
add('check','解实数方程 |x-2|=3。','当 x≥2 时，x-2=3，得 x=5。\n当 x<2 时，2-x=3，得 x=-1。\n因此解集为 {-1,5}。',expected='correct',note='分类穷尽且候选满足分支条件。')
add('check','已知 a₁=2，且对所有正整数 n，aₙ₊₁-aₙ=3，求 aₙ。','由相邻两项差为3，得到 aₙ=3n+2。\n所以 a₁=5。',expected='incorrect',first_error=1,note='首项索引，aₙ=2+3(n-1)=3n-1。')
add('hint','解实数方程 (x-4)(x+2)=0。','两边约去 x+2，得到 x-4=0。\n所以只有 x=4。',expected='单提示，不泄露全部根',first_error=1,note='提示约去的因子能否为0，不直接补全解集。')
add('hint','解实数不等式 -3x>12。','两边除以 -3，得 x>-4。',expected='单提示，不直接给最终不等式',first_error=1,note='提示负数乘除对不等号方向的影响。')
add('hint','正实数 x 满足 x+9/x=10，求 x。','两边乘以 x，得到 x²-10x+9=0。\n我只找到了 x=1，觉得没有别的解。',expected='单提示，不泄露另一个根',first_error=2,note='提示二次式因式分解与根的完整性。')
add('hint','数列 aₙ=1/[n(n+1)]，求前 n 项和。','aₙ=1/n-1/(n+1)。\n所以前 n 项和为 1-1/n。',expected='单提示，不直接给完整求和式',first_error=2,note='提示列出前几项查看最后未抵消的一项。')
add('answer_check','解实数方程 x²=16。','x=4。',expected='answer_only 或 incorrect；只核对漏解，不虚构过程',note='只有最终答案，不推断使用了开方或约分。')
add('answer_check','已知 a₁=4，aₙ₊₁=aₙ+2，求 a₅。','a₅=12。',expected='answer_only 或 correct；不虚构过程',note='结果正确但未提供过程。')

add('draft',draft='左栏顶部标了第1题，下面每步单独一行；右栏顶部标了第2题，两栏之间画了竖线。第2题末尾四行挤在一起，底部没有留白。',expected='六维观察；引用右栏末尾四行密集与底部留白；不判数学对错',note='只提供版面，不能假定计算内容。')
add('draft',draft='纸的左上角是一个三角形草图，三个顶点有字母标记；图右边有两条算式，行距清楚；左下角旧值被一条线划掉，新值写在旁边并圈起来。',expected='六维观察；肯定图形标注与清晰划改；不根据未给字符判断计算',note='多路径等未观察维度应说明证据不足。')
add('draft',draft='纸面没有题号，中间有两片算式，它们之间没有空白或分隔线；左片末尾画箭头指向右片顶部，右片旁边写了方法二。纸张下方留有约四分之一空白。',expected='区分多方法和多题的不确定性；保留留白优点',note='不能据两片算式断定两道题。')
add('draft',draft='只有纸张中间的一小块内容：一行算式，下面一个结果框。照片其余位置被裁掉，看不到边距、题号或划改。',expected='承认证据不足；不补想其余版面；提供一个可执行动作',note='短草稿不支持长期习惯标签。')
add('draft',draft='顶部写了一个题号，随后分成甲、乙、丙三个有编号的小区域；乙区有两次划改，丙区的图没有点名；纸面右侧留着一条空栏，但没有检验标记。',expected='关联乙区划改、丙区缺标注与右侧空栏；不判推导',note='是否一题多问不能断言。')
add('draft',draft='从左上写到右下，全页基本写满；中间有两处新值直接覆盖旧值，辨别不出先后；几条不同方向的箭头交叉。没有图形，没有明显分区或题号。',expected='对应覆盖旧值、交叉箭头、无分区；不给学生贴能力标签',note='下一题动作具体且不要求周期计划。')

if __name__=='__main__':
    for name, rows in [('cases.jsonl',cases),('gold.jsonl',gold)]:
        (HERE/name).write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows))
    print(f'{len(cases)} cases written')
