# -*- coding: utf-8 -*-
"""假 PIL —— 用来确定性地模拟「这台机器没装 Pillow」。

用法（和 no-fonttools 同一手法）：

    PYTHONPATH=evals/fixtures/no-pillow python scripts/bench.py regress

为什么要有它：`verify_pptx` 的「图片拉伸」与「着墨一致性」两条检查依赖 Pillow。
没装时正确行为不是「当作没问题」，而是**显式记 not_run**。但要验这件事，
不能指望测试机上恰好没装 —— 那就成了「能跑就通过、跑不了就跳过」，
正是本项目最怕的那种假绿。这个挡板让「没装」变成可以随时复现的状态。

导入即抛，与真实缺失时的表现一致。
"""

raise ImportError(
    "fixture: no-pillow —— 这是 evals/fixtures/no-pillow/ 里的挡板，"
    "用来模拟未安装 Pillow。"
)
