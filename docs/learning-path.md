# 学习路径与任务恢复

工作台沿用本地单设备、共用数据库的协作方式。每道发布题目固定保存原题、学习目标、成功标准、教师提示和可选数学活动。没有账号隔离或跨设备班级访问。

## 教学流程

教师先确定学生需要展示的推理，再写成功标准，最后选择题目。模型草案必须包含 `problem/objective/success_criteria`；旧任务和旧 API 手工数据缺少标准时以目标兼容显示，不能据此宣称已完成有效测量。草案不自动发布，教师检查数学内容和可解性后发布。

“按学习路径学习”连接自己尝试、按需帮助、动手观察和新题复核。场景可以自由返回，避免为了走完流程强制学生先看讲解。活动仅提供二次函数参数、单位圆、割线与切线固定组件；不运行模型生成的 JavaScript。单位圆等比例绘图；二次项为零时说明已退化，差商步长为零时显示导数极限图示，不计算 0/0。组件是受限演示，不是通用图形计算器，也不能替代学生推理。

## 帮助条件与复核

提交保存本题当前练习会话当时的帮助快照，后续提示不会回写历史提交。没有学习者账号，系统不把其他练习会话的帮助归给当前学生；跨任务链见过等价题的情况需使用者补记。请求提示、完整讲解、查看教师提示、打开活动及补记外部帮助均进入记录。内容生成完成记录的是“可用”，不声称学生已阅读。完整讲解请求即使失败，也不能再把之后提交视作未请求帮助。

教师汇总区分别显示过程状态与帮助条件。重新绑定同一任务原题会保留该题的已知帮助记录。旧数据库没有完整帮助日志，显示条件不明，不补造独立完成记录。

独立复核需从当前有效诊断教案布置关联任务，选择前序任务项，沿用目标和成功标准，并提供同一教学链中未发布过的新题。原题和兄弟复核题的文字重复、同一复核任务内部重复均拒绝。文字归一化去重不识别数学等价题；目标匹配不证明难度等价，教师仍需审查。

`independent_check_passed` 仅在新题当前完整过程诊断正确、提交前未记录帮助时成立。它描述本题在已记录条件下的表现，不证明没有外部帮助或已稳定掌握。普通受助修订正确不转为独立复核。教师补救计划保留帮助条件及证据版本。

## 持久任务中心

浏览器中的过程诊断、任务草案、补救规划、课件大纲、课件源码与渲染进入 SQLite 队列。最多四个排队或运行任务，两个工作线程。关页或刷新不取消任务；从任务中心查看结果。相同请求编号与相同输入复用任务，不同输入拒绝复用编号。

状态为 `queued → running → completed`，失败转 `paused`，人工停止转 `cancelled`。服务重启把运行中任务暂停，用户选择继续后才恢复；已排队任务可正常执行。停止在当前模型调用或脚本返回后的步骤边界生效，不会立即中止外部进程。失败不会自动无限重试。

任务阶段回执、事件及结果持久保存。课件配图、构建、独立检查分别保存输入签名和文件 SHA-256；输入、模板、Builder 脚本或产物变化后重新执行相关阶段。任务不提供跨进程严格 exactly-once：若模型返回之后、回执持久化之前进程退出，该调用可能重做。部分备课文件夹可能保留中间产物；最终状态以独立检查为准。

同一课件的活动任务互斥，重试同样检查。旧的同步备课与教学 API 保留兼容，直接调用这些旧接口不享受后台恢复保证。它们仍检查证据版本。SQLite 本地锁防止同一数据库同时运行多个工作台实例。

## 接口

| 方法与路径 | 内容 |
| --- | --- |
| `GET /api/teaching/{task}/path/{item}` | 目标、标准、场景、当前证据、尝试、帮助、关联新题 |
| `POST /api/sessions/{sid}/support` | `kind/problem/detail`；仅接受显式帮助类型 |
| `POST /api/math-widget` | `template` 和受限数值参数，返回计算数据 |
| `POST /api/jobs` | `kind/payload/request_key`，返回公开任务视图 |
| `GET /api/jobs`、`GET /api/jobs/{id}` | 状态、事件、完成阶段和可交付结果；不返回原始任务参数或回执内容 |
| `POST /api/jobs/{id}/retry`、`cancel` | 手动继续或请求停止 |

教学结构约束在 [constraints.json](../learning-task-designer/constraints.json)，由提示、服务器校验和学生路径共同使用。帮助记录仍包含学生自填文本；分享或导出时须按原有隐私规则审查。

## 借鉴来源

设计参考清华大学 [OpenMAIC](https://github.com/THU-MAIC/OpenMAIC)，审阅基线为 `84a88bc4fda25c6e4ff10323e68169ce013f6186`。本次独立实现教学流程与受限组件，没有复制其源代码或引入其依赖。

- [最近发展区指导](https://github.com/THU-MAIC/OpenMAIC/blob/84a88bc4fda25c6e4ff10323e68169ce013f6186/skills/agent-runtime/zone-of-proximal-development/SKILL.md)：帮助后表现与独立尝试分开；本项目以提交快照及关联新题落实。
- [逆向教学设计](https://github.com/THU-MAIC/OpenMAIC/blob/84a88bc4fda25c6e4ff10323e68169ce013f6186/skills/agent-runtime/understanding-by-design/SKILL.md)：目标、可观察证据与学习活动对应。
- [运行引擎](https://github.com/THU-MAIC/OpenMAIC/blob/84a88bc4fda25c6e4ff10323e68169ce013f6186/lib/server/generation/run/engine.ts)：长流程分阶段保存与恢复。本项目采用本地 SQLite 和人工重试，未照搬其分布式运行结构。

这些实现与接口测试不构成学习效果实验证据。模型辅助评测保留原冻结范围，真人复核仍为后续工作。


## 复现

```bash
python3 -m unittest discover -s app/tests -p 'test_*.py'
python3 scripts/smoke_teaching_loop.py --real-model
# 独立终端启动隔离替身服务，仅用于 UI 验收
python3 app/tests/browser/serve_fixture.py --port 8767
```

Playwright CLI 打开 `http://127.0.0.1:8767/` 后依次以 `run-code --filename` 运行 `app/tests/browser/teaching_loop.js`、`learning_path.js`、`math_widgets.js`。文件是接收 `page` 的异步函数；截图保存在 `output/playwright/`。替身数据只在临时数据库，不进入正式工作台。结果摘要见 [浏览器记录](delivery/evidence/browser-learning-path.json)。
