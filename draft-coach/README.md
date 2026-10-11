# skill：Draft Coach

**首要检查草稿里的计算错误，其次分析草稿的过程习惯。** 输入是学生的草稿（手写照片、文字还原或笔迹数据）。不诊断知识漏洞、不贴标签、不出变式题、不排复习计划、不给整题重写。

由用户提供的「草稿与过程管理教练」提示词规范改写而来。**2026-10-11 按用户要求重新定位**：原提示词把"不判对错"列为绝对禁止，现已改为"先查错、后讲习惯"——判对错、指出某处算错了、给出该写成什么，都是本职。改动见下方。

它**不在** math-error-diagnosis → solution-refiner 的交接链路里，也不消费交接包。与 `math-error-diagnosis` 的分界靠**输入**判别：交的是**正式解答**走诊断，交的是**草稿纸**走本技能。

从本目录运行（Windows 上 `python3` 可能是应用商店占位程序，用可用的解释器）：

```bash
python3 draft_coach_check.py hint --draft "下面写 3x^2=3 → x^2=1 → x=1（划掉）x=±1" --grade-level 高中
python3 draft_coach_check.py validate --card example/high_school_cubic.json
python3 draft_coach_check.py audit --card example/high_school_cubic.json \
  --draft "左上角写 x^3-3x 求极值；中间写 f'(x)=3x^2-3；下面写 3x^2=3 → x^2=1 → x=1（划掉）x=±1；右边写 f(1)=1-3=-2；右下角写 f(-1)=-1+3=2；底部写 极大值2 极小值-2" --strict
```

示例卡：

- `example/high_school_cubic.json`、`example/junior_high_substitution.json`：`error_check.errors` 为空（这两份草稿没查出计算错误），两门都应通过。
- `example/junior_high_transposition.json`：含一条真实错误（移项未变号），两门都应通过。
- `example/fabricated_error.json`：结构门通过（退出 0），审计应拒绝（退出 1）——它①报了一条草稿里根本没有的错误（`48÷4=12`），②给学生贴标签，③写了"连续做 10 道"。其中 `W_ERROR_NOT_IN_DRAFT` 会把草稿里查不到的候选记号 `48/4/12` 列出来。
- `example/refuse_*.json`：`refuse` 三个出口的真实输出，退出码分别是 2、2、1。

**两道门都不验数学。** 结构门只看错误条目有没有四个字段，审计只看证据在不在草稿里。本技能最核心的声称——"这处算错了"——恰恰是它唯一验不了的东西。没有人工复核的草稿检查卡不构成数学结论。

## 相对原提示词的改动

1. **"不判对错"整条撤销**（2026-10-11）。原提示词第 5–7 行、206 行、397–398 行把它列为绝对禁止；现改为首要职责。相应地删除了 `D_JUDGE` 闸，新增 `A_SCORE`（评分扣分仍不许）与 `W_ERROR_NOT_IN_DRAFT`（错误必须有草稿证据）。
2. **新增 `error_check` 字段**并置于卡片首位：`scope` 说明本次检查范围，`errors` 逐条给出位置、原式、解释、最小修改。
3. **缺原题时查错降级**：只能查草稿内部自洽（前后矛盾、代回不成立），必须写进 `scope`，不能含糊成"我检查过了"。
4. 原提示词示例 1 的"连续做 10 道"与它自己的规则冲突，已改成单题动作，并保留 `A_PLAN` 拦住回潮。
5. "禁止输出 JSON 以外的内容"与本仓库"卡片是机器接口、教学语言是交付物"的惯例冲突，按后者处理。

共用调度见 [AGENTS.md](../AGENTS.md)。
