# 高中数学作业项目的 Agent 调度约定

本文件是项目根目录的 Agent 入口（AGENTS.md）。Agent 决定调用时机，三个 Skill 分别提供诊断、优化和草稿习惯分析的方法。默认使用中文和高中方法，尊重用户的反馈模式。

## 技能与职责

- skill：**Math Error Diagnosis**（`math-error-diagnosis/SKILL.md`）：检查题目、答案和解答过程，定位首错，给最小修改；处理信息不足、论证缺口与答案正确但过程有误。
- skill：**Solution Refiner**（`solution-refiner/SKILL.md`）：对结论和完整过程已成立的当前学生解答提供优化卡。不承担原解答判错或修补。
- skill：**Draft Coach**（`draft-coach/SKILL.md`）：看学生**草稿**——首要检查草稿里的计算错误，其次分析过程习惯（分区组织、跳步、涂改、试错、画图、草稿利用率）——输出错误清单 + 六维观察 + 习惯 + 下一道题可执行的动作。完整卡 3 条习惯；学生只给照片、没有文字描述时出**版面卡**（只依据版面，错误清单为空，习惯 1–3 条）；学生愿意逐行核对机器候选时，确认稿（`machine_transcription`）可当内容。不诊断知识漏洞、不贴标签、不给整题重写、不出变式题、不排复习计划。

未包含 presolve-starter；不会开始时可给起步帮助，但不要声称调用未安装技能。本项目**不内置任何识别引擎**：机器候选转写由宿主提供，本仓只校验它的形状与"是否经过学生确认"的声明。**未确认的机器读数不是内容**——不许拿它报错，也不许当 `--draft` 的依据；学生**逐行**核对后的确认稿才算（见 [draft-coach/references/transcription.md](draft-coach/references/transcription.md)）。原有的自我作证风险见 [draft-coach/references/image-intake.md](draft-coach/references/image-intake.md) 第一条。注意这些约束只针对**内容**：版面（分块、涂改、图形、行序）本来就必须由助手自己看，版面卡就是这么来的。

## 调度

1. 收集原题与学生实际过程，先调用 math-error-diagnosis。只有答案时可核对结果，但不准入优化。
2. 解答有错或论证缺口：给诊断/修补或提示，等待学生修订并重新检查。助手修补稿不冒充学生解答。
3. 只有结论正确、完整过程成立、核验无未解决项、来源为学生，而且用户要求优化时，准备独立交接包。
4. 交接包按 [协议](docs/handoff-protocol.md) 保存；运行 `python3 scripts/handoff_check.py route --handoff handoff.json --problem-file problem.txt --solution-file solution.txt`。以当前题目与过程文件比较版本，退出 0 才可进入 solution-refiner；1 表示不准入，2 表示输入或协议非法。脚本通过只验证元信息与版本，不验证数学或用户授权真实性。
5. 优化卡与诊断报告分开。先由宿主核验建议的数学有效性、学段允许性和实际改进，再按 solution-refiner 运行 validate 和 audit，保存真实输出。推荐 `audit --strict` 并人工检查告警；不能用两道门代替数学检查。
6. 用户只要求检查时完成检查即可，不强制优化。用户要求提示时持续一次一个提示，不因自动调度泄露解答。
7. 学生改变题目、参数、过程或提交新方法后旧检查失效，重新调用诊断；不能把旧解答的正确性状态转给新解答。

问题有多个小问时按题号绑定各自题目、过程与状态，检查依赖，不用某一小问通过替代整套作业核验。优化阶段发现检查遗漏时停止交付，由宿主重新诊断，不能把判错文字藏进优化卡。

## draft-coach 的选用条件

draft-coach **不在这条交接链路里**，它是横着长出来的第三条路：它**不消费交接包**，也不要求 `result_status` 是什么。

**它和 math-error-diagnosis 都查错，分界线靠输入：**

- 学生交的是**作业本 / 答卷上的正式解答** → `math-error-diagnosis`：首错定位、最小修改、分层提示，有六份题型清单。
- 学生交的是**草稿纸** → `draft-coach`：计算错误清单 + 过程习惯。
- **两者不可互相替代**：draft-coach 没有题型清单，只覆盖草稿上看得见的计算，也**不做首错定位和分层提示**；math-error-diagnosis 不做过程习惯分析。

其余边界：

