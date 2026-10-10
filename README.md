# 高中数学作业三 Skill 项目

一个供支持本地 Skill 的智能体使用的高中数学作业协作项目。**skill：Math Error Diagnosis**（`math-error-diagnosis`）检查学生实际提交的解答，定位首错并给最小修改；**skill：Solution Refiner**（`solution-refiner`）在当前解答的结论与完整过程都成立、且用户请求优化后，提供三个优化方向；**skill：Draft Coach**（`draft-coach`）只看学生的草稿，分析思考习惯——分区、跳步、涂改、试错、画图、草稿利用率——给出下一道题就能执行的动作。它不判对错、不诊断知识漏洞、不修补解答。

覆盖函数与导数、三角函数与解三角形、圆锥曲线、数列、向量与立体几何、概率统计，以及集合、逻辑、复数等基础代数内容。

## 使用

将整个 `math-error-diagnosis/` 目录复制到宿主的技能目录。Codex 的常用位置为 `~/.codex/skills/`；若设置了自定义技能目录，则使用相应位置。避免覆盖同名技能，先比较已有版本。

需要协作使用时也安装 `solution-refiner/`，并在本项目工作区使用根目录的 [AGENTS.md](AGENTS.md) 作为调度约定。它引用 [交接协议](docs/handoff-protocol.md) 和 `scripts/handoff_check.py`；宿主需实际执行审查与调度，本仓库没有自动运行的后台Agent服务。只使用诊断技能仍可独立检查作业。

```text
请使用 $math-error-diagnosis 检查我的解题过程，指出首个实质错误并给出最小修改。

题目：在 0≤x<2π 内解 sin(2x)=sin(x)。
我的过程：用二倍角公式后，两边除以 sin(x)，得 cos(x)=1/2，
所以解只有 π/3 和 5π/3。
```

也可以向能读取本地文件的 Agent 指定 `math-error-diagnosis/SKILL.md`，要求按其规则检查题目和学生解答。Skill 需要宿主模型执行，Python 脚本不提供通用诊断服务。

学生只交出草稿、想知道自己习惯哪里有问题时用 `$draft-coach`（草稿只有图片时，先把结构和布局用文字描述出来）：

```text
请使用 $draft-coach 分析我的草稿，看看我的思考习惯有什么问题。

草稿：左上角写 x^3-3x 求极值；中间写 f'(x)=3x^2-3；下面写 3x^2=3 → x^2=1 → x=1（划掉）x=±1；
右边写 f(1)=-2；右下角写 f(-1)=2；底部写 极大值2 极小值-2
```

它**不需要**答案对不对就能分析，所以同一份草稿无论对错都可以用；反过来，它也不会告诉你哪里算错了。

默认模式是过程检查。可要求“完整纠正”“只给一个提示，别告诉答案”或“仅核对答案”；只有最终答案时不会推断未提供的过程。默认使用高中方法，不擅自扣分，参考答案也需核验。

## 文件结构

```text
math-error-diagnosis/
  SKILL.md                 技能入口、触发描述与审查流程
  agents/openai.yaml       界面信息与默认调用提示
  references/              六份题型清单、判断尺度与示例
solution-refiner/
  SKILL.md                 优化卡入口、四字段接口与优化方向表
  solution_card_check.py   优化卡的结构门与越界审计
  example/                 三份示例卡（含混入诊断的反例）
draft-coach/
  SKILL.md                 草稿习惯分析入口、六维尺度与学段适配
  draft_coach_check.py     结构门、越界审计、hint 与 refuse
  example/                 两份示例卡、一份越界反例、三份 refuse 输出
docs/                      诊断案例、验证范围与说明
tests/                     衔接回归测试、draft-coach 门测试与固定案例计算脚本
scripts/handoff_check.py   交接元信息与当前解答版本检查
AGENTS.md                 三个技能的调用与反馈规则
```

优先阅读 [技能入口](math-error-diagnosis/SKILL.md)、[代表案例](docs/代表案例.md) 和 [验证说明](docs/验证说明.md)。展示名称统一带“skill：”前缀；文件夹名称和 `$math-error-diagnosis`、`$solution-refiner`、`$draft-coach` 调用名保持一致。

## 复现计算核验

Python 3，三个脚本仅依赖标准库，在仓库根目录执行：

```bash
python3 tests/核验测试数学.py
python3 tests/新例计算核验.py
python3 tests/高中题型计算核验.py
```

它们分别核验10、6、11组固定数学事实。后两个脚本会在同目录生成JSON证据文件，首个脚本将JSON结果输出到终端；生成结果不纳入版本控制。有限样本与浮点容差检查的限制在输出中说明。这些脚本不是模型行为测试，也不代替一般性数学证明。

交接与卡片兼容性测试：

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

覆盖过期解答、答案正确但过程无效、论证缺口、只有答案、助手修补稿、提示模式、未请求优化、非法输入及卡片接口。检查状态不放入优化卡。两道卡片门仍不审数学，优化建议需宿主另行核验。`tests/test_draft_coach.py` 另覆盖草稿卡的结构、越界、关联度与三个 refuse 出口。

draft-coach 的两道门可直接复现：

```bash
cd draft-coach
python3 draft_coach_check.py validate --card example/high_school_cubic.json
python3 draft_coach_check.py audit --card example/drifts_into_judgment.json \
  --draft "左上角写 x^3-3x 求极值；下面写 3x^2=3 → x^2=1 → x=1（划掉）x=±1"
```

第一道应退出 0；第二道结构合格但审计应退出 1（它滑进了判对错、错因诊断、贴标签和题量计划）。

前两个技能的结构已通过 skill-creator 的 `quick_validate.py`；仓库参考路径与界面配置已检查。新增 draft-coach 时环境里没有该验证器，**这一项没跑**，改用 frontmatter/界面 YAML 可解析、示例 JSON 可解析、Markdown 相对链接可达和 unittest 退出码覆盖代替。诊断案例由同一助手执行及复核，尚未进行独立盲测。复测时只向新会话提供技能和案例输入，隐藏已有回答，然后比较首错定位、条件边界与提示模式。

## 能力边界

图片/PDF识别、工具权限、长期记忆和独立验证服务依赖宿主。本项目不附带OCR服务或学生数据库。复杂题目仍应审查实际数学依据，不能把有限案例结果视为任意高考题的准确率保证。

draft-coach 只处理**文字还原或布局描述**的草稿，不附带笔迹或OCR识别；草稿认不出来时它应当拒绝分析而不是猜。它的两道门都不检查教学质量——结构门只看卡片长得对不对，措辞门只抓固定说法、换个说法就绕得过去，宿主仍需自己读草稿判断观察是否成立。
