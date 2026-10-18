# skill：Math Solver（数学求解器）

**从零求解高中数学题**：解析题意、选高中范围内的方法、分步推导、独立核验，输出可核验的解答，以及供下游教学使用的结构化结果。

它求解，**不检查学生已经写出的解答；不优化已成立的解法；不看草稿版面；不做图片或手写转写。**

## 什么时候用

| 学生给的材料 / 需求 | 去哪里 |
| --- | --- |
| 只有题目，要求求解、证明、求范围或完整解答 | 本技能 |
| 有学生自己写的正式解答，要判对错、找首错、给最小修改 | `math-error-diagnosis` |
| 结论与完整过程已核验成立，要求更简单 / 更短 / 更巧 / 更多方法 | 当前项目暂不提供优化技能；本技能不代做 |
| 草稿纸的版面习惯 | `draft-coach` |
| 图片、PDF 或手写内容的转写 | 不归本技能；需学生自己转成文字 |

本技能产出的是**助手解答**，不是学生解答；不要把它标成学生原解答，也不要用它替换或冒充学生的过程。

## 用法

```text
请使用 $math-solver 求解下面这道题，给出分步推导和核验。

题目：解方程 √(x+2)=x。
```

需要机器可读结果时：

```text
请使用 $math-solver 求解，并输出约定的 JSON。
```

默认用中文讲解。调用方要求机读输出时，返回单个 JSON 对象，包含 `status`、`problem`、`plan`、`solution`、`verification`、`teaching_notes` 六个顶层字段；完整字段与状态一致性见 [输出 Schema](references/output-schema.md)。

## 结构门

```bash
cd math-solver
python3 scripts/validate_output.py validate --card example/sqrt_equation_solved.json --strict
python3 scripts/validate_output.py validate --card example/ambiguous_needs_clarification.json --strict
```

两份示例都应退出 0。第一份是完整求解（含增根检验）；第二份是条件不足、`needs_clarification` 的输出。

退出码：**0** 通过 · **1** 结构不合格（`--strict` 下告警也算不合格） · **2** 输入非法（文件缺失、JSON 坏、顶层不是对象）。

它只查：

- 顶层与嵌套字段是否齐全、是否混入未声明字段；
- 枚举值是否合法；
- `status` 与 `verification.status` 是否一致；
- `solved` 是否具备答案与推导、`passed` 是否没有失败或未完成的检查；
- 是否混入置信度 / 概率校准字段。

它**不判断数学推导是否正确，也不验证答案是否成立**。通过结构门不等于答案正确。

## 测试

在仓库根目录执行：

```bash
python3 -m unittest discover -s math-solver/tests -p 'test_*.py'
```

当前 20 项，覆盖两份示例、字段缺失与多余、状态冲突、检查状态、增根式答案校验所依赖的结构约束、步骤序号告警、`--strict` 行为与三类输入非法。

## 最小可行性测试（2026-10-18）

用五类题各 1 道跑端到端：基础计算与方程、函数与不等式、数列、含参分类讨论、易错与异常输入。五份 JSON 均通过 `--strict` 结构门，另做代回与有限点数值核对。题目、答案、门结果与复现命令见 [example/mvp-2026-10-18/README.md](example/mvp-2026-10-18/README.md)。

扩充测试见 [example/mvp-2026-10-18-expanded/README.md](example/mvp-2026-10-18-expanded/README.md)：五类共 25 道，结构门 **25/25** 通过，数学核验 **44/44** 通过。`verify_math.py` 是测试辅助脚本（需要 sympy），不属于技能结构门。

## 基准（bench）

`bench/` 对**已保存的输出**做确定性评分，不调用模型。32 条案例分四组：`answer_core` 14 / `verification_discipline` 9 / `status_handling` 5 / `boundary_routing` 4；其中 5 条为 test 划分。评分覆盖答案形态、核验点、状态一致性、分支完备、边界转交与 tool_log 真实性。

```bash
cd math-solver/bench
python3 schema_check.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 make_fixture_predictions.py --mode oracle --out predictions/fixtures/oracle.json
python3 evaluate.py --predictions predictions/fixtures/oracle.json \
    --out reports/fixtures/oracle.report.json --markdown reports/fixtures/oracle.report.md
```

oracle 夹具 100 分只说明评分流程自洽，不是模型质量证据；bad 夹具在 `--strict` 下应退出 1。设计与能力边界见 [bench/README.md](bench/README.md) 与 [bench/DESIGN.md](bench/DESIGN.md)。

## 目录结构

```text
SKILL.md                    技能入口：职责、工作流、安全规则与输出契约
agents/openai.yaml          界面信息与默认调用提示
references/
  output-schema.md          逐字段类型、可空性、状态一致性与禁止项
  verification.md           按题型展开的核验路线与常见非等价变形
scripts/validate_output.py  结构门（仅标准库）
example/
  sqrt_equation_solved.json               完整求解 + 增根检验
  ambiguous_needs_clarification.json      条件不足、要求补充信息
  mvp-2026-10-18/                         五类题最小可行性测试夹具与记录
  mvp-2026-10-18-expanded/                五类共 25 题扩充测试夹具、核验脚本与记录
bench/                                    32 条案例、确定性评分、oracle/bad 夹具、27 项测试
tests/test_validate_output.py             20 项结构门回归测试
```

## 能力边界

- “独立核验”是同一助手换路线复核，不是第三方独立验证，也不是形式化证明。
- 有限数值检验只覆盖它实际检查的范围，不能替代一般性证明。
- 工具没实际运行就不声称运行过。
- 不做 OCR；题面转写未经学生确认时只能当线索。
- 复杂题仍可能出错；本项目不提供任意高考题的准确率保证。
