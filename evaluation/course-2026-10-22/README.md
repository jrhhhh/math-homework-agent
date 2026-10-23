# 课程大作业三组真实对照

本轮新增 30 个案例：10 个求解、14 个学生解答检查（含 4 个单提示和 2 个仅答案）、6 个草稿版面案例。
先编写案例与真值，再冻结技能、输出契约与运行代码；本轮输出不得用于修改冻结技能。

三组共用同一 Codex CLI 配置、模型后端与输出结构。`baseline` 不加载本仓库技能；`skill` 加载技能但只生成一次；`skill_gates` 加载相同技能，并在校验失败时将真实失败信息反馈，最多修正两次。各组最终输出都重放同一套门，只有第三组收到重放反馈。

```bash
python3 evaluation/course-2026-10-22/run_experiment.py --workers 2
python3 evaluation/course-2026-10-22/review.py packets
python3 evaluation/course-2026-10-22/review.py assisted
```

运行器不读 `gold.jsonl`。每题每条件使用新上下文；原始 prompt、模型输出、事件、用量、耗时、门退出码逐次保存。
`runs/initial/manifest.json` 保存冻结文件 SHA256；不能把更改后的代码输出混进同一实验。
每个样本使用独立文件，成功结果可续跑，失败记录不静默覆盖。

评审包逐题随机排列 A/B/C，作答者不接触真值与评审标准答案，模型核验者只看到原题及匿名输出，自行检查。
`review/mapping.json` 只供事后汇总，不能发给盲评者。
`runs/recovered/review/human.template.json` 是 10 题的真实人员复核包；评分初始为 null。本轮按用户决定先交付模型辅助评测，未进行真人复核。后续教师或同学实际填写后另存为 `human.completed.json`，运行：

```bash
python3 evaluation/course-2026-10-22/review.py human --file evaluation/course-2026-10-22/runs/recovered/review/human.completed.json
```

边界：新编案例只表示未用于本轮调试，不是外部独立抽样；每条件一次不能证明稳定增益。相同模型不同上下文核验不是人工、异模型或形式化验证。
公共输出契约含任务约束，所以本轮估计的是在相同接口基础上，技能文档与门反馈的额外作用，不是无约束聊天对比。
CLI 自带全局指令和用户模型配置在三组中相同；若无法取得服务端精确模型快照，需要如实保留该限制。CLI 返回 token 用量；未取得可验证账单价格时不编造货币费用。


## 初次运行与补跑

初次运行 `runs/initial/` 保留全部90条请求记录，其中38条取得有效模型输出、52条调用层失败。原适配器只保存了通用失败信息，不能据此断言具体网络根因。最小请求恢复后，使用 `recover.py` 串行补跑失败条目，保存到 `runs/recovered/`；初次有效结果逐字节沿用，不挑选更好的回答。补跑不算独立重复实验，也不能掩盖服务中断对时间/顺序的影响。

```bash
python3 evaluation/course-2026-10-22/recover.py
python3 evaluation/course-2026-10-22/review.py assisted --run evaluation/course-2026-10-22/runs/recovered
python3 evaluation/course-2026-10-22/render_human_form.py
python3 evaluation/course-2026-10-22/summarize.py --run evaluation/course-2026-10-22/runs/recovered
```

`provenance.json` 区分初次成功与补跑结果。已归档冻结源码可供复现；后续工作台新增的工具核验不属于该轮三组对照。后台模型失败的诊断分类已在当前工作台改进，但不会改写旧记录。
