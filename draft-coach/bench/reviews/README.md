# 人工评审（尚未运行）

本目录当前没有人工评分数据。自动层不回答「观察是否属实」「习惯是否适合这个学生」
「next_step 是否可执行」，这三项只走这里。

生成模板：

```bash
python3 engine/human_review.py export \
    --predictions predictions/your-run.json \
    --out reviews/human.template.json
```

把 `review` 里的三个字段填成 `true` / `false` / `null`（`null` = 无法判断，不进分母），
再回读：

```bash
python3 engine/human_review.py merge \
    --reviews reviews/human.filled.json \
    --out reviews/human.summary.json
```

**人工层单独统计，不并入自动分。** 评审者是否独立、是否与产出方同模型，
脚本不验证，必须由运行者自己记录。