- 用 draft-coach：学生**提供了草稿**（文字还原，或他自己对一张手写照片的文字描述），并问对错、哪里算错了、草稿组织、跳步、涂改、试错、画图或草稿利用率；**只给了一张手写照片、没有文字描述**时也用它——出的是版面卡（不含计算错误判断），或走机器候选 + 学生逐行核对（`machine_transcription`）。
  **不用于**没有任何草稿时（只给题目、只给最终答案或只有答卷）；
  **不用于**已成立解答的优化（转 solution-refiner）；
  **不诊断知识漏洞、不贴标签、不给整题重写、不出变式题、不排复习计划、不评分扣分**。
- **缺原题时查错要降级**：只能查草稿内部自洽，且必须写进卡片的 `error_check.scope`；不得含糊成"检查过了"。
- draft-coach 的卡片过两道门，**分处两个脚本**：`scripts/validate_output.py validate`（结构）与 `scripts/audit_output.py audit`（越界 + **错误证据是否出自草稿**）。
  两者共用常量模块 `scripts/_rules.py`（六维键名、越界正则、`REFUSALS`、学段表都在那里）；判据冲突时以脚本常量为准。
  它沿用本项目的退出码约定：**0** 通过 / 干净 · **1** 有效但不合格 · **2** 非法输入。
  但查的东西与 handoff_check.py、solution_card_check.py 完全不同，**不可互相替代**。
  **两道门都不验数学**：本技能最核心的声称"这处算错了"恰恰是它唯一验不了的东西，`W_ERROR_NOT_IN_DRAFT` 只能发现"草稿里找不到这处"，发现不了"你判错了"。宿主必须人工复核错误清单。
- `refuse` 的退出码另有一套读法：**2 = 草稿本身不能当证据**（没给 / 给了但用不了）；
  **1 = 草稿没问题，但这个问题不归本技能管**（比如要变式题或复习计划）。判断理由是模型给的，脚本认不出来。
- `clarify` 是**不产出分析卡的第二条出口**：关键记号拿不准、且不同读法会改变结论时，只问 1–5 处（`location` / `question` / `candidates?` / `affects`），学生答后把原话追加进草稿文字再重跑。
  它的退出码是**问题单校验结果**：**0** 有效并输出 · **1** 不合格 · **2** 输入非法——调用方看 `action`（`clarify`），别把 0 当成"卡片已就绪"。
  **候选只能来自学生文字点过名的角色，不许从字形推断**；协议见 [draft-coach/references/key-marks.md](draft-coach/references/key-marks.md)。
- `transcribe` 是**第三条出口**：机器出整份候选（`candidate` + `uncertain[].readings`），学生**逐行**核对/更正后才作 `--draft`，来源写 `machine_transcription`，`scope` 写明"学生已逐行核对，更正 N 处"（否则 `W_TRANSCRIPTION_SCOPE_SILENT`）。
  退出码同为 **0 / 1 / 2**；输出的 `status` 是 `awaiting_student_confirmation`，**0 不表示学生已确认**。候选与机器读法不按助手越界措辞扫描；**识别准确率未经验证，这条路是实验性的**。

## 维护与验证

修改接口后运行 `python3 -m unittest discover -s tests -p 'test_*.py'`；draft-coach 自己的门测试在技能目录内，另跑 `python3 -m unittest discover -s draft-coach/tests -p 'test_*.py'`；它的评测子系统在 `draft-coach/evals/`，跑 `python3 -m unittest discover -s draft-coach/evals/tests -p 'test_*.py'` 与 `python3 draft-coach/evals/engine/schema_check.py`。数学参考资料变化时运行相关固定计算脚本。保留三个技能的职责边界和原优化卡四字段接口；结构核验、同一助手复核和独立验证分别陈述。衔接规则不是自动服务：宿主仍需执行实际数学审查。

改任何门脚本或卡片 schema 后，必须重跑真实输出，不许凭印象写"应该会通过"。同伴仓库的副本只供比对，不是交付物；**不去修改同伴仓库的任何文件**。

**Windows 注意**：`PATH` 里的 `python` / `python3` 可能是应用商店的占位程序，会静默失败、什么都不输出。本机可用的解释器为 `"D:/Program Files/anaconda3/python.exe"`。`tests/test_handoff.py` 用字面量 `"python3"` 起子进程，在本机跑不起来；`draft-coach/tests/` 与 `draft-coach/evals/tests/` 下的测试都用 `sys.executable`，可直接运行。
