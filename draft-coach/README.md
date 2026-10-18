# skill：Draft Coach（草稿习惯教练）

**只看草稿的版面习惯，不判断计算对错，也不做手写转写。** 六个维度：分区与边距、步骤分行与密度、划改与自纠、多路径标记、图形与标注、留白与检验区；输出 1–3 条习惯 + 下一道题就能执行的动作。

重点看中学生常见的版面风险：多题混写、高风险步骤（移项/去括号/开方/分类边界/代入）挤在一行、分类讨论不标号、旧值新值叠在一起、几何图不标顶点/辅助线、结果旁没有检验区。**草稿允许随意**：允许简写、箭头、低风险步骤心算；不评工整，只评可追溯、可复核、可区分。

整张草稿纸问「大概做了几道题」时，走 `partition` 出口：只按版面分块，给估计数与范围；**块数不等于题目数**，归属由学生确认。

它**不参与求解或诊断链路**，也不消费交接包。分工：

| 输入 | 走哪里 |
| --- | --- |
| 作业本 / 答卷上的正式解答 | `math-error-diagnosis` |
| 草稿纸 | 本技能（六维版面习惯） |
| 整张草稿纸 + 做了几道题 | 本技能的 `partition` 出口 |
| 已核验成立的解法 + 要优化 | 当前项目暂不提供优化技能（不归本技能） |

## 门与运行

```bash
python3 scripts/validate_output.py validate --card example/high_school_cubic.json
python3 scripts/audit_output.py audit --card example/high_school_cubic.json \
  --draft "左上角写 x^3-3x 求极值；中间写 f'(x)=3x^2-3；下面写 3x^2=3 → x^2=1 → x=1（划掉）x=±1；右边写 f(1)=1-3=-2；右下角写 f(-1)=-1+3=2；底部写 极大值2 极小值-2" --strict
python3 scripts/partition_check.py validate --payload example/partition_sheet.json --strict
```

示例卡：

- `example/high_school_cubic.json`、`example/junior_high_substitution.json`、`example/junior_high_transposition.json`：三张正常习惯卡，两门都应通过。
- `example/layout_habits.json`：短草稿，两个维度标「不适用」，2 条习惯；两门都应通过。
- `example/out_of_scope_label.json`：反例——结构门 0，审计 1（贴标签 `A_LABEL`、题量计划 `A_PLAN`）。
- `example/partition_sheet.json`：整页分块单；`partition_check.py validate --strict` 应退出 0。
- `example/refuse_*.json`：`refuse` 三个出口的真实输出，退出码分别是 2、2、1。

## 目录结构

```text
SKILL.md       技能入口：工作流、规则与边界
scripts/       门脚本 —— validate_output.py（结构门 + hint）、audit_output.py（审计门 + refuse）、
               partition_check.py（分区门），共用 _rules.py
references/    细节文档 —— analysis-rules.md、output-schema.md、examples.md、image-intake.md、partition.md
assets/        output_template.json（输出模板）、partition_template.json（分块单模板）
example/       固定 fixture：习惯卡、反例、整页分块单、refuse 输出
tests/         技能自带测试 —— 38 项：结构门、审计门、分区门
bench/         当前技能的版面习惯基准 —— 24 条正面能力案例、确定性评分、夹具、人工层导出
evals/         旧版「查错」基准，已冻结；见 evals/FROZEN.md，不对应当前技能
```

测试（在仓库根目录执行）：

```bash
python3 -m unittest discover -s draft-coach/tests -p 'test_*.py'
```

版面习惯基准（在 `draft-coach/bench/` 下）：

```bash
python3 schema_check.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 make_fixture_predictions.py --mode oracle --out predictions/fixtures/oracle.json
python3 evaluate.py --predictions predictions/fixtures/oracle.json
python3 evaluate.py --predictions predictions/fixtures/bad.json --strict   # 应退出 1
```

它评的是已保存的输出，不调用模型；自动层不判断版面观察是否属实。细则见
[`bench/README.md`](bench/README.md) 与 [`bench/DESIGN.md`](bench/DESIGN.md)。

## 能力边界

**两道门都不验数学，也不验证版面观察是否属实。** 本技能不判断计算对错；它说「这一步挤在一行」，不说「这一步算错了」。通过两道门只说明卡片没越过结构线与措辞线。要查对错请走 `math-error-diagnosis`；已成立解法的优化当前项目暂不提供。

分诊门已随 `triage` 出口一起移除；图片与 OCR 依赖宿主，本技能不含转写层。
