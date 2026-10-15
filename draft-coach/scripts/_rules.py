#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_rules.py — draft-coach 两道门共用的常量与工具。

被 `validate_output.py`（结构门）与 `audit_output.py`（越界与证据审计）共同导入，
也是评测器取常量的唯一来源（`draft-coach/evals/engine/metrics.py` 按路径加载本文件）。

**常量只在这里存一份。** 六维键名、越界正则、REFUSALS、题号标记这些若有第二份
拷贝，改一处忘另一处必然不一致——SKILL.md 里那句「两处不一致时以脚本常量为准」
就是因为这个才存在的。

约定：
  - 所有结果以 JSON 打到 stdout；
  - 退出码：0 = 通过 / 干净；1 = 未通过（有 error，或 --strict 下出现 warning）；
    2 = 输入非法。`refuse` 另有一套映射，见 REFUSALS。
  - 仅使用 Python 标准库，无第三方依赖。

定位（2026-10-11 起）：**首要是查计算错误，其次是讲草稿习惯。**
所以判对错、指出"这一步算错了"、给出该写成什么，**都是本职**，不再越界。

能力边界（诚实声明，别把它当正确性证明）：
  - 结构门只查"卡片长得对不对"：错误清单与六个维度是否齐全、评分是否在取值集合内、
    每条错误的四个字段是否填了、习惯是否恰好 3 条、学段与草稿来源是否合法。
    **它不判断你报的那处错误在数学上是否真的错**——那要人来算。
  - 越界审计靠措辞规则，抓的是"诊断知识漏洞 / 给学生贴标签 / 排题量计划 /
    出变式题 / 给完整解答 / 评分扣分"。它是便宜的确定性门，不是语义理解；
    换个说法绕过去，它抓不住。
  - **本门唯一能守住的错误相关约束是"错误指控必须有草稿证据"**（W_ERROR_NOT_IN_DRAFT）：
    每条错误的 evidence 必须引用草稿里的记号。它拦不住"引用了草稿却把对的判成错的"——
    那只能靠人复核。**没有人工复核的草稿检查卡不构成数学结论。**
  - 草稿关联度用记号重合判断；短草稿可能整段跳过这项检查。
