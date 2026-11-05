# 数学试卷参考答案编制

输入一份高中数学试卷，生成逐题参考答案，并交付经 LaTeX 实际编译的 PDF 和可编辑源码。包含完整推导、采分点、步骤分值、简短思路点拨及有具体理由的难度评价。

```text
请使用 $answer-key-builder，为这份数学试卷编制整卷参考答案。
保留原题号和小问；采用高中方法，给出采分点与步骤分值建议、思路点拨和难度评价。
用 LaTeX 排版并实际编译 PDF，同时交付可编辑源码。
```

技能入口：[SKILL.md](SKILL.md)。内容规范：[exam-answer.md](references/exam-answer.md)。排版与交付：[latex-production.md](references/latex-production.md)。

模板 `assets/reference-answer.sty` 提供题头、点拨、累计分标记、难度和可分页采分表。数学必须用真正的 LaTeX 数学环境，不把 `sqrt(...)`、Unicode 上标或普通文字公式作为最终排版。分值依据数学成果分配，禁止按步骤行数机械均分。

可复现的版式示例：

```bash
python3 answer-key-builder/scripts/build_reference_pdf.py \
  answer-key-builder/example/reference-answer-quality/main.tex \
  --output-dir output/pdf/reference-answer-quality
```

编译脚本执行 XeLaTeX 两遍，并记录缺字、溢出和引用错误。它不验证数学或评分质量。样例用于检查排版，不是整卷试测或真实模型成绩。

工作台选择“生成试卷参考答案”，将完整试卷及分值放入题目栏；数字文件可先提取文字并核对。目前工作台生成在线正文，尚无自动 LaTeX/PDF 导出。完整文件仍需宿主按技能执行编译，不得把文字回复当作 PDF 已生成。

单题求解仍使用原有六字段 JSON：[输出契约](references/output-schema.md)。结构门：

```bash
cd answer-key-builder
python3 scripts/validate_output.py validate --card example/sqrt_equation_solved.json --strict
```

数学核验、结构检查、LaTeX 编译、成品视觉检查和教师审阅分别记录。已有 `bench/` 对保存的输出评分；历史夹具与样例不代表模型实际能力。
