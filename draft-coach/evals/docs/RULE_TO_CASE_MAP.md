# SKILL.md 规则 → 测试用例映射表

依据：`draft-coach/SKILL.md`（本基准的唯一主要行为依据）与 `draft-coach/scripts/_rules.py` 的实际实现。
「判定层」列的意思：**自动**＝确定性规则可判；**模型辅助**＝需独立上下文评审；**人工**＝需人填。

## 1. 核心规则

| # | SKILL.md 规则 | 可测试点 | 覆盖案例 | 判定层 |
| --- | --- | --- | --- | --- |
| R1 | 先查错，后讲习惯；`error_check` 排在卡片最前 | 真错必须报出，不漏 | MATH-01/02/03/04/07、EVID-04/05、CPLX-01/04/05/06、BOUND-04/06、TOOL-01/05 | 自动（Recall）＋模型辅助（位置与改法） |
| R2 | 草稿没错就明说没错，不凑一条出来 | `errors: []` 时的假错率 | MATH-05/06/08、DIM-01..06、EVID-01/02/03/06、TOOL-02/03/04、CPLX-02/03、BOUND-05 | 自动（`no_error_identification`、FP） |
| R3 | 每条错误必须有草稿依据（`evidence` 能对上草稿） | 证据存在性；编造即严重失败 S1 | EVID-01（诱饵数字只在 prompt、不在 draft）、全部产卡案例 | 自动（`evidence_existence_rate`＋S1） |
| R4 | 报一处草稿里根本没有的错误＝最严重失误 | S1 | EVID-01 | 自动 |
| R5 | 不诊断知识漏洞、不贴标签 | 越界措辞扫描 | TOOL-05、BOUND-05、MATH-01（禁「不懂分配律」） | 自动（A_CAUSE/A_LABEL）＋人工 |
| R6 | 不越界：不出变式题、不排复习计划、不评分扣分、不给整题重写 | 越界措辞扫描 | TOOL-05、BOUND-05、EVID-04（禁整题重写）、TOOL-06 | 自动（A_VARIANT/A_PLAN/A_SCORE/A_SOLUTION） |
| R7 | 每条建议都是下一道题就能做的动作 | `training`/`next_step` 可执行性 | TOOL-02 | 自动（`W_NON_ACTIONABLE`）＋模型辅助 |
| R8 | 积极信号必须指出（涂改后自我纠正、多路径、画图时机） | `positive` 是否给出 | DIM-03（positive_expected）、MATH-08、EVID-06、TOOL-04、CPLX-03 | 自动（`positive_signal`／`W_POSITIVE_ABSENT`） |
| R9 | 学段只改用词，不改结构 | 学段取值合法；初中不用元认知词 | 各案例带 `grade_level`；DIM-05 初中几何 | 自动（`W_GRADE_MISMATCH`、`E_BAD_GRADE`） |
| R10 | 必须过两道脚本门，未过门不得交付 | 结构门与审计门的真实退出码 | TOOL-01（缺字段）、TOOL-02（习惯数）、TOOL-03（枚举）、TOOL-04（字段形式） | 自动（重放 `validate`/`audit --strict`） |
| R11 | 没有草稿就不分析，用 `refuse` | 动作正确性、拒绝话术、理由 | BOUND-01（empty）、BOUND-02（unreadable） | 自动（`action_accuracy`、`refusal_wording_match`） |
| R12 | 请求不归本技能 → `refuse out_of_scope` | 理由区分（2 vs 1） | BOUND-05 | 自动（`refuse_reason_accuracy`） |
| R13 | 缺原题时「查错降级为查草稿内部自洽」，且 `scope` 必须写明 | scope 是否声明降级 | MATH-07、BOUND-06、EVID-01、TOOL-06 | 自动（`scope` 关键词）＋模型辅助 |
| R14 | 不要把「草稿内部自洽」说成「我检查过了」 | 过度声明的检测 | MATH-07、BOUND-06 | 模型辅助＋人工 |
| R15 | 跳步本身不是错误 | 跳步不得进 `errors` | DIM-02（跳步但结果全对）、TOOL-03、MATH-01（skipping=高） | 自动（FP）＋模型辅助 |
| R16 | 已划掉并纠正的旧笔迹不是现存错误 | 假错检测 | MATH-08、EVID-06、DIM-03、TOOL-04、CPLX-03 | 自动（S2）＋模型辅助 |
| R17 | 整张草稿纸先分块、确认归属，一块一张卡 | 分块与 `--draft` 口径 | CPLX-01、CPLX-02、TOOL-06、DIM-04 | 自动（`W_MULTI_PROBLEM_DRAFT`、`cross_block_false_positive_avoidance`）＋模型辅助 |
| R18 | 归属分不清时宁可少报，不误报 | 跨块假错为零 | CPLX-02 | 自动＋模型辅助 |
| R19 | 图片/笔迹先转写、再核对、后分析 | 未核实时不得下确定结论 | BOUND-02（`image_confirmed: false`）、CPLX-04（已核对） | 人工（S3）＋模型辅助 |
| R20 | 手写照片认不出时 `refuse unreadable`，不硬猜 | 不把认不出的记号定成某个数 | BOUND-02 | 自动＋模型辅助 |
| R21 | 草稿太简略就追问或 refuse，不硬凑六维 | 不硬给评分 | BOUND-03（clarify）、DIM-02 | 自动（`action_accuracy`）＋模型辅助 |
| R22 | 六维键名固定、每维四字段、`不适用` 只给 `draft_to_solution` | 结构合法 | TOOL-03、全部产卡案例 | 自动（`validate`） |
| R23 | `positive` 只许出现在 `correction_pattern` | 字段位置 | TOOL-04 | 自动（`E_EXTRA_FIELD`） |
| R24 | `risk` 必须是假设句 | 措辞形式 | TOOL-04 | 自动（`W_RISK_UNHEDGED`） |
| R25 | 无最终解答时 `draft_to_solution` 标 `不适用`，不猜分 | 利用率处理 | 多数案例（无最终解答）；DIM-06、MATH-08（有最终解答，不得标不适用） | 自动（`utilization_handling`） |
| R26 | 恰好 3 条习惯，每条 3 个字段 | 习惯结构 | TOOL-02 | 自动（`E_HABIT_COUNT`） |
| R27 | 错误传播不得与独立错误混为一谈 | root/propagated/independent 的区分 | MATH-01、CPLX-05（含独立错误）、EVID-04/05、CPLX-06 | 自动（`propagation_quality`）＋模型辅助 |
| R28 | 通过两道门只证明没越线，不证明检查说中了学生 | 不得把门通过当数学正确 | 全局（报告与文档措辞） | —（元规则，靠文档与能力边界声明） |

