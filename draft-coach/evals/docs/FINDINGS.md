# 建这套基准时实际发现的东西

下面每一条都有可复现的命令或指向具体案例/断言，不是感想。

## F1 正确的卡片会被技能自己的严格门判为不通过（DIM-04）

`scripts/_rules.py` 的 `PROBLEM_MARKER_RE` 把**带圈序号**当作题号标记。学生用「方法①／方法②」标同一道题的两条路径时，草稿被判成「整张纸不止一道题」，`audit --strict` 报 `W_MULTI_PROBLEM_DRAFT` 并退出 1。

[`DIM-04`](../cases.jsonl) 正是这个形状：一道 `x²-6x+5=0`，方法①（因式分解，写错后整段划掉）与方法②（配方，正确）。**关于它的卡片可以完全正确，却过不了严格门。**

复现：

```bash
python3 -c "
import json,sys,importlib.util
sys.path.insert(0,'engine')
import gate_replay; from cases import load_cases
c=[x for x in load_cases('.') if x['case_id']=='DIM-04'][0]
spec=importlib.util.spec_from_file_location('f','make_fixture_predictions.py')
f=importlib.util.module_from_spec(spec); spec.loader.exec_module(f)
cfg=json.load(open('config.json',encoding='utf-8'))
print(gate_replay.replay_card(cfg, f.build_oracle_card(c), gate_replay.audit_draft_for(c))['audit_strict'])
"
```

影响：SKILL.md 的 Core Rule 8 是「未过门不得交付」。遇到这种草稿，agent 要么改一份本来正确的卡片，要么如实报「卡在某一条」——两者对学生都不是好结果。**基准不改数据集去迁就它**（DIM-04 本来就只有一道题，不该设 `audit_draft`），而是把它钉在 [`tests/test_end_to_end.py`](../tests/test_end_to_end.py) 的 `KnownGateFalsePositiveTests` 里：一旦扩散到别的案例，测试就失败。

建议（不在本基准范围内）：把「方法标记」与「题号标记」区分开，或让 `W_MULTI_PROBLEM_DRAFT` 在 `--strict` 下不至于致命。

## F2 技能自己的标准拒绝话术，会被自己的越界规则扫中

`refuse --reason out_of_scope` 的标准话术是「……要优化已经做对的解法，或者要**变式题**、**复习计划**，请交给对应的技能。」——它**必须**点名这些词才能把请求退回去，而 `A_VARIANT` 与 `A_PLAN` 的正则正好命中这些词。

技能自身的 `audit` 只扫**卡片文本**，所以正常流程不会踩到；但任何扫描**交付给学生的那段文字**的消费者（本基准最初就是这样）都会误报。基准现在的处理是：扫描前先剥掉三条标准话术（`metrics.strip_refusal_wording`），并留了断言 [`test_metrics.py::test_standard_refusal_wording_is_not_a_boundary_violation`](../tests/test_metrics.py)。答案若真去出变式题，写的是自己的话，照样会被扫到。

建议：在 SKILL.md 里明确「标准话术本身豁免越界扫描」，免得下游各自决定。

## F3 「整张草稿纸」必须按块过门，口径不写死就会冤枉所有合规卡片

一块一道题一张卡，`--draft` 只传**那一块**（SKILL.md 明写）。若拿整张纸去审一张块级卡片，任何合规卡片都会触发 `W_MULTI_PROBLEM_DRAFT`。基准把这件事做成案例里的显式字段 `input.audit_draft`（如 [`CPLX-01`](../cases.jsonl)、[`TOOL-06`](../cases.jsonl)），门层优先用它并记录 `audit_draft_source`。

这与早先在 `tests/behavior-evaluation/draft-coach-2026-10-15/` 里踩到的是同一个坑：**口径问题而不是卡片问题，改的是基准不是卡片。**

## F4 「什么错都不报」在证据忠实度上拿满分

空答案（`errors: []`）没有任何证据，也就无从判断证据是否忠实，于是 `evidence_subset` 只剩一项指标有分母，分数是 100。它真正的失分在 A 子集的 Recall 上。

基准的应对不是硬造一个惩罚项，而是把**覆盖度**摆在报告里：每个子集列出「自动指标已用/可用」与「最小自动分母」，并给出 `thin` 标记。空答案的报告里 `A`、`B`、`F` 三个子集都会标 `thin`。

**读加权总分时必须连着覆盖度一起读**，尤其是不同组的覆盖不一致时——否则「93 分」和「100 分」可能不是一回事。

## F5 匹配口径本身会造出草稿里不存在的式子（建基准时踩到并修掉）

最初把预测的 `evidence` 与 `location` 拼成一个串再找锚点子串。归一化会去掉空白，于是两栏都是 `x=12/7` 时拼出 `x=12/7x=12/7`，其中**意外含有** `7x=12`——这条预测被错判成命中了 gold 里 `7x=12` 那条错误，真正的错误反而成了假阳性，`cross_block_false_positive_avoidance` 因此从 100 掉到 83。

修法是逐字段比对（`metrics.pred_fields`），并留了 [`test_metrics.py::test_fields_are_matched_separately_not_concatenated`](../tests/test_metrics.py)。**任何重写这套指标的人都会踩同一个坑。**

## F6 锚点比对不能去掉括号，否则引用原式会虚高 Recall

`scripts/_rules.py` 的 `norm` 会连括号一起去掉，于是原式 `2(x+3)=14` 与漏乘后的错误式 `2x+3=14` 归一成同一个串。答案只要引用原式，就会被判成命中了「去括号漏乘」那条错误，**Recall 被虚高**。

基准对锚点改用 `normalise_strict`（只去空白、统一全角，保留括号与运算符）；记号级比对仍沿用技能自己的口径。

## F7 数据集自身也要能验「证据必须有草稿依据」

每条 `evidence_anchor` 被强制要求**逐字出现在 `input.draft` 里**（`E_ANCHOR_NOT_IN_DRAFT`），`gold_correct_steps` 与 `gold_errors` 的锚点不许重叠（`E_ANCHOR_CONFLICT`）。这把技能里那条最重要的约束（「报一处草稿里根本没有的错误是最严重的失误」）前移到了数据层：**标注写错锚点的案例根本进不了库。**

38 个案例在严格锚点下 0 error、0 warning。

## F8 没有观察到严重失败 ≠ 不会失败

三个夹具里只有一个（故意编造的 `fabricated`）触发了严重失败，共 39 条（`S1` 19 条、`S5` 20 条）。**这是夹具，不是模型。** 本批**没有任何真实模型输出**，所以关于三组实验的真实行为，这套基准目前给不出结论——它能给出的是：流程跑得通、该抓的抓得住、四条自动严重失败检测（S1/S2/S4/S5）都有真实触发的证据。
