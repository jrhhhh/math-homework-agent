# -*- coding: utf-8 -*-
"""假 fontTools —— 用来确定性地模拟「这台机器没装 fontTools」。

用法：把它所在的目录塞进 PYTHONPATH，真实的 fontTools 就被这个挡在后面：

    PYTHONPATH=evals/fixtures/no-fonttools python scripts/build_pptx.py ...

为什么要有它：字形检查查不到时，正确行为是**明说「字形覆盖未检查」**，而不是
安静地当作没问题。但要验这件事，不能指望测试机上恰好没装 fontTools ——
那就成了「能跑就通过、跑不了就跳过」，正是本项目最怕的那种假绿。
这个挡板让「没装」变成一个可以随时复现的状态。

导入即抛，与真实缺失时的表现一致。
"""

raise ImportError(
    "fixture: no-fonttools —— 这是 evals/fixtures/no-fonttools/ 里的挡板，"
    "用来模拟未安装 fontTools。"
)
