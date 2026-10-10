# skill：Draft Coach

只看学生的草稿，分析他思考过程中的习惯问题。不判对错、不诊断知识漏洞、不修补解答、不出变式题、不排复习计划。

草稿可以是学生口述的文字，也可以是手写照片——**手写照片走"转写 → 让学生核对 → 再分析"三步**，核对没做完不许分析。原因很简单：涂改和分区这两个维度全靠图像细节，转写错了就会分析出一个不存在的习惯，而两道脚本门只查卡片长得对不对，拦不住转写错误。详见 [SKILL.md](SKILL.md) 的「输入形态与手写草稿」。

由用户提供的「草稿与过程管理教练」提示词规范改写而来，按本仓库惯例补齐了结构门、越界审计与真实示例。它**不在** math-error-diagnosis → solution-refiner 的链路里：草稿对错都能分析习惯，所以既不要求解答已核验成立，也不消费交接包。

从本目录运行（Windows 上 `python3` 可能是应用商店占位程序，直接用可用的解释器）：

```bash
python3 draft_coach_check.py hint --draft "下面写 3x^2=3 → x^2=1 → x=1（划掉）x=±1" --grade-level 高中
python3 draft_coach_check.py validate --card example/high_school_cubic.json
python3 draft_coach_check.py audit --card example/high_school_cubic.json \
  --draft "左上角写 x^3-3x 求极值；中间写 f'(x)=3x^2-3；下面写 3x^2=3 → x^2=1 → x=1（划掉）x=±1；右边写 f(1)=1-3=-2；右下角写 f(-1)=-1+3=2；底部写 极大值2 极小值-2" --strict
```

示例卡：

- `example/high_school_cubic.json`、`example/junior_high_substitution.json`：结构门与审计门都应通过。
- `example/drifts_into_judgment.json`：结构门通过（退出 0），但审计应拒绝（退出 1）——它滑进了判对错、错因诊断、贴标签和"连续做 10 道"的题量计划。
- `example/refuse_*.json`：`refuse` 三个出口的真实输出，退出码分别是 2、2、1。

两门都不检查教学质量：结构门只看卡片长得对不对，措辞门只抓固定说法。宿主仍需自己读草稿，判断观察是否成立。

## 改写原提示词时改掉的三处

1. **示例里"连续做 10 道"与它自己的规则冲突**——规则要求每条建议"下一道题就能执行"，而题量计划不是。改成单题动作，并在审计里加了 `D_PLAN`（`连续做 N`、`做 N 道`）拦住回潮。
2. **"禁止输出 JSON 以外的内容"与本仓库的交付方式冲突**——本仓库把卡片当机器接口、把教学语言当交付物（见 solution-refiner 的 Output Standards）。改为：卡片必须是规定的 JSON，交付给学生时翻译成教学语言。
3. **"不判对错"与"跳步是否导致了错误"冲突**——观察点里的"或错误"是在邀请判错，已删除；`risk` 保留，但限定为"若…可能…"的假设句，由 `W_RISK_UNHEDGED` 和 `D_JUDGE` 共同把关。

另外补了两处结构：`grade_level` / `draft_source` 必须回填（学段适配才可检查），以及"草稿利用率"在缺少最终解答时允许标「不适用」——原提示词把 `final_solution` 列为可选，却假设它存在。

共用调度见 [AGENTS.md](../AGENTS.md)。
