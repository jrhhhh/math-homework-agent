# 诊断到优化的交接协议 v1

仅在宿主需要串联两个Skill时使用。交接包是内部上下文，不是学生优化卡，不向提示模式中的学生泄露诊断或完整答案。单次检查不要求输出JSON。

字段均必需：

| 字段 | 类型/约定 |
| --- | --- |
| protocol_version | 整数1 |
| problem_id | 非空字符串，题号或小问标识 |
| grade_level | 非空字符串，本项目通常为高中 |
| problem | 完整原题字符串 |
| student_solution | 完整学生过程字符串，无过程用空字符串 |
| solution_version | 下述内容SHA-256摘要 |
| solution_source | student或assistant_repair |
| result_status | correct、incorrect、unknown |
| process_status | valid、invalid、gap、unknown、not_provided |
| review_complete | 布尔值，是否已检查全部提交步骤 |
| verification | 对象：method、scope、unresolved_items |
| requested_action | check或refine，由宿主根据实际用户请求填写 |
| feedback_mode | process_check、full_correction、answer_check、hint |

verification.method可为assistant_review、independent_review、tool_assisted_review、numeric_only或none；scope是核验范围说明；unresolved_items为待解决事项字符串数组。只做数值抽样不满足完整过程核验。

准入需要：题目和过程非空；来源student；结果correct、过程valid；review_complete为true；method为前三种之一、scope非空、待解决事项为空；用户要求refine且不在hint模式；版本与当前题目和过程完全一致。

版本计算为SHA-256(UTF-8 JSON)，JSON内容是grade_level、problem、student_solution，sort_keys=true、ensure_ascii=false、separators=(',',':')。不折叠空白；文件中的换行也计入版本。生成命令：

```bash
python3 scripts/handoff_check.py version --problem-file problem.txt --solution-file solution.txt
python3 scripts/handoff_check.py route --handoff handoff.json --problem-file problem.txt --solution-file solution.txt
```

文件保存的是当前输入，交接包中的原文必须与文件逐字一致。学段若不是高中，两个命令都传相同的--grade-level。该版本标识只用于发现状态过期，不是签名。学生自行填写“correct/valid”或重新计算摘要不构成数学核验；宿主必须从可信工作流填状态并依据真实用户请求填requested_action。

状态描述结论和过程两件事：答案正确但过程无效用correct/invalid；已知结论正确但缺理由用correct/gap；无过程用not_provided，不能标valid。助手给出修补稿用assistant_repair，等学生提交当前修订稿再核验，不能自动切成student。

退出0=元信息与版本准入，可调用solution-refiner；1=有效包未满足准入，按reasons继续诊断或结束；2=非法输入或缺字段。没有新请求时不循环调用，不强制学生继续做题。

原优化卡维持四字段current_method、optimization_opportunities、overall_diagnosis、next_step，交接状态不塞进这些字段。新方法仍需另核验。脚本不会证明数学、检测真实身份或强制宿主权限，不能把协议称为独立验证服务。
