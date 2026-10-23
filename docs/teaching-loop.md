# 师生任务交接协议

## 运行与教学链

运行 `python3 run.py` 后打开本机工作台，选择“师生任务”。本轮新增三个 Skill：学习任务设计（learning-task-designer）、学习证据汇总（learning-evidence-bridge）与补救教学规划（remedial-lesson-planner）。原有求解、诊断、正解优化、草稿反馈、课件技能职责不变。

1. 教师填写任务标题、教材材料/目标与原题。也可依据目标起草题目；模型草案标注未做数学核验，教师可编辑每题原题与目标，检查后发布。
2. 发布创建固定原题的任务项；学生点击“领取并作答”，进入既有学生练习表单。填写自己的过程，选择检查或提示并提交。题目、来源或学段改了，旧绑定不继承正确性；再领取时创建正确原题的新会话，旧会话仍保留。
3. 教师刷新当前证据，按任务项查看最新提交：未提交/诊断中/诊断不可用/绑定变化/待补充/过程正确/过程有错/论证缺口/仅答案。不能把重复修订当成多个独立样本。只给提示不等于完整过程诊断。
4. 有有效过程诊断时，可起草补救或巩固教案。模型只接收固定题目、目标、当前诊断及必要引用，不接收任务标题和自由备注；草稿必须引用真实当前 submission ID，数学合理性仍需教师审阅，分享前检查题目和引文中的身份信息。
5. 教师编辑草稿后转入“教师备课”，补齐教材、年级、课时，按原流程确认逐页大纲、生成源码与课件。也可发布关联的再练习，再练习的出题输入会带上当前证据。新的作答再由诊断技能检查。

本机服务是单设备协作演示：教师与学生共用数据库和可见页面，没有独立身份认证、跨设备访问或班级权限；统计单位是任务项而非学生人数或班级正确率。不把按钮切换称为角色权限隔离。生成草案、诊断和补救建议均是模型辅助；接口检查不证明数学正确或教学有效。

## 数据与版本

- `teaching_tasks`：不可变任务内容、前序任务 ID/证据版本、最新教案草稿。
- `teaching_items`：固定 `problem`、`objective`、任务项 ID 与绑定的 `session_id`。
- 学生的 `submissions` 继续不可变，按 revision 标记当前版本。报告从绑定练习的最新提交实时生成，不拷贝旧判断。
- `evidence_version` 对逐题当前证据计算 SHA256，包含 submission ID、revision、内容版本、状态及首错依据。新的提交、运行状态或诊断变化导致指纹变化。
- 草稿保存 assignment ID、证据版本和当前提交 ID。生成期间证据变化会拒绝保存；交给备课前重查版本，备课记录持久化 teaching_source，并在大纲、源码、渲染接口再次检查；发布关联再练习也由服务端重查。旧计划可保留作历史，但标记过期。
- 提示与仅答案不能被回传为完整过程正确性判断；失败结果不被作为错误过程统计。草稿版面结果不推断数学障碍。

## HTTP 接口

| 方法与路径 | 作用 |
| --- | --- |
| `GET /api/teaching` | 列出本机已发布任务 |
| `POST /api/teaching/design` | 从 title/objective 起草任务，返回待审 items；可带 parent_id/evidence_version |
| `POST /api/teaching` | 发布固定题目，输入 title/items；再练习带 parent_id/evidence_version |
| `GET /api/teaching/{id}` | 获取任务、绑定会话及教案过期状态 |
| `POST /api/teaching/{id}/open/{item_id}` | 领取/继续任务，返回原题与绑定 session_id |
| `POST /api/sessions/{session_id}/submissions` | 原有学生作答与异步诊断入口 |
| `GET /api/teaching/{id}/evidence` | 实时汇总当前提交状态 |
| `POST /api/teaching/{id}/plan` | 依据当前有效诊断起草教师教案 |

生成大纲仍由 `POST /api/lessons/outline` 执行；任务页只带入可编辑草稿，不跳过教师参数核对或大纲确认。服务只绑定 loopback，沿用 Origin 与 JSON 请求限制。任务仅含学生题目和目标，不保存教师标准答案；求解稿应保存在教师侧，不能塞入学生任务字段。

## 验证与范围

`python3 -m unittest app.tests.test_teaching_loop -v` 验证发布与领取、异步诊断回传、重复修订不重复计数、原题/学段/来源变更、失败/提示/仅答案分流、旧证据拒绝再练习、生成中证据变化及缺失提交引用。HTTP 测试验证服务端接口。新测试的模型响应是明确的测试替身，不能写成真实模型教学效果实验；此前三组模型辅助评测也不能用来证明新技能增益。

完整验收仍用 `python3 scripts/verify_all.py`，Builder 隐私探针需要 BENCH_IDENTIFIERS；测试标记不等于实际学生身份审查。Skill 结构由 skill-creator 的 quick_validate 检查，结构合格不证明行为质量。真人复核与教学效果跟踪仍为后续工作。


## 可复现浏览器与真实模型冒烟

浏览器全链路使用独立临时数据库和明确标记的测试替身，不会调用真实模型：

```bash
python3 app/tests/browser/serve_fixture.py --port 8767
# 在另一个终端，通过已安装的 playwright-cli 或本机 Skill 包装器运行：
playwright-cli --session teaching-loop open http://127.0.0.1:8767/
playwright-cli --session teaching-loop run-code --filename app/tests/browser/teaching_loop.js
```

脚本覆盖布置、领取、作答、诊断回传、教案交接、关联再练习、修订与旧计划失效，并截图检查 1280/390 两个视口。截图输出到 `output/playwright/`。检查结果存于 `docs/delivery/evidence/teaching-loop-browser.json`，模型与诊断为测试替身，不表示真实教学效果。

真实模型接口冒烟需显式运行 `python3 scripts/smoke_teaching_loop.py --real-model`：实际调用 Codex CLI 两次，检查任务草案与教师教案输出。教案依据使用明确的合成学生诊断，不能当作真实学生或教学质量实验。当前两次真实调用均成功，原始返回、耗时与用量保存在 `docs/delivery/evidence/teaching-loop-model-smoke.json`。
