# -*- coding: utf-8 -*-
"""2024 年新高考Ⅰ卷数学（19 题）的 benchmark 案例与标准答案。

题面采用通行真题版本，不采用转录有误的版本。相对用户最初贴出的文本，以下
题面按通行真题修正：

- 第 2 题：z/(z-1)=1+i（不是 2/(z-1)）；
- 第 6 题：x<0 时为 -x²-2ax-a，x≥0 时为 e^x+ln(x+1)；
- 第 10 题：f(x)=(x-1)²(x-4)，B、D 选项按真题；
- 第 11 题：B 为 (2√2,0)，D 为 y0≤4/(x0+2)；
- 第 12 题：|AB|=10（不是 12）；
- 第 16(2) 题：条件为 △ABP 的面积为 9，答案有两条直线；
- 第 17–19 题：按真题的标准题面（(2,13)-可分数列、P_m>1/8 等）。

新增案例均为 development，不构成独立 test 留出集。solution 夹具在
fixtures/solutions/2024_xgk1/。
"""

_SOL = "fixtures/solutions/2024_xgk1"

EXAM_CASES = [
    {
        "case_id": "MATH-33",
        "subset": "answer_core",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "已知集合 A={x | -5<x³<5}，B={-3,-1,0,2,3}，求 A∩B。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "set", "inequality", "cube_root"],
        "_source_file": f"{_SOL}/q01.json",
    },
    {
        "case_id": "MATH-34",
        "subset": "answer_core",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "若 z/(z-1)=1+i，求复数 z。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "complex_number", "equation"],
        "_source_file": f"{_SOL}/q02.json",
    },
    {
        "case_id": "MATH-35",
        "subset": "answer_core",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "已知向量 a=(0,1)，b=(2,x)，若 b⊥(b-4a)，求 x。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "vector", "perpendicular", "dot_product"],
        "_source_file": f"{_SOL}/q03.json",
    },
    {
        "case_id": "MATH-36",
        "subset": "answer_core",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "已知 cos(α+β)=m，tanα tanβ=2，求 cos(α-β)。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "trigonometry", "identity", "cosine"],
        "_source_file": f"{_SOL}/q04.json",
    },
    {
        "case_id": "MATH-37",
        "subset": "answer_core",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "已知圆柱和圆锥的底面半径相等，侧面积相等，且它们的高均为 √3，求圆锥的体积。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "solid_geometry", "cylinder", "cone", "volume"],
        "_source_file": f"{_SOL}/q05.json",
    },
    {
        "case_id": "MATH-38",
        "subset": "verification_discipline",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "已知函数 f(x)={ -x²-2ax-a, x<0; e^x+ln(x+1), x≥0 } 在 R 上单调递增，"
                             "求实数 a 的取值范围。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "piecewise_function", "monotonicity", "parameter"],
        "_source_file": f"{_SOL}/q06.json",
    },
    {
        "case_id": "MATH-39",
        "subset": "verification_discipline",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "当 x∈[0,2π] 时，曲线 y=sin x 与 y=2sin(3x-π/6) 的交点个数为多少？",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "trigonometry", "equation", "intersection_count"],
        "_source_file": f"{_SOL}/q07.json",
    },
    {
        "case_id": "MATH-40",
        "subset": "verification_discipline",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "已知函数 f(x) 的定义域为 R，f(x)>f(x-1)+f(x-2)，且当 x<3 时 f(x)=x。"
                             "下列结论中一定正确的是：A. f(10)>100 B. f(20)>1000 "
                             "C. f(10)<1000 D. f(20)<10000。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "sequence", "recurrence", "inequality", "fibonacci"],
        "_source_file": f"{_SOL}/q08.json",
    },
    {
        "case_id": "MATH-41",
        "subset": "answer_core",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "为了解推动出口后的亩收入，从该种植区抽取样本，得到推动出口后亩收入的样本均值 "
                             "x̄=2.1，样本方差 s²=0.01。已知该种植区以往的亩收入 X~N(1.8,0.1²)，"
                             "假设推动出口后的亩收入 Y~N(x̄,s²)。判断：A. P(X>2)>0.2 "
                             "B. P(X>2)<0.5 C. P(Y>2)>0.2 D. P(Y>2)<0.8。"
                             "（若 Z~N(μ,σ²)，P(Z<μ+σ)≈0.8413）",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "normal_distribution", "probability"],
        "_source_file": f"{_SOL}/q09.json",
    },
    {
        "case_id": "MATH-42",
        "subset": "verification_discipline",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "设函数 f(x)=(x-1)²(x-4)，判断：A. x=3 是 f(x) 的极小值点 "
                             "B. 当 0<x<1 时，f(x)<f(x²) C. 当 1<x<2 时，-4<f(2x-1)<0 "
                             "D. 当 -1<x<0 时，f(2-x)>f(x)。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "derivative", "monotonicity", "extremum", "multiple_choice"],
        "_source_file": f"{_SOL}/q10.json",
    },
    {
        "case_id": "MATH-43",
        "subset": "answer_core",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "曲线 C 过坐标原点 O，C 上的点满足横坐标大于 -2，到点 F(2,0) 的距离与到定直线 "
                             "x=a(a<0) 的距离之积为 4。判断：A. a=-2 B. 点(2√2,0)在 C 上 "
                             "C. C 在第一象限内的点的纵坐标的最大值为 1 "
                             "D. 当(x0,y0)在 C 上时，y0≤4/(x0+2)。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "conic", "curve_equation", "inequality", "multiple_choice"],
        "_source_file": f"{_SOL}/q11.json",
    },
    {
        "case_id": "MATH-44",
        "subset": "answer_core",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "设双曲线 C: x²/a²-y²/b²=1 (a>0,b>0) 的左、右焦点分别为 F1、F2，"
                             "过 F2 作平行于 y 轴的直线交 C 于 A、B 两点，若 |F1A|=13，|AB|=10，"
                             "求 C 的离心率。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "hyperbola", "eccentricity", "focal_chord"],
        "_source_file": f"{_SOL}/q12.json",
    },
    {
        "case_id": "MATH-45",
        "subset": "answer_core",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "若曲线 y=e^x+x 在 x=0 处的切线也是曲线 y=ln(x+1)+a 的切线，求 a。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "derivative", "tangent_line", "common_tangent"],
        "_source_file": f"{_SOL}/q13.json",
    },
    {
        "case_id": "MATH-46",
        "subset": "answer_core",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "甲、乙两人各有四张卡片，甲的卡片上分别标有数字 1,3,5,7，乙的卡片上分别标有"
                             "数字 2,4,6,8。两人进行四轮比赛，每轮各自从自己持有的卡片中随机选一张，"
                             "数字大的人得 1 分，数字小的人得 0 分，然后各自弃掉此轮所选的卡片。"
                             "求四轮比赛后甲的总得分不小于 2 的概率。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "probability", "permutation", "enumeration"],
        "_source_file": f"{_SOL}/q14.json",
    },
    {
        "case_id": "MATH-47",
        "subset": "answer_core",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "记 △ABC 的内角 A、B、C 的对边分别为 a、b、c，已知 sin C=√2 cos B，"
                             "a²+b²-c²=√2 ab。(1) 求 B；(2) 若 △ABC 的面积为 3+√3，求 c。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "triangle", "cosine_rule", "sine_rule", "area"],
        "_source_file": f"{_SOL}/q15.json",
    },
    {
        "case_id": "MATH-48",
        "subset": "answer_core",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "已知 A(0,3)，P(3,3/2) 为椭圆 C: x²/a²+y²/b²=1 (a>b>0) 上两点。"
                             "(1) 求 C 的离心率；(2) 若过点 P 的直线 l 交 C 于另一点 B，"
                             "且 △ABP 的面积为 9，求 l 的方程。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "ellipse", "eccentricity", "line_equation"],
        "_source_file": f"{_SOL}/q16.json",
    },
    {
        "case_id": "MATH-49",
        "subset": "verification_discipline",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "如图，四棱锥 P-ABCD 中，PA⊥底面 ABCD，PA=AC=2，BC=1，AB=√3。"
                             "(1) 若 AD⊥PB，证明：AD∥平面 PBC；"
                             "(2) 若 AD⊥DC，且二面角 A-CP-D 的正弦值为 √42/7，求 AD。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "solid_geometry", "line_plane_parallel", "dihedral_angle"],
        "_source_file": f"{_SOL}/q17.json",
    },
    {
        "case_id": "MATH-50",
        "subset": "verification_discipline",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "已知函数 f(x)=ln(x/(2-x))+ax+b(x-1)³。"
                             "(1) 若 b=0，且 f'(x)≥0，求 a 的最小值；"
                             "(2) 证明：曲线 y=f(x) 是中心对称图形；"
                             "(3) 若 f(x)>-2 当且仅当 1<x<2，求 b 的取值范围。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "derivative", "symmetry", "parameter_range", "proof"],
        "_source_file": f"{_SOL}/q18.json",
    },
    {
        "case_id": "MATH-51",
        "subset": "verification_discipline",
        "split": "development",
        "grade_level": "高中",
        "input": {"problem": "设 m 为正整数，数列 a1,...,a_{4m+2} 是公差不为 0 的等差数列。若从中删去两项 "
                             "a_i 和 a_j (i<j) 后剩余的 4m 项可被平均分为 m 组，且每组的 4 个数都能构成"
                             "等差数列，则称该数列是 (i,j)-可分数列。"
                             "(1) 写出所有的 (i,j)，1≤i<j≤6，使 a1,...,a6 是 (i,j)-可分数列；"
                             "(2) 当 m≥3 时，证明：数列是 (2,13)-可分数列；"
                             "(3) 从 1,...,4m+2 中一次任取两个数 i 和 j (i<j)，记该数列是 (i,j)-可分数列"
                             "的概率为 P_m，证明 P_m>1/8。",
                  "student_attempt": None, "draft": None, "requested_method": None},
        "expected_action": "solve",
        "expected_status": "solved",
        "expected_route": None,
        "tags": ["2024_xgk1", "sequence", "new_definition", "counting", "proof"],
        "_source_file": f"{_SOL}/q19.json",
    },
]

