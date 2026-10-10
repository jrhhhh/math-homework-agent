# solution-refiner · 正解优化器（课堂作品）

《数学智能体工程与实践》第 4 讲动手环节作品——`my_skill/`（presolve-starter）的姊妹篇。

**学生做对了，但解法很笨、很慢、很局限。** 本技能不判对错，而是分析"正确但不够好"的解法，
找出优化空间，并反推学生缺失的数学能力：**3 个优化方向 + 每个方向暴露的短板 + 一个训练建议**。

与同伴的错题诊断 skill 分工，以及本项目四个技能的位置：

```
不会开始 → presolve-starter                  （事前：启动思路）
做错了   → 同伴 math-error-diagnosis          （事后：诊断错因 → 修复 → 分层提示）
        → 攒够 ≥2 道 → error-atlas 第一段      （跨题：从病例到错误模式）★本项目新增
        → 学生要求出题 → error-atlas 第二段    （定制：从模式到练习）    ★本项目新增
做对了   → 本技能 solution-refiner            （事后：从对到好）
```

```
做题 → 答案错了 → 同伴：诊断错因 → 修复 → 变式 → 复习   （从错到对）
     → 答案对了 → 本技能：优化空间 → 反推短板 → 训练建议 （从对到好）
```

所有工具都在服务"从错到对"，没人服务"从对到好"——这是本技能要填的空白。
`presolve-starter` 管"不会开始"（事前启动），本技能管"对了但还能更好"（事后提升）。

与 `error-atlas` 的分界要特别留意：**本技能只谈"这一份解答"。**
它**禁止出变式题**，也**不凭一道题认定学生长期能力弱**（`exposed_gap` 只描述"本份解答未展示的能力"）；
而 `error-atlas` 专做跨题聚合（≥2 道已修复错题）与定制出题。
一个管单题、一个管一批，两者输入规模与断言强度都不同，不能互相替代。

## 结构

```
solution_refiner/
├── SKILL.md                      ← 入口（触发器 + 纪律 + 工作流 + 红线）
├── README.md                     ← 给人看的说明（本文件）
├── solution_card_check.py        ← 确定性操作脚本（纯标准库，无依赖）
└── example/                      ← 五份成品卡 + 一张故意写坏的卡
    ├── primary_25x16.json          ← 小学：25×16 竖式 vs 拆因数凑整
    ├── junior_quadratic.json       ← 初中：x²-5x+6=0 求根公式 vs 因式分解
    ├── junior_linear_system.json   ← 初中：2x+3y=12 代入法 vs 加减消元
    ├── senior_extremum.json        ← 高中：f(x)=x³-3x 极值，代入求值 vs 分解定号
    ├── college_integral.json       ← 大学：∫₀¹xeˣdx 标准分部积分 vs 表格法
    └── bad_card.json               ← 结构合法但越界（audit 应当驳回）
```

## 两道门

本技能沿用 presolve-starter 的"结构门 + 越界门"设计，两道门管的完全是两件事：

| 门 | 命令 | 查什么 | 不查什么 |
| --- | --- | --- | --- |
| 结构门 | `validate` | 字段齐不齐、方向是不是**恰好 3 条**、方向在不在七类白名单内、方向有没有重复、短板标签与方向搭不搭 | 建议在数学上是否真的更优 |
| 越界门 | `audit` | 有没有**判对错 / 诊断错因 / 出变式题 / 排复习计划 / 报置信度 / 探测理解深度**，以及卡片是否脱离学生的原解答 | 同上 |

## 快速体验

```bash
# 方法线索启发式初判（只是提示，不能替代读解法）+ 打印七类方向菜单
python3 solution_card_check.py hint \
  --problem "求 x^2-5x+6=0 的根。" \
  --solution "用求根公式：x=(5±√1)/2，所以 x1=3, x2=2。"

# 结构门：0 = 通过，1 = 结构不合格，2 = 输入非法（文件缺失 / JSON 坏）
python3 solution_card_check.py validate --card example/junior_quadratic.json

# 越界门：0 = 干净，1 = 发现越界；--strict 时 warning 也算失败
python3 solution_card_check.py audit --card example/junior_quadratic.json \
  --problem "求 x^2-5x+6=0 的根。" \
  --solution "用求根公式：x=(5±√1)/2，所以 x1=3, x2=2。"

# 坏卡片：validate 放行（结构合法），audit 驳回（退出码 1）
python3 solution_card_check.py validate --card example/bad_card.json
python3 solution_card_check.py audit    --card example/bad_card.json \
  --problem "求 x^2-5x+6=0 的根。" \
  --solution "用求根公式：x=(5±√1)/2，所以 x1=3, x2=2。"
```

`example/bad_card.json` 是配套教具：它结构完全合法（四个字段齐全、恰好 3 个方向、方向全在白名单），
但一路越界——写了"算错了"（判对错）、"错因是……"（诊断错因）、"下面这道变式题"（出变式题）、
"每天做 5 道，一周补上"（排复习计划）、"置信度不高"（报置信度）。

实测结果（两道门的分工一目了然）：

```
validate → passed=true,  errors=0, warnings=4   （只有告警：3 条短板标签不搭 + 1 条建议过短）
audit    → passed=false, errors=7               （A_JUDGE / A_CAUSE / A_VARIANT / A_PLAN ×3 / A_CONFIDENCE）
```

**结构门管"卡片长得对不对"，越界门管"卡片有没有跑到别的 skill 的地盘"**——
这样卡片正好演示两道门各管一段，谁都不越权。

**Windows 注意**：`PATH` 里的 `python` / `python3` 可能是应用商店的占位程序，
运行时会静默失败、什么都不输出。若如此请用真实解释器的完整路径，例如本机为
`"D:/Program Files/anaconda3/python.exe"`。

## 脚本的诚实边界

两道门都是**便宜的确定性门，不是数学判断**：

- 脚本**不判断优化建议是否真的更优**。"这个更优方法其实不比原方法快"这类错误，只能靠人读出来。
- 措辞门抓的是固定说法，换个说法就绕过去了；`W_GAP_MISMATCH` 只是关键词匹配，可能误报。
- 关联度检查**忽略个位数字**（"2" 会撞上 "25"），所以短数字解法会跳过该项检查。
- 通过两道门只证明"卡片没越过这几条线"，**不证明教学质量**。

## 给 agent 的安装 / 测试提示词

> 请把 `solution_refiner/` 作为技能安装到你的技能目录，然后用它完成冒烟测试：
> 题目"求 x²-5x+6=0 的根"，学生解答"用求根公式：x=(5±1)/2，所以 x₁=3, x₂=2"。
> 对这个**正确**解法生成一张优化卡，跑 `validate` 与 `audit` 两道门，
> 把脚本的真实输出原文贴给我，并说明这张卡有没有越界。
> 然后把卡片故意改坏——写上"你这一步其实算错了"、"错因是十字相乘不熟"、
> "下面这道变式题你试试"、"每天做 5 道，一周就能补上"、"置信度不高"
> ——重跑两道门，解释为什么这一次 `audit` 驳回了它。

（提示：正确的 agent 应当**先把学生的解法读清楚**再生成卡片，
两道门都跑、如实引用脚本输出，对被驳回的坏卡片逐条指出越界位置，
而不是含糊地说"基本可用"。改坏后 `validate` 仍会放行——结构没变，只多几条告警；
`audit` 则应当驳回 7 条越界——这正是两道门的分工：**`validate` 管结构，`audit` 管越界**。）
