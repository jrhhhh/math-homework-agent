# `emph-wrap.md` —— 抓「底部堆叠区的行距静默脱钩」

**这条夹具不是读代码想出来的，是产出层第一次真跑时被抓出来的。**

断言：`reg.emph_spacing`（见 `scripts/bench.py`）→ `reg.emph_spacing.clean`。
撞的告警类别：`verify.spacing.missing`（「行距未显式指定」）。

## 经过

`with_skill` 组的执行子代理报上来：折成两行的 `!!!` 强调块必报
「行距未显式指定」，而作者从 `课件.md` 里**改不掉** —— 只能把句子压成一行。
那是绕过，不是修好。

根因比「多一条告警」深：

- `add_emph()` / `add_question()` 各自手搓形状，**不走 `layout_block`**，
  所以谁也不给它们写 `a:spcPts`；
- 可它们的高度是按 `EMPH_LINE = 0.62` / `QUESTION_LINE = 0.47` 算的，
  渲染行高却由字体的自然行高决定 —— **模型假定 0.62in 一行，实际是另一个数**；
- 两套行距校验（`verify_pptx.py` 的行距扫描、`build_pptx.py` 的
  `check_spacing_written`）当时都只盯 `body-block` / `answer-block`，这类块整片漏掉。

中间对齐只是把误差藏起来，不是消掉它。

## 三页各自钉什么

| 页 | 内容 | 钉住 |
|---|---|---|
| 2 | `!!!` 折成两行 | **修前必红**：这条就是缺陷本身 |
| 3 | `!!!` 只有一行（`短结论`） | **对照**：修完不许所有强调块都多出告警 |
| 4 | `>` 驱动问题折成三行 | 同一根因的另一处 —— 只修强调块就漏了它 |

## 修法与证据

`EMPH_BLOCK` / `QUESTION_BLOCK` 两个形状名，行距写死**与算高同一个常量**，
并纳入 `check_spacing_written` 的名字元组。

```
修前  FAIL —— 报了 1 条：行距未显式指定：Rectangle 3
修后  PASS —— 整份夹具 verify 报 ERROR 0 / WARN 0
```

改完拿三份真卡组重渲染验证没有误伤：好那份 0/0、`with_skill` 产物 0/0、
盲跑那份仍只报它自己那条 P12（P7 那条是旧渲染器的产物，详见
`../warning-categories.json` 里 `verify.flow.ink_mismatch` 的 note）。

## 给夹具作者的一句话

**别把说明写进 `emph-wrap.md` 本身。** 课件解析器逐行处理 `<!--`，
多行 HTML 注释不是注释 —— 整段会被当要点渲染进页面。这就是本文件存在的原因。
