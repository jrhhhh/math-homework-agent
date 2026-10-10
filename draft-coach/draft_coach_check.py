#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""draft_coach_check.py — "草稿习惯分析卡"的结构门与越界审计。

用法：
  validate --card CARD.json
  audit    --card CARD.json --draft "草稿内容" [--final-solution "最终解答"] [--strict]
  hint     --draft "草稿内容" [--grade-level 高中]
  refuse   --reason empty|unreadable|out_of_scope

约定：
  - 所有结果以 JSON 打到 stdout；
  - 退出码：0 = 通过 / 干净；1 = 未通过（有 error，或 --strict 下出现 warning）；
    2 = 输入非法。refuse 另有一套映射，见 REFUSALS。
  - 仅使用 Python 标准库，无第三方依赖。

能力边界（诚实声明，别把它当正确性证明）：
  - 结构门只查"卡片长得对不对"：六个维度是否齐全、评分是否在取值集合内、
    证据与风险是否填了、习惯是否恰好 3 条、学段与草稿来源是否合法。
    **它不判断这条习惯观察在数学上是否站得住**——那要人来读。
  - 越界审计靠措辞规则，抓的是"判对错 / 诊断知识漏洞 / 给学生贴标签 / 排题量计划 /
    出变式题 / 给出完整解答"。它是便宜的确定性门，不是语义理解；换个说法绕过去，
    它抓不住。抓不住"修复句"本身：修复句的前提是判错，D_JUDGE / D_CAUSE 抓那个前提。
  - 本技能的核心词汇——跳步、涂改、划掉、心算、漏根——**不在**禁列。
    "如果 x²=1 写成 x=1，就会漏根"是假设性风险，合法；"这一步错了"才是判对错。
  - 草稿关联度用记号重合判断，只认多位数字与 ASCII 标识符，短草稿可能整段跳过
    这项检查（和 solution-refiner 的 W_DETACHED_SOLUTION 同性质）。
