# 完整功能测试记录

测试执行于 **2026-10-28**，整理提交于 **2026-10-29**。当前功能与浏览器回归针对源码 [`93ce08b`](https://github.com/jrhhhh/math-homework-agent/commit/93ce08b)；历史真实模型教学流程对应 [`b5265ef`](https://github.com/jrhhhh/math-homework-agent/commit/b5265efea88b7933bcd332d5e1bf6c5db1a1e9cd)。本文将不同版本、模型参与方式和验证范围分别标明。

## 结果概览

| 检查 | 结果 | 证据 |
|---|---|---|
| 当前代码单元与集成测试 | 273项通过，其中工作台113项 | [汇总](current/verification.json)、[工作台原始输出](current/workbench.txt) |
| 课件功能回归 | 35项功能断言通过；隐私探针无标识符清单而NOT-RUN，全量脚本退出1，不能记为全部通过 | [原始输出](current/lesson-builder-regression.txt) |
| 当前浏览器交互 | 四组全部通过，使用独立数据库与明确的模型替身 | [结构化结果](current/browser/results.json)、[9张截图](current/browser/screenshots/)、[总览](当前交互-截图总览.png) |
| 历史真实模型教学闭环 | 16个任务最终完成，3次暂停后手动重试成功 | [完整报告](historical-e2e/测试报告.md)、[公开快照](historical-e2e/records/完整运行快照.json)、[36张截图](historical-e2e/screenshots/)、[总览](历史过程-截图总览.png) |
| 新版视觉模板与完整课件 | 6份PPTX、合计75页通过结构与几何检查；保留21页完整课例静态预览 | [检查记录](ppt/全部模板结构检查.json)、[21页PNG](ppt/slides/)、[静态PDF](ppt/完整课堂静态预览.pdf) |

## 功能覆盖

| 功能 | 主要检查内容 | 证据 |
|---|---|---|
| 任务设计与发布 | 教学目标、成功标准、固定原题、学生领取 | [历史任务草案](historical-e2e/records/01-task-design.txt)、[当前教学闭环](current/browser/teaching_loop.txt) |
| 过程诊断与修订 | 首错定位、零因子漏解、当前提交版本、受助修订 | [首次诊断](historical-e2e/records/02-first-attempt.txt)、[重试截图](historical-e2e/screenshots/14b-重试后修订成功.png) |
| 提示与数学活动 | 单步提示、单位圆、函数退化、帮助记录 | [历史提示](historical-e2e/records/07-hint-revision.txt)、[当前活动检查](current/browser/math_widgets.txt) |
| 学习证据与补救教案 | 诊断依据、教案交接、旧证据失效、更新规划 | [补救规划](historical-e2e/records/03-remedial-plan.txt)、[更新规划](historical-e2e/records/08-refresh-plan.txt) |
| 独立新题复核 | 同目标新题、提交前帮助条件、结果表述边界 | [真实模型记录](historical-e2e/records/09-independent.txt)、[当前学习路径](current/browser/learning_path.txt) |
| 完整求解 | 例题求解、分支和区间结果、输出门 | [真实模型记录](historical-e2e/records/extra-solver.txt) |
| 正解优化 | 先诊断后优化、失败输出修正、结构与措辞门 | [真实模型记录](historical-e2e/records/extra-refine.txt)、[当前输出门测试](current/root-tests.txt) |
| 草稿习惯与分块 | 文字版面描述、分区、自纠、归属待确认；不冒充数学诊断 | [反馈](historical-e2e/records/extra-draft-view.txt)、[分块](historical-e2e/records/extra-partition.txt) |
| 仅答案与完整纠正 | 缺过程时的边界、纠正模式 | [记录](historical-e2e/records/extra-modes.txt) |
| 备课与课件生成 | 大纲确认、源码、渲染、可编辑文字、原生版式、教师备注 | [历史源码阶段](historical-e2e/records/05-lesson-source.txt)、[新版课件验收](ppt/交付记录.md)、[当前集成测试](current/workbench.txt) |
| 任务队列 | 任务状态、重试、重启与回执、文件改动后重建 | [历史任务事件](historical-e2e/records/完整运行快照.json)、[当前任务与崩溃恢复测试](current/workbench.txt) |
| UI与附件 | 文字提取、键盘提交、弹窗焦点、工作区导航、减少动效、320至1440像素宽度 | [当前界面测试](current/browser/glass_ui.txt) |
| 数学核对 | 固定题型、独立解集计算、结构门与数学检查的区别 | [历史计算代码](historical-e2e/records/check_math.py)、[计算输出](historical-e2e/records/math-check.json)、[当前固定案例](current/math-facts-11.txt) |

## 课件成品

- [绛红书院主题](../../../lesson-materials-builder/assets/themes/scholar-red.pptx) · [渲染预览](ppt/scholar-red.preview.png)
- [墨青研习主题](../../../lesson-materials-builder/assets/themes/ink-teal.pptx) · [渲染预览](ppt/ink-teal.preview.png)
- [21页完整课堂PPTX](../../../lesson-materials-builder/assets/examples/trigonometric/lesson.pptx) · [源码](../../../lesson-materials-builder/assets/examples/trigonometric/lesson.md)

历史真实模型流程生成的旧版10页课件只代表其记录时的版本，不用于展示当前模板效果。新版课件采用后来改进的内容与视觉实现，不能把其效果归给历史流程。

## 复现与证据边界

见[复现说明](复现说明.md)。当前浏览器检查在真实浏览器运行，推理后端是显式替身，只验证交互与状态转换；历史流程调用了真实模型，使用合成教师/学生输入，未固定当时账号默认模型版本和宿主环境，不保证逐字重现。

测试不是实际课堂试教，也不是教学效果或模型总体准确率评测。静态PPT预览不验证目标放映软件的动画。历史报告中的问题属于当时版本，不能不经复测就视为当前缺陷。公开快照省略模型工具事件和本机绝对路径，保留任务事件、模型输出与门结果；本地数据库、账号配置、缓存和无关实验未公开。整理说明见[publication.json](publication.json)，文件完整性见[manifest.json](manifest.json)。