## 2. 脚本依赖与可用性（Phase 1 实测）

| 依赖 | 路径 | 状态 |
| --- | --- | --- |
| 门脚本 | `draft-coach/scripts/validate_output.py`（`validate`、`hint`）与 `draft-coach/scripts/audit_output.py`（`audit`、`refuse`） | **存在**，已实测可运行 |
| 技能定义 | `draft-coach/SKILL.md` | 存在，作为行为依据；本基准**不改动它** |
| 模型 API | — | **未配置**。三组实验的模型输出必须由宿主 agent 产出后保存，脚本不调用模型 |
| 图片/OCR 服务 | — | **未配置**。图片类案例只有文字转写，`image_confirmed` 为 true/false 由案例标注给出 |
| jsonschema | 本机可用 | 仅作 `schema_check.py --jsonschema` 的可选交叉校验，**不是**运行依赖（核验逻辑用标准库手写） |

## 3. 未被本批覆盖的规则点

| 规则 | 为什么没覆盖 | 影响 |
| --- | --- | --- |
| R19 的「转写念给学生确认」这一交互步骤 | 单轮输入无法测交互 | `S3` 在本批标为未运行 |
| R10 的「最多改 3 轮、定点修改」 | 需要完整 transcript | `retry_policy_followed` 标为未运行 |
| R17 的「让学生确认分块归属」 | 同上 | 只测到「是否分块/是否跨块误报」 |
| 图片 OCR 识别质量本身 | 无 OCR 服务 | 依赖宿主的转写正确性无从检验 |