"""

import argparse
import json
import re
import sys

try:  # Windows 控制台默认编码可能是 GBK，统一成 UTF-8，免得中文与数学符号炸掉
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------- 常量

DIMENSIONS_FIELD = "dimensions"
HABIT_FIELD = "top_3_habits"
REQUIRED_FIELDS = (DIMENSIONS_FIELD, HABIT_FIELD, "next_step", "grade_level", "draft_source")

# 六个分析维度，键名固定、顺序固定
DIM_KEYS = ("organization", "skipping", "correction_pattern",
            "trial_and_error", "graphic_use", "draft_to_solution")
DIM_LABEL = {
    "organization": "组织度",
    "skipping": "跳步模式",
    "correction_pattern": "涂改模式",
    "trial_and_error": "试错痕迹",
    "graphic_use": "图形使用",
    "draft_to_solution": "草稿利用率",
}
DIM_FIELDS = ("score", "observation", "evidence", "risk")
POSITIVE_DIM = "correction_pattern"   # 只有涂改模式允许 positive 字段

SCORES = ("高", "中", "低")
# 没有最终解答时，"草稿利用率"无法评分。宁可留空，也不虚构一个分数。
UNAVAILABLE = "不适用"
SCORES_LAST = SCORES + (UNAVAILABLE,)   # 仅 draft_to_solution 允许

HABIT_FIELDS = ("habit", "impact", "training")
HABIT_COUNT = 3

GRADES = ("小学", "初中", "高中", "大学")
DEFAULT_GRADE = "高中"
SOURCES = ("text_reconstruction", "stroke_data", "image_description")

# 学段适配表。SKILL.md 里有一份同内容的表格；此处常量供 hint 子命令回显，
# 两处不一致时以本常量为准。
GRADE_TABLE = (
    ("小学", "简单、具体、像口令", "折纸分区、每步落笔、画图", ("organization", "skipping")),
    ("初中", "清晰、鼓励、可操作", "先观察再选方法、草稿标号", ("skipping", "trial_and_error")),
    ("高中", "简洁、策略导向", "先画图再算、多路径标号", ("graphic_use", "trial_and_error")),
    ("大学", "平等、元认知导向", "探索路径标注、草稿即检查", ("draft_to_solution", "organization")),
)

# 六维检查要点（hint 回显用，不构成判断）
DIM_RUBRIC = (
    ("organization", "组织度", "是否分区、有序、可追溯；已知条件 / 推导 / 计算结果是否分开写"),
    ("skipping", "跳步模式", "哪些步骤没有落笔、哪些靠心算；跳的是哪一类（解方程 / 代数变形 / 代入计算 / 分类讨论）"),
    ("correction_pattern", "涂改模式", "涂改的频率、位置、类型；有没有留下修改理由；是不是想清楚再改"),
    ("trial_and_error", "试错痕迹", "有没有尝试第二条路、有没有标号区分、第一条路失败后有没有换方法"),
    ("graphic_use", "图形使用", "有没有画图、图形是否标注完整、画图时机是否在动笔计算之前"),
    ("draft_to_solution", "草稿利用率", "草稿算出的结果有多少进入最终解答；草稿是思考工具还是废纸"),
)

# 草稿里的启发式信号（只作提示）
SIGNAL_CUES = (
    ("correction_pattern", "出现涂改 / 划掉 / 重写痕迹",
     ("划掉", "涂改", "重写", "划去", "打叉", "涂掉", "改了", "改掉")),
    ("graphic_use", "出现图形 / 草图痕迹",
     ("画图", "草图", "图象", "图像", "数轴", "坐标", "辅助线", "树状图", "韦恩图", "示意图")),
    ("skipping", "疑似心算 / 跳步",
     ("心算", "口算", "直接得", "显然", "易得", "略")),
    ("trial_and_error", "疑似多路径尝试",
     ("另一", "方法二", "换一种", "换元", "另解", "再试", "改用")),
    ("organization", "疑似分区书写",
     ("左上", "右上", "左下", "右下", "左边", "右边", "上面", "下面", "第一块", "分区", "一格", "分块")),
)

PUNCT_RE = re.compile(r"[\s　，。？！、；：,.?!;:'\"“”‘’（）()【】\[\]]+")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
IDENT_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,7}")
STOP_TOKENS = frozenset({"已知", "求其", "下列", "的是", "一个", "以及", "其中", "如何", "什么"})

# 越界措辞：命中即说明卡片跑到了别的 skill 的疆域。
# 每条是 (代码, 说明, 正则)。正则一律要求"断言"语境（第二人称 / 这一步 / 答案），
# 不单禁"错"字，免得误伤"如果…就会漏根"这类假设性风险。
OUT_OF_SCOPE = (
    ("D_JUDGE", "判对错 / 给出正确结果",
     re.compile(
         r"你.{0,6}?(?:算|做|写|答|解|求).{0,3}?(?:错|不对|有问题)"
         r"|(?:这一步|该步|此处|这里|那一步|第[一二三四五六七八九十\d]+步|整个过程"
         r"|你的答案|你的结果|你的解法|你的思路)"
         r".{0,4}?(?:是?错了?|不正确|不对|有误|出错了?|有问题)"
         r"|正确答案|标准答案|参考答案|正确(?:的)?(?:结果|答案)"
         r"|应(?:该|当)(?:是|为|等于|改成|改写|写成)"
         r"|判(?:对错|分|卷)|对错|评分|打分|扣分|得分|满分|零分")),
    ("D_CAUSE", "诊断知识漏洞 / 判错因",
     re.compile(
         r"你(?:不|没)(?:懂|会|理解|掌握|明白|熟悉|记住)"
         r"|基础(?:差|薄弱|不牢|不扎实)|知识(?:点)?(?:漏洞|薄弱|欠缺|缺失)"
         r"|概念(?:不清|不牢|模糊|混淆)|错因|错误的原因|根本原因|出错的原因"
         r"|之所以.{0,12}?(?:错|失误)")),
    ("D_LABEL", "给学生贴标签",
     re.compile(
         r"你(?:很|太|比较|有(?:些|点)|就是)?(?:粗心|马虎|笨|懒|糟糕)"
         r"|你(?:的)?(?:思维|思路).{0,3}?(?:混乱|不清|很乱)"
         r"|你(?:不|没).{0,3}?(?:认真|仔细|用心|专心)"
         r"|态度不端正|粗心大意")),
    ("D_PLAN", "排题量 / 复习计划",
     re.compile(
         r"复习计划|学习计划|复习安排|错题本|计划表|打卡"
         r"|每天|每日|每周|一周|一个月|坚持\s*\d+\s*天"
         r"|连续做\s*\d+|做\s*\d+\s*道|刷\s*\d+\s*道|练\s*\d+\s*道")),
    ("D_VARIANT", "出变式题 / 出练习题",
     re.compile(
         r"变式|举一反三|再出.{0,3}?题"
         r"|(?:给你|再做|另出|附加).{0,4}?(?:一|几|\d+)\s*道"
         r"|出\s*\d*\s*道|练习(?:题|册)|习题|题库")),
    ("D_SOLUTION", "给出完整解答",
     re.compile(
         r"完整(?:解答|解法|过程|步骤|证明)"
         r"|正确(?:的)?(?:解法|解答|过程|步骤|写法)"
         r"|(?:应该|可以|建议)(?:这样|按这样)(?:写|做|算|解|画)")),
)

# 训练动作里的空话。出现这些说明这条"建议"下一道题没法执行。
VAGUE_ACTION_RE = re.compile(
    r"多练|多做题|多加练习|加油|要注意|要认真|认真一点|仔细一点|下次小心|不要马虎")

# 风险字段必须是假设句：出现后果词却没有任何限定词，就等于在断言已经出错了。
RISK_CONSEQUENCE_RE = re.compile(r"错|漏|误|偏差|丢")
RISK_HEDGE_RE = re.compile(r"可能|会|容易|易|若|如果|一旦|也许|或")

META_VOCAB_RE = re.compile(r"元认知|策略导向|路径标注|方法比较")

# 草稿里"有涂改痕迹"的信号，用来判断该不该肯定积极信号
DRAFT_CORRECTION_RE = re.compile(r"划掉|划去|涂改|涂抹|重写|改了|改掉|打叉|更正")

# refuse 的三种情形：学生会话里唯一允许的"不分析"出口。
# 退出码取值理由：2 = 草稿本身不能当证据（没给 / 给了但用不了）；
# 1 = 草稿没问题，但这个问题不归本技能管（有效请求，不予受理）。
REFUSALS = {
    "empty": ("无草稿",
              "没有检测到草稿内容。如果你是在脑子里算的，建议下次把关键步骤写下来，"
              "这样才能分析思考过程。", 2),
    "unreadable": ("草稿无法识别",
                   "草稿内容太乱或图片不清晰，无法分析。建议重新拍一张更清晰的草稿，"
                   "或把草稿内容用文字描述出来。", 2),
    "out_of_scope": ("超出范围",
                     "我只分析草稿习惯，不判断对错。如果你想知道答案对不对，"
                     "请把解答交给诊断工具。", 1),
}


# ---------------------------------------------------------------- 工具

def emit(payload, code):
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(code)


def norm(text):
    """归一化：去掉空白与标点、转小写。用于重复检测与关联度判断。"""
    return PUNCT_RE.sub("", str(text)).lower()


def load_card(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            card = json.load(fh)
    except FileNotFoundError:
        emit({"error": "card file not found", "path": path}, 2)
    except json.JSONDecodeError as exc:
        emit({"error": "card file is not valid JSON", "path": path, "detail": str(exc)}, 2)
    except UnicodeError as exc:
        emit({"error": "card file is not valid UTF-8", "path": path, "detail": str(exc)}, 2)
    except OSError as exc:
        emit({"error": "cannot read card file", "path": path, "detail": str(exc)}, 2)
    if not isinstance(card, dict):
        emit({"error": "card must be a JSON object", "path": path,
              "got": type(card).__name__}, 2)
    return card


def card_texts(card):
    """把卡片里所有文字摊平成 [(字段名, 文本)]，便于逐条扫描。"""
    out = []

    dimensions = card.get(DIMENSIONS_FIELD)
    if isinstance(dimensions, dict):
        for key, dim in dimensions.items():
            if not isinstance(dim, dict):
                continue
            for field in DIM_FIELDS:
                value = dim.get(field)
                if isinstance(value, str):
                    out.append(("%s.%s.%s" % (DIMENSIONS_FIELD, key, field), value))
            value = dim.get("positive")
            if isinstance(value, str):
                out.append(("%s.%s.positive" % (DIMENSIONS_FIELD, key), value))

    habits = card.get(HABIT_FIELD)
    if isinstance(habits, list):
        for index, habit in enumerate(habits, start=1):
            if not isinstance(habit, dict):
                continue
            for field in HABIT_FIELDS:
                value = habit.get(field)
                if isinstance(value, str):
                    out.append(("%s[%d].%s" % (HABIT_FIELD, index, field), value))

    value = card.get("next_step")
    if isinstance(value, str):
        out.append(("next_step", value))
    return out


def draft_tokens(text):
    """草稿里的"地标记号"：数字与 ASCII 标识符（f、x、a_n 之类）。

    与 solution-refiner 的 text_tokens 不同：这里**保留个位数字**，因为草稿天生
    挤满单字符记号（x=±1、n≥2）。为避免"2"命中"25"，匹配时改用数字边界
    （见 token_hit），所以保留个位数是安全的。
    """
    tokens = NUM_RE.findall(text) + IDENT_RE.findall(text)
    seen, out = set(), []
    for token in tokens:
        if token in STOP_TOKENS or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def token_hit(haystack_norm, token):
    """归一化文本里是否出现该记号；纯数字按数字边界匹配，避免子串误命中。"""
    if token[0].isdigit():
        return re.search(r"(?<!\d)" + re.escape(token) + r"(?!\d)", haystack_norm) is not None
    return token in haystack_norm


# ---------------------------------------------------------------- validate

def cmd_validate(args):
    card = load_card(args.card)
    errors, warnings = [], []

    for field in REQUIRED_FIELDS:
        if field not in card:
            errors.append({"code": "E_MISSING_FIELD", "field": field,
                           "detail": "缺少必需字段"})
    for field in card:
        if field not in REQUIRED_FIELDS:
            errors.append({"code": "E_EXTRA_FIELD", "field": field,
                           "detail": "分析卡只能包含五个标准字段；交接状态、诊断结论请放在卡片之外"})

    # -- 六个维度
    dimensions = card.get(DIMENSIONS_FIELD)
    if DIMENSIONS_FIELD in card:
        if not isinstance(dimensions, dict):
            errors.append({"code": "E_BAD_DIMENSIONS", "field": DIMENSIONS_FIELD,
                           "detail": "必须是对象，键为六个固定维度名"})
            dimensions = None
        else:
            for key in DIM_KEYS:
                if key not in dimensions:
                    errors.append({"code": "E_MISSING_DIMENSION", "field": key,
                                   "detail": "缺少维度「%s」" % DIM_LABEL[key]})
            for key in dimensions:
                if key not in DIM_KEYS:
                    errors.append({"code": "E_EXTRA_DIMENSION", "field": key,
                                   "detail": "非标准维度名；六个维度键名固定，不新增不细分",
                                   "allowed": list(DIM_KEYS)})

    if isinstance(dimensions, dict):
        for key in DIM_KEYS:
            if key not in dimensions:
                continue
            dim = dimensions[key]
            tag = "%s.%s" % (DIMENSIONS_FIELD, key)
            if not isinstance(dim, dict):
                errors.append({"code": "E_BAD_DIMENSION", "field": tag,
                               "detail": "每个维度必须是 JSON 对象"})
                continue

            for field in DIM_FIELDS:
                if field not in dim:
                    errors.append({"code": "E_MISSING_FIELD",
                                   "field": "%s.%s" % (tag, field),
                                   "detail": "缺少必需字段"})
                elif not isinstance(dim[field], str) or not dim[field].strip():
                    errors.append({"code": "E_EMPTY_TEXT",
                                   "field": "%s.%s" % (tag, field),
                                   "detail": "必须是非空字符串"})

            allowed_scores = SCORES_LAST if key == "draft_to_solution" else SCORES
            score = dim.get("score")
            if isinstance(score, str) and score.strip():
                if score.strip() not in allowed_scores:
                    errors.append({"code": "E_BAD_SCORE", "field": "%s.score" % tag,
                                   "text": score,
                                   "detail": "评分取值非法",
                                   "allowed": list(allowed_scores),
                                   "note": None if key == "draft_to_solution"
                                           else "只有「草稿利用率」在缺少最终解答时可用「不适用」"})
            if "positive" in dim:
                if key != POSITIVE_DIM:
                    errors.append({"code": "E_EXTRA_FIELD", "field": "%s.positive" % tag,
                                   "detail": "只有「涂改模式」可以写 positive；"
                                             "其他维度的积极信号写进 observation"})
                elif not isinstance(dim["positive"], str) or not dim["positive"].strip():
                    errors.append({"code": "E_EMPTY_TEXT", "field": "%s.positive" % tag,
                                   "detail": "必须是非空字符串"})
            for field in dim:
                if field not in DIM_FIELDS and field != "positive":
                    errors.append({"code": "E_EXTRA_FIELD", "field": "%s.%s" % (tag, field),
                                   "detail": "非标准字段，建议删除"})

            evidence = dim.get("evidence")
            if isinstance(evidence, str) and evidence.strip() and len(norm(evidence)) < 6:
                warnings.append({"code": "W_EVIDENCE_SHORT", "field": "%s.evidence" % tag,
                                 "text": evidence,
                                 "detail": "证据过短，看不出草稿里的具体位置或记号"})

    # -- 学段与来源
    grade = card.get("grade_level")
    if isinstance(grade, str) and grade.strip() and grade.strip() not in GRADES:
        errors.append({"code": "E_BAD_GRADE", "field": "grade_level", "text": grade,
                       "detail": "学段必须是小学 / 初中 / 高中 / 大学之一",
                       "allowed": list(GRADES)})
    source = card.get("draft_source")
    if isinstance(source, str) and source.strip() and source.strip() not in SOURCES:
        errors.append({"code": "E_BAD_SOURCE", "field": "draft_source", "text": source,
                       "detail": "草稿来源取值非法", "allowed": list(SOURCES)})

    # -- next_step
    next_step = card.get("next_step")
    if "next_step" in card and (not isinstance(next_step, str) or not next_step.strip()):
        errors.append({"code": "E_EMPTY_TEXT", "field": "next_step",
                       "detail": "必须是非空字符串"})
    if isinstance(next_step, str) and next_step.strip():
        if len(norm(next_step)) < 6 or VAGUE_ACTION_RE.search(next_step):
            warnings.append({"code": "W_NON_ACTIONABLE", "field": "next_step",
                             "text": next_step,
                             "detail": "看不出下一道题具体做什么；写成能立刻执行的动作"})

    # -- 三条习惯
    habits = card.get(HABIT_FIELD)
    if HABIT_FIELD in card:
        if not isinstance(habits, list):
            errors.append({"code": "E_BAD_HABITS", "field": HABIT_FIELD,
                           "detail": "必须是数组，数组里每条是一个习惯"})
            habits = None
        elif len(habits) != HABIT_COUNT:
            errors.append({"code": "E_HABIT_COUNT", "count": len(habits),
                           "detail": "习惯必须恰好 %d 条，实为 %d 条" % (HABIT_COUNT, len(habits))})

    if isinstance(habits, list):
        seen = {}
        for index, habit in enumerate(habits, start=1):
            tag = "%s[%d]" % (HABIT_FIELD, index)
            if not isinstance(habit, dict):
                errors.append({"code": "E_BAD_HABIT", "field": tag,
                               "detail": "每条习惯必须是 JSON 对象"})
                continue
            for field in HABIT_FIELDS:
                if field not in habit:
                    errors.append({"code": "E_MISSING_FIELD", "field": "%s.%s" % (tag, field),
                                   "detail": "缺少必需字段"})
                elif not isinstance(habit[field], str) or not habit[field].strip():
                    errors.append({"code": "E_EMPTY_TEXT", "field": "%s.%s" % (tag, field),
                                   "detail": "必须是非空字符串"})
            for field in habit:
                if field not in HABIT_FIELDS:
                    errors.append({"code": "E_EXTRA_FIELD", "field": "%s.%s" % (tag, field),
                                   "detail": "非标准字段，建议删除"})

            key = norm(habit.get("habit", ""))
            if key:
                if key in seen:
                    errors.append({"code": "E_DUPLICATE_HABIT", "field": "%s.habit" % tag,
                                   "text": habit.get("habit"),
                                   "detail": "与第 %d 条习惯重复；三条习惯要说三件事" % seen[key]})
                else:
                    seen[key] = index

            training = habit.get("training")
            if isinstance(training, str) and training.strip():
                if len(norm(training)) < 6 or VAGUE_ACTION_RE.search(training):
                    warnings.append({"code": "W_NON_ACTIONABLE",
                                     "field": "%s.training" % tag, "text": training,
                                     "detail": "看不出下一道题具体做什么；"
                                               "写成能立刻执行的动作，不是周期计划"})

    # -- 整卡层面的警告
    if isinstance(dimensions, dict):
        scores = [dimensions[k].get("score") for k in DIM_KEYS
                  if isinstance(dimensions.get(k), dict)]
        if len(scores) == len(DIM_KEYS) and len(set(scores)) == 1:
            warnings.append({"code": "W_SCORE_UNIFORM", "field": DIMENSIONS_FIELD,
                             "detail": "六个维度评分完全相同（%s）；"
                                       "先确认这不是没有逐维看草稿" % scores[0]})

    passed = not errors
    emit({
        "action": "validate",
        "input": {"card": args.card},
        "method": "字段完整性 + 恰好六个维度 + 评分取值 + 恰好三条习惯 + 学段与来源合法性",
        "errors": errors,
        "warnings": warnings,
        "passed": passed,
        "capability_note": "结构门只查卡片长得对不对，不判断习惯观察是否成立；"
                           "证据与草稿是否对得上由 audit 的 W_DETACHED_DRAFT 提醒。",
    }, 0 if passed else 1)


# ---------------------------------------------------------------- audit

def cmd_audit(args):
    card = load_card(args.card)
    draft = (args.draft or "").strip()
    if not draft:
        emit({"error": "--draft must be a non-empty string",
              "hint": "没有草稿就不要分析；用 refuse --reason empty 给出标准回复"}, 2)
    final_solution = (args.final_solution or "").strip()

    errors, warnings = [], []
    texts = card_texts(card)

    # A 组：越界措辞——跑到了别的 skill 的疆域
    for field, text in texts:
        for code, label, pattern in OUT_OF_SCOPE:
            match = pattern.search(text)
            if match:
                errors.append({"code": code, "field": field, "text": text,
                               "matched": match.group(0),
                               "detail": "越过本 skill 边界：%s" % label})

    # W 组：卡片与草稿 / 最终解答是否脱节
    joined = " ".join(norm(text) for _, text in texts)
    tokens = draft_tokens(draft)
    if len(tokens) >= 3:
        if not any(token_hit(joined, token) for token in tokens):
            warnings.append({"code": "W_DETACHED_DRAFT", "field": "*",
                             "draft_tokens": tokens[:12],
                             "detail": "卡片没有引用草稿里的任何数字或记号，"
                                       "可能不是从这份草稿看出来的"})
    if final_solution:
        solution_tokens = draft_tokens(final_solution)
        if len(solution_tokens) >= 3:
            if not any(token_hit(joined, token) for token in solution_tokens):
                warnings.append({"code": "W_DETACHED_SOLUTION", "field": "*",
                                 "solution_tokens": solution_tokens[:12],
                                 "detail": "卡片没有引用最终解答里的任何数字或记号，"
                                           "可能脱离实际解答"})

    dimensions = card.get(DIMENSIONS_FIELD)
    if isinstance(dimensions, dict):
        correction = dimensions.get(POSITIVE_DIM)
        if isinstance(correction, dict):
            # 草稿里有涂改却没写积极信号：不是错误，但值得人工看一眼
            if correction.get("score") != "高" and not str(correction.get("positive", "")).strip() \
                    and DRAFT_CORRECTION_RE.search(draft):
                warnings.append({"code": "W_POSITIVE_ABSENT",
                                 "field": "%s.%s.positive" % (DIMENSIONS_FIELD, POSITIVE_DIM),
                                 "detail": "草稿里有涂改痕迹，但没有指出积极信号；"
                                           "涂改后能自我纠正、改处有标注都应肯定"})
            # 给了最终解答却把"草稿利用率"标成不适用
            utilization = dimensions.get("draft_to_solution")
            if isinstance(utilization, dict) and utilization.get("score") == UNAVAILABLE \
                    and final_solution:
                warnings.append({"code": "W_UTILIZATION_UNAVAILABLE",
                                 "field": "%s.draft_to_solution.score" % DIMENSIONS_FIELD,
                                 "detail": "已提供最终解答，草稿利用率应当可以评分"})

    # risk 是假设句：说了后果就得带限定词
    if isinstance(dimensions, dict):
        for key in DIM_KEYS:
            dim = dimensions.get(key)
            if not isinstance(dim, dict):
                continue
            risk = dim.get("risk")
            if isinstance(risk, str) and RISK_CONSEQUENCE_RE.search(risk) \
                    and not RISK_HEDGE_RE.search(risk):
                warnings.append({"code": "W_RISK_UNHEDGED",
                                 "field": "%s.%s.risk" % (DIMENSIONS_FIELD, key),
                                 "text": risk,
                                 "detail": "风险句没有限定词，读起来像在断言已经出错了；"
                                           "改成「若…可能…」的假设句"})

    # 学段适配：小学 / 初中不该出现元认知词汇
    grade = card.get("grade_level")
    if grade in ("小学", "初中"):
        for field, text in texts:
            match = META_VOCAB_RE.search(text)
            if match:
                warnings.append({"code": "W_GRADE_MISMATCH", "field": field, "text": text,
                                 "matched": match.group(0),
                                 "detail": "学段是%s，却使用了元认知 / 策略导向的措辞" % grade})

    passed = not errors and not (args.strict and warnings)
    emit({
        "action": "audit",
        "input": {"card": args.card, "draft": draft,
                  "final_solution": final_solution or None, "strict": args.strict},
        "method": "规则扫描：判对错 / 诊断知识漏洞 / 贴标签 / 排题量计划 / 出变式题 / 给完整解答，"
                  "外加与草稿及最终解答的关联度、风险句限定词、学段用词一致性",
        "errors": errors,
        "warnings": warnings,
        "passed": passed,
        "capability_note": "规则门而非语义理解：passed 只说明卡片没越过这几条线，"
                           "不说明这条习惯观察在数学上站得住，也不说明建议真的可执行。"
                           "跳步 / 涂改 / 划掉 / 漏根等本技能核心词汇不在禁列，"
                           "假设性风险句（「若…可能漏根」）是合法的。",
    }, 0 if passed else 1)


# ---------------------------------------------------------------- hint

def cmd_hint(args):
    draft = (args.draft or "").strip()
    if not draft:
        emit({"error": "--draft must be a non-empty string"}, 2)
    grade = (args.grade_level or DEFAULT_GRADE).strip()
    if grade not in GRADES:
        emit({"error": "--grade-level must be one of %s" % " / ".join(GRADES)}, 2)

    blob = draft.lower()
    detected = []
    for key, label, keywords in SIGNAL_CUES:
        hits = [kw for kw in keywords if kw.lower() in blob]
        if hits:
            detected.append({"dimension": key, "dimension_label": DIM_LABEL[key],
                             "signal": label, "matched_keywords": hits})

    emit({
        "action": "hint",
        "input": {"draft": draft, "grade_level": grade},
        "method": "六维检查要点回显 + 学段适配表 + 草稿关键词启发式提示"
                  "（未命中不代表该维度没问题，只代表关键词表没覆盖）",
        "dimensions": [{"key": key, "label": label, "focus": focus}
                       for key, label, focus in DIM_RUBRIC],
        "grade_menu": [{"grade": g, "style": style, "training": training,
                        "focus_dimensions": [DIM_LABEL[k] for k in keys]}
                       for g, style, training, keys in GRADE_TABLE],
        "selected_grade": grade,
        "detected_signals": detected,
        "authority": "heuristic-hint-only",
        "capability_note": "关键词命中只是提示，可能误判；必须以读完草稿后的判断为准，"
                           "不得用本输出替代对草稿的理解，也不得凭关键词就下习惯结论。"
                           "六个维度都要给评分，不能因为没命中关键词就跳过。",
    }, 0)


# ---------------------------------------------------------------- refuse

def cmd_refuse(args):
    error, message, code = REFUSALS[args.reason]
    emit({
        "action": "refuse",
        "error": error,
        "message": message,
        "reason": args.reason,
        "exit_code_meaning": {
            "empty": "没有草稿：必需输入缺失",
            "unreadable": "草稿无法识别：输入存在但用不了",
            "out_of_scope": "超出范围：草稿有效，但这个问题不归本技能管",
        }[args.reason],
    }, code)


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(
        description="Validate and audit a student draft-habit analysis card.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="structural gate for a draft analysis card")
    p_validate.add_argument("--card", required=True, help="path to the card JSON file")
    p_validate.set_defaults(func=cmd_validate)

    p_audit = sub.add_parser("audit", help="scan a card for out-of-scope moves and detachment")
    p_audit.add_argument("--card", required=True, help="path to the card JSON file")
    p_audit.add_argument("--draft", required=True, help="the student's draft content")
    p_audit.add_argument("--final-solution", default=None,
                         help="optional: the student's final solution")
    p_audit.add_argument("--strict", action="store_true", help="treat warnings as failures")
    p_audit.set_defaults(func=cmd_audit)

    p_hint = sub.add_parser("hint", help="echo the six-dimension rubric and grade table")
    p_hint.add_argument("--draft", required=True, help="the student's draft content")
    p_hint.add_argument("--grade-level", default=DEFAULT_GRADE,
                        help="小学 / 初中 / 高中 / 大学（默认高中）")
    p_hint.set_defaults(func=cmd_hint)

    p_refuse = sub.add_parser("refuse", help="emit the standard refusal payload")
    p_refuse.add_argument("--reason", required=True, choices=sorted(REFUSALS),
                          help="empty = 无草稿；unreadable = 草稿无法识别；"
                               "out_of_scope = 学生只想知道对错")
    p_refuse.set_defaults(func=cmd_refuse)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