EXAM_GROUND_TRUTH = {
    "MATH-33": {
        "answer_check": {"kind": "value_set", "values": [-1, 0]},
        "required_checks": [["区间", "端点"], ["逐项", "交集"]],
        "required_terms": [["{-1,0}"]],
        "forbidden_terms": ["{-3,-1,0}", "{-1,0,2}"],
        "rationale": "-5<x³<5 等价于 -∛5<x<∛5；∛5 在 1 与 2 之间，B 中只有 -1 与 0 落在该区间。",
    },
    "MATH-34": {
        "answer_check": {"kind": "text_forms", "groups": [["1-i"]]},
        "required_checks": [["代回", "代入"], ["分母", "z≠1"]],
        "required_terms": [["1-i"]],
        "forbidden_terms": ["z=2-i"],
        "rationale": "拆分分式得 1/(z-1)=i，故 z-1=-i，z=1-i；代回原式成立。",
    },
    "MATH-35": {
        "answer_check": {"kind": "value_set", "values": [2]},
        "required_checks": [["点积", "数量积"], ["方程", "平方"]],
        "required_terms": [["x=2"]],
        "forbidden_terms": ["x=-2", "x=-1"],
        "rationale": "b-4a=(2,x-4)，数量积为 (x-2)²=0，故 x=2。",
    },
    "MATH-36": {
        "answer_check": {"kind": "text_forms", "groups": [["-3m"]]},
        "required_checks": [["展开", "两角和"], ["tan", "正切"]],
        "required_terms": [["-3m"]],
        "forbidden_terms": ["cos(α-β)=3m", "cos(α-β)=m/3"],
        "rationale": "tanαtanβ=2 给出 sinαsinβ=2cosαcosβ；cos(α+β)=-cosαcosβ=m，故 cos(α-β)=3cosαcosβ=-3m。",
    },
    "MATH-37": {
        "answer_check": {"kind": "text_forms", "groups": [["3√3π", "3√3 pi"]]},
        "required_checks": [["侧面积", "母线"], ["体积", "圆锥"]],
        "required_terms": [["3√3π"]],
        "forbidden_terms": ["2√3π", "6√3π", "9√3π"],
        "rationale": "侧面积相等给 πr√(r²+3)=2πr√3，r=3；圆锥体积为 πr²h/3=3√3π。",
    },
    "MATH-38": {
        "answer_check": {"kind": "interval_set", "intervals": [
            {"lo": -1, "hi": 0, "lo_closed": True, "hi_closed": True}]},
        "required_checks": [["分界点", "端点"], ["单调", "导数"]],
        "required_terms": [["[-1,0]"]],
        "forbidden_terms": ["(-∞,0]", "[-1,1]"],
        "rationale": "左段需 a≤0，分界点需 -a≤f(0)=1，即 a≥-1，故 a∈[-1,0]。",
    },
    "MATH-39": {
        "answer_check": {"kind": "value_set", "values": [6]},
        "required_checks": [["零点", "区间"], ["单调", "导数"], ["端点", "符号"]],
        "required_terms": [["6"]],
        "forbidden_terms": ["8个交点", "4个交点", "3个交点"],
        "rationale": "在 h 的每个零点邻域内用 |h'|>|cos x| 证明 f 严格单调，端点符号交替，6 个区间各一个解；其余区间 |h|>1 无解。",
    },
    "MATH-40": {
        "answer_check": {"kind": "text_forms", "groups": [["f(20)>1000"]]},
        "required_checks": [["递推", "归纳"], ["下界", "斐波那契"]],
        "required_terms": [["f(20)>1000"]],
        "forbidden_terms": ["f(10)>100", "f(20)<10000"],
        "rationale": "归纳得 f(n)>F_(n+1)，故 f(20)>10946>1000；其余选项只给下界或上界，不一定成立。",
    },
    "MATH-41": {
        "answer_check": {"kind": "text_forms", "groups": [["bc"]]},
        "required_checks": [["正态", "标准化"], ["对称", "概率"]],
        "required_terms": [["BC"]],
        "forbidden_terms": ["P(Y>2)<0.8"],
        "rationale": "P(X>2)=P(Z>2)<P(Z>1)=0.1587<0.2；P(Y>2)=P(Z>-1)=0.8413>0.2 且 >0.8，故 B、C 正确。",
    },
    "MATH-42": {
        "answer_check": {"kind": "text_forms", "groups": [["acd"]]},
        "required_checks": [["导数", "极小"], ["区间", "端点"]],
        "required_terms": [["ACD"]],
        "forbidden_terms": ["B正确", "ABD"],
        "rationale": "f'=3(x-1)(x-3)，x=3 为极小值点；0<x<1 时 f(x)>f(x²)；1<t<3 时 -4<f(t)<0；-1<x<0 时 f(2-x)-f(x)=-2(x-1)³>0。",
    },
    "MATH-43": {
        "answer_check": {"kind": "text_forms", "groups": [["abd"]]},
        "required_checks": [["原点", "代入"], ["方程", "曲线"], ["纵坐标", "不等式"]],
        "required_terms": [["ABD"]],
        "forbidden_terms": ["C正确", "ABC"],
        "rationale": "原点代入得 a=-2；曲线为 √((x-2)²+y²)(x+2)=4；点 (2√2,0) 在曲线上；x=3/2 时 y²>1，故 C 错；由 y²≤16/(x+2)² 得 D。",
    },
    "MATH-44": {
        "answer_check": {"kind": "text_forms", "groups": [["3/2"]]},
        "required_checks": [["焦点", "通径"], ["定义", "离心率"]],
        "required_terms": [["3/2"]],
        "forbidden_terms": ["√133/7", "sqrt(133)/7"],
        "rationale": "通径长 2b²/a=10，|AF2|=5；双曲线定义给 2a=13-5=8，a=4，b²=20，c=6，e=3/2。",
    },
    "MATH-45": {
        "answer_check": {"kind": "text_forms", "groups": [["ln2"]]},
        "required_checks": [["切线", "斜率"], ["切点", "代入"]],
        "required_terms": [["ln2"]],
        "forbidden_terms": ["a=-ln2"],
        "rationale": "第一条切线为 y=2x+1；第二条曲线切点 x=-1/2，切线为 y=2x+1+a-ln2，比较得 a=ln2。",
    },
    "MATH-46": {
        "answer_check": {"kind": "text_forms", "groups": [["1/2"]]},
        "required_checks": [["枚举", "排列"], ["得分", "概率"]],
        "required_terms": [["1/2"]],
        "forbidden_terms": ["1/3", "2/3"],
        "rationale": "固定甲的顺序，乙的 24 种排列中 S≥2 的有 12 种，故 P=1/2。",
    },
    "MATH-47": {
        "answer_check": {"kind": "text_forms", "groups": [["π/3"], ["2√2"]]},
        "required_checks": [["余弦定理", "cosC"], ["正弦定理", "面积"]],
        "required_terms": [["π/3"], ["2√2"]],
        "forbidden_terms": ["B=π/6", "c=2√3"],
        "rationale": "余弦定理给 cos C=√2/2，C=π/4；sin C=√2 cos B 给 cos B=1/2，B=π/3；A=5π/12，面积给 c²=8，c=2√2。",
    },
    "MATH-48": {
        "answer_check": {"kind": "text_forms", "groups": [["x-2y=0"], ["3x-2y-6=0"]]},
        "required_checks": [["椭圆", "离心率"], ["面积", "距离"], ["联立", "交点"]],
        "required_terms": [["1/2"], ["x-2y=0"], ["3x-2y-6=0"]],
        "forbidden_terms": ["唯一解", "只有一条"],
        "rationale": "a²=12，b²=9，e=1/2；面积为 9 给 B 到 AP 的距离 12/√5，联立得 B(-3,-3/2) 或 B(0,-3)，对应两条直线。",
    },
    "MATH-49": {
        "answer_check": {"kind": "text_forms", "groups": [["ad∥平面pbc"], ["ad=√3"]]},
        "required_checks": [["线面平行", "判定"], ["法向量", "二面角"]],
        "required_terms": [["AD∥平面PBC"], ["AD=√3"]],
        "forbidden_terms": ["AD=3", "AD=2√3"],
        "rationale": "(1) AD⊥PA、AD⊥PB ⇒ AD⊥平面 PAB ⇒ AD⊥AB，又 AB⊥BC，故 AD∥BC，进而 AD∥平面 PBC；(2) 坐标法给 cos²θ=(4-t²)/(4+t²)=1/7，t=√3。",
    },
    "MATH-50": {
        "answer_check": {"kind": "text_forms", "groups": [["-2"], ["(1,a)"], ["b≥-2/3"]]},
        "required_checks": [["导数", "最小值"], ["对称", "中心"], ["必要性", "充分性"]],
        "required_terms": [["-2"], ["(1,a)"], ["b≥-2/3"]],
        "forbidden_terms": ["a=-2/3", "b≥2/3"],
        "rationale": "(1) f'=2/[x(2-x)]+a≥a+2，a_min=-2；(2) f(x)+f(2-x)=2a，中心 (1,a)；(3) x=1 给 a=-2，必要性给 b≥-2/3，充分性用 h(x)=ln(x/(2-x))-2x-(2/3)(x-1)³ 单调递增证明。",
    },
    "MATH-51": {
        "answer_check": {"kind": "text_forms", "groups": [
            ["(1,2)"], ["(1,6)"], ["(5,6)"], ["(2,13)"], ["1/8"]]},
        "required_checks": [["下标", "等差"], ["构造", "分组"], ["计数", "概率"]],
        "required_terms": [["(1,2)"], ["(1,6)"], ["(5,6)"], ["(2,13)"], ["1/8"]],
        "forbidden_terms": ["T_m>a_1+2md", "(2,m)-可分数列"],
        "rationale": "(1) 三对下标；(2) m=3 用三组公差 3 的下标，m>3 时后续连续四项成组；(3) A、B 两类可分数对合计 m²+m+1，总取法 8m²+6m+1，故 P_m>1/8。",
    },
}
