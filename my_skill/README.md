# presolve-starter（课堂作品）

《数学智能体工程与实践》第 4 讲动手环节作品，按"五步法"建设的最小完整技能：
学生看到题、不知道从哪下笔时，生成一张**解题前思考卡**——只启动思路，不给答案。

与同伴的错题诊断 skill 分工：诊断管"做错了怎么办"（事后），本技能管"根本不知道怎么开始"（事前），二者不重叠。

本项目四个技能在同一个闭环上各占一段（完整分工表见项目根目录 `AGENTS.md`）：

```
不会开始 → presolve-starter（本技能）        （事前：启动）
做错了   → 同伴 math-error-diagnosis          （事后：错因 → 最小修改 → 分层提示）
        → 攒够 ≥2 道 → error-atlas 第一段      （跨题：从病例到错误模式）★本项目新增
        → 学生要求出题 → error-atlas 第二段    （定制：从模式到练习）    ★本项目新增
做对了   → solution-refiner                   （事后：从对到好）
```

本技能是链条的**最前端**：它不碰"对错"，也不碰"一摞错题"，只负责让学生**能动笔**。

## 结构

```
my_skill/
├── SKILL.md                  ← 入口（触发器 + 纪律 + 工作流 + 红线）
├── README.md                 ← 给人看的说明（本文件）
├── think_card_check.py       ← 确定性操作脚本（纯标准库，无依赖）
└── example/                  ← 四学段成品卡 + 一张故意写坏的卡
    ├── primary_fraction.json   ← 小学：分数应用题
    ├── junior_geometry.json    ← 初中：等腰三角形证明
    ├── senior_extremum.json    ← 高中：三次函数极值
    ├── college_series.json     ← 大学：级数收敛性
    └── bad_leak.json           ← 结构合法但泄漏答案（audit 应当驳回）
```

## 快速体验

```bash
# 题型启发式初判（只是提示，不能替代读题）
python3 think_card_check.py classify --problem "已知函数 f(x)=x^3-3x，求其极值。"

# 结构门：0 = 通过，1 = 结构不合格，2 = 输入非法（文件缺失 / JSON 坏）
python3 think_card_check.py validate --card example/senior_extremum.json

# 泄漏审计：0 = 干净，1 = 发现越界；--strict 时 warning 也算失败
python3 think_card_check.py audit --card example/senior_extremum.json \
  --problem "已知函数 f(x)=x^3-3x，求其极值。" \
  --answer "极大值 f(-1)=2，极小值 f(1)=-2"

# 坏卡片：validate 放行（结构合法），audit 驳回（退出码 1）
python3 think_card_check.py validate --card example/bad_leak.json
python3 think_card_check.py audit    --card example/bad_leak.json \
  --problem "已知函数 f(x)=x^3-3x，求其极值。"
```

`example/bad_leak.json` 是配套教具：它结构完全合法，但写了"答案是……"、还用 `解：`
开头替学生把解法写了。**`validate` 管结构，`audit` 管越界**——这张卡正好演示两道门的分工。

**Windows 注意**：`PATH` 里的 `python` / `python3` 可能是应用商店的占位程序，
运行时会静默失败、什么都不输出。若如此请用真实解释器的完整路径，例如本机为
`"D:/Program Files/anaconda3/python.exe"`。

## 给 agent 的安装 / 测试提示词

> 请把 `my_skill/` 作为技能安装到你的技能目录，然后用它完成冒烟测试：
> 对题目"已知函数 f(x)=x^3-3x，求其极值。"生成一张解题前思考卡，跑 `validate` 与 `audit`
> 两道门，把脚本的真实输出原文贴给我，并告诉我这张卡有没有越界。
> 然后把卡片故意改坏——写上一句"答案是极大值 2、极小值 -2"，并把 `first_move` 改成以 `解：` 开头
> ——重跑两道门，解释为什么这一次 `audit` 驳回了它。

（提示：正确的 agent 应当**先读题再生成卡片**，两道门都跑、如实引用脚本输出，
对被驳回的坏卡片指出"答案是""解："两处越界，而不是含糊地说"基本可用"。
改坏后 `validate` 仍会放行——结构没变；`audit` 则应当驳回——这正是两道门的分工：
**`validate` 管结构，`audit` 管越界**。）