"""

import json
import re
import sys

try:  # Windows 控制台默认编码可能是 GBK，统一成 UTF-8，免得中文与数学符号炸掉
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------- 常量

ERROR_FIELD = "error_check"
DIMENSIONS_FIELD = "dimensions"
HABIT_FIELD = "top_3_habits"
REQUIRED_FIELDS = (ERROR_FIELD, DIMENSIONS_FIELD, HABIT_FIELD,
                   "next_step", "grade_level", "draft_source")

# 错误清单：每条恰好四个字段。errors 允许为空数组（草稿没错就说没错）。
ERROR_ITEM_FIELDS = ("location", "evidence", "explanation", "fix")

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

# 学段适配表。SKILL.md 的「学段适配指南」同内容；此处常量供 hint 子命令回显，
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
# 注意：**判对错、指出某处算错了、给出该写成什么，都不在禁列**——那是本职。
# 剩下的边界是"别越到能力评价和别的技能的地盘上去"。
OUT_OF_SCOPE = (
    ("A_CAUSE", "诊断知识漏洞 / 给学生能力定级",
     re.compile(
         r"你(?:不|没)(?:懂|会|理解|掌握|明白|熟悉|记住)"
         r"|基础(?:差|薄弱|不牢|不扎实)|知识(?:点)?(?:漏洞|薄弱|欠缺|缺失)"
         r"|概念(?:不清|不牢|模糊|混淆)"
         r"|之所以.{0,12}?(?:错|失误)")),
    ("A_LABEL", "给学生贴标签",
     re.compile(
         r"你(?:很|太|比较|有(?:些|点)|就是)?(?:粗心|马虎|笨|懒|糟糕)"
         r"|你(?:的)?(?:思维|思路).{0,3}?(?:混乱|不清|很乱)"
         r"|你(?:不|没).{0,3}?(?:认真|仔细|用心|专心)"
         r"|态度不端正|粗心大意")),
    ("A_PLAN", "排题量 / 复习计划",
     re.compile(
         r"复习计划|学习计划|复习安排|错题本|计划表|打卡"
         r"|每天|每日|每周|一周|一个月|坚持\s*\d+\s*天"
         r"|连续做\s*\d+|做\s*\d+\s*道|刷\s*\d+\s*道|练\s*\d+\s*道")),
    ("A_VARIANT", "出变式题 / 出练习题",
     re.compile(
         r"变式|举一反三|再出.{0,3}?题"
         r"|(?:给你|再做|另出|附加).{0,4}?(?:一|几|\d+)\s*道"
         r"|出\s*\d*\s*道|练习(?:题|册)|习题|题库")),
    # 给"最小修改"是本职；整题重写、给完整解答不是。
    ("A_SOLUTION", "给完整解答 / 整题重写",
     re.compile(
         r"(?:给出|提供|附上|下面是|以下是|这就是|这是)"
         r"\s*(?:完整|正确)的?(?:解答|解法|过程|步骤|证明)"
         r"|(?:把|将)(?:整|全)(?:道|个)?题.{0,4}?(?:重写|重做|写一遍)"
         r"|完整(?:解答|解法|证明)\s*[:：]")),
    ("A_SCORE", "评分 / 扣分",
     re.compile(r"判(?:对错|分|卷)|评分|打分|扣分|得分|满分|零分")),
)

# 错误清单里禁止出现的"空话式修改"：说了等于没说
FIX_NON_ACTIONABLE_RE = re.compile(
    r"^\s*(?:注意|小心|认真|仔细|再算算|重算|检查一下)[。！!]*\s*$")

# 训练动作里的空话。出现这些说明这条"建议"下一道题没法执行。
VAGUE_ACTION_RE = re.compile(
    r"多练|多做题|多加练习|加油|要注意|要认真|认真一点|仔细一点|下次小心|不要马虎")

# 风险字段必须是假设句：出现后果词却没有任何限定词，就等于在断言已经出错了。
RISK_CONSEQUENCE_RE = re.compile(r"错|漏|误|偏差|丢")
RISK_HEDGE_RE = re.compile(r"可能|会|容易|易|若|如果|一旦|也许|或")

META_VOCAB_RE = re.compile(r"元认知|策略导向|路径标注|方法比较")

# 草稿里"有涂改痕迹"的信号，用来判断该不该肯定积极信号
DRAFT_CORRECTION_RE = re.compile(r"划掉|划去|涂改|涂抹|重写|改了|改掉|打叉|更正")

# 题号标记：用来发现"这其实是一整张草稿纸，不止一道题"。
# 刻意避开普通数字与 f(1) 这类函数记号，否则草稿里满地都是误报。
# 已知边界：带圈序号也被当作题号，因此用「方法①/方法②」标同一道题的两条路径时
# 会误报 W_MULTI_PROBLEM_DRAFT，`--strict` 下会把一张正确的卡片判为不过。
PROBLEM_MARKER_RE = re.compile(
    r"第\s*[一二三四五六七八九十\d]+\s*[题问]"      # 第一题 / 第 2 问
    r"|[①②③④⑤⑥⑦⑧⑨⑩]"                          # 带圈序号
    r"|（\s*\d+\s*）"                              # 全角括号小问号
    r"|(?:^|[；;。\n])\s*\d+\s*[、.．]"            # 段落起首的 1、 / 2.
)

# refuse 的三种情形：学生会话里唯一允许的"不分析"出口。
# 退出码取值理由：2 = 草稿本身不能当证据（没给 / 给了但用不了）；
# 1 = 草稿没问题，但这个问题不归本技能管（有效请求，不予受理）。
REFUSALS = {
    "empty": ("无草稿",
              "没有检测到草稿内容。如果你是在脑子里算的，建议下次把关键步骤写下来，"
              "这样才能检查计算过程、也才能分析习惯。", 2),
    "unreadable": ("草稿无法识别",
                   "草稿内容太乱或图片不清晰，无法分析。建议重新拍一张更清晰的草稿，"
                   "或把草稿内容用文字描述出来。", 2),
    "out_of_scope": ("超出范围",
                     "我检查草稿里的计算错误和过程习惯。要优化已经做对的解法，"
                     "或者要变式题、复习计划，请交给对应的技能。", 1),
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

    error_check = card.get(ERROR_FIELD)
    if isinstance(error_check, dict):
        value = error_check.get("scope")
        if isinstance(value, str):
            out.append(("%s.scope" % ERROR_FIELD, value))
        errors = error_check.get("errors")
        if isinstance(errors, list):
            for index, item in enumerate(errors, start=1):
                if not isinstance(item, dict):
                    continue
                for field in ERROR_ITEM_FIELDS:
                    value = item.get(field)
                    if isinstance(value, str):
                        out.append(("%s.errors[%d].%s" % (ERROR_FIELD, index, field), value))

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
