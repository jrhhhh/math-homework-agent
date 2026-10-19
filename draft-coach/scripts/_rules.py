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

定位（2026-10-17 起）：**只看草稿的版面习惯，不判断计算对错，也不做手写转写。**
分析单位是一道题的草稿；整个技能围绕“分区、分行、划改、多路径、图形、留白”六个
版面可观察的习惯，不产生任何错误指控。

能力边界（诚实声明，别把它当正确性证明）：
  - 结构门只查"卡片长得对不对"：六个维度是否齐全、评分是否在取值集合内、
    习惯是否 1–3 条、学段与草稿来源是否合法。**它不判断任何数学内容。**
  - 越界审计靠措辞规则，抓的是"诊断知识漏洞 / 给学生贴标签 / 排题量计划 /
    出变式题 / 给完整解答 / 评分扣分"。它是便宜的确定性门，不是语义理解；
    换个说法绕过去，它抓不住。
  - **本技能不判断草稿上的计算对错。** 版面观察也不是数学结论；要查对错请走
    `math-error-diagnosis`；已成立解法的优化当前项目暂不提供。
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

SCOPE_FIELD = "scope"
DIMENSIONS_FIELD = "dimensions"
HABIT_FIELD = "top_3_habits"
# 纯习惯卡：没有错误清单，也没有交接/诊断字段。
REQUIRED_FIELDS = (SCOPE_FIELD, DIMENSIONS_FIELD, HABIT_FIELD,
                   "next_step", "grade_level", "draft_source")

# 六个**版面习惯**维度，键名保留兼容，含义已改为只看版面。
DIM_KEYS = ("organization", "skipping", "correction_pattern",
            "trial_and_error", "graphic_use", "draft_to_solution")
DIM_LABEL = {
    "organization": "分区与边距",
    "skipping": "步骤分行与密度",
    "correction_pattern": "划改与自纠",
    "trial_and_error": "多路径标记",
    "graphic_use": "图形与标注",
    "draft_to_solution": "留白与检验区",
}
DIM_FIELDS = ("score", "observation", "evidence", "risk")
POSITIVE_DIM = "correction_pattern"   # 只有划改维度允许 positive 字段

SCORES = ("高", "中", "低")
# 版面本身看不出时宁可标"不适用"，也不虚构一个分数。
UNAVAILABLE = "不适用"
SCORES_ANY = SCORES + (UNAVAILABLE,)
SCORES_LAST = SCORES_ANY   # 兼容旧导入

# score=不适用 时，observation 里应出现的原因词（只用来提醒，不做硬门）。
UNAVAILABLE_REASON_RE = re.compile(
    r"无法|看不出|不足|未提供|缺失|不可判|未核对|草稿太短|短草稿|不适用|"
    r"没有提供|不清晰|拍不到")

HABIT_FIELDS = ("habit", "impact", "training")
HABIT_COUNT = 3          # 目标条数
HABIT_MIN = 1            # 至少给一条可执行动作
HABIT_MAX = 3

GRADES = ("小学", "初中", "高中", "大学")
DEFAULT_GRADE = "高中"
SOURCES = ("text_reconstruction", "image_description")

# 学段适配表。SKILL.md 的「学段适配指南」同内容；此处常量供 hint 子命令回显，
# 两处不一致时以本常量为准。
GRADE_TABLE = (
    ("小学", "简单、具体、像口令", "折纸分区、每步落笔、画图", ("organization", "skipping")),
    ("初中", "清晰、鼓励、可操作", "草稿标号、改错留因", ("skipping", "correction_pattern")),
    ("高中", "简洁、策略导向", "先画图再算、多路径标号", ("graphic_use", "trial_and_error")),
    ("大学", "平等、元认知导向", "探索路径标注、草稿即检查", ("draft_to_solution", "organization")),
)

# 六维检查要点（hint 回显用，不构成判断）
DIM_RUBRIC = (
    ("organization", "分区与边距",
     "有没有题号/分块、已知/求/推导是否分开；条件与推导是否混写；多题是否混写。"
     "不要求横平竖直"),
    ("skipping", "步骤分行与密度",
     "高风险步骤（移项变号、去括号、开方、分类边界、代入）是否单独落行；"
     "不要求每步都写，低风险步骤可以心算"),
    ("correction_pattern", "划改与自纠",
     "划改后旧值是否明确作废、新值是否可辨；不要求重抄整页"),
    ("trial_and_error", "多路径标记",
     "分类讨论/多解/多方法有没有 ①②、箭头或分支标记；不要求整齐"),
    ("graphic_use", "图形与标注",
     "几何图有没有标顶点/辅助线/关键点；函数图有没有坐标轴/极值点；"
     "不要求画得漂亮"),
    ("draft_to_solution", "留白与检验区",
     "有没有留出检验区，答句/单位/范围有没有固定落点；结果有没有写在纸边/题缝。"
     "不要求专门划区"),
)

# 草稿里的启发式信号（只作提示）
SIGNAL_CUES = (
    ("correction_pattern", "出现划改 / 重写痕迹",
     ("划掉", "涂改", "重写", "划去", "打叉", "涂掉", "改了", "改掉")),
    ("graphic_use", "出现图形 / 草图痕迹",
     ("画图", "草图", "图象", "图像", "数轴", "坐标", "辅助线", "顶点",
      "树状图", "韦恩图", "示意图", "极值点")),
    ("skipping", "疑似高风险步骤挤在一起",
     ("一行", "连写", "挤在", "没分行", "未分行", "写在了一起", "连着写",
      "移项", "开方", "去括号", "代入", "分类边界")),
    ("trial_and_error", "疑似多路径 / 分类讨论标记",
     ("标号", "方法一", "方法二", "另一", "箭头", "圈出", "另起", "换了",
      "分类讨论", "①", "②", "第一种", "第二种")),
    ("organization", "疑似分区 / 题号书写",
     ("左上", "右上", "左下", "右下", "左边", "右边", "上面", "下面",
      "第一块", "分区", "一格", "分块", "边距", "题号", "已知", "求", "条件")),
    ("draft_to_solution", "疑似留白 / 检验区",
     ("留白", "空白", "检验区", "写满", "空着", "右下角留", "代回", "答句",
      "单位", "范围", "纸边", "题缝", "背面")),
)

PUNCT_RE = re.compile(r"[\s　，。？！、；：,.?!;:'\"“”‘’（）()【】\[\]]+")

# 越界措辞：命中即说明卡片跑到了别的 skill 的疆域。
# 本技能不判对错；边界是"别越到能力评价、别的技能和评分的地盘上去"。
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

# 越界扫描的否定豁免。紧接在命中措辞**之前**的否定词，把该命中豁免掉。
# 学生问"帮我按百分制打个分"，答案答"这一项我没有打分"是在**拒绝**越界，
# 不是越界；A_SCORE 的正则只看字面，必然误报。这与 REFUSALS 的豁免同类：
# 规则门认不出语义，所以要把"如实声明自己没做某件事"这一小类显式豁免。
NEGATION_BEFORE_RE = re.compile(
    r"(?:没有|没|不|未|无需|不需要|不必要|不用|谈不上)\s*$")

# ---------------------------------------------------------------- 题目分区（partition）
# 只做版面分块：看留白、分隔线、区域大小、书写方向，**不读字符**。
# 块数不等于题目数；输出必须给范围、写不确定处，并请学生确认。
PARTITION_ACTION = "partition"
PARTITION_SOURCES = ("image_layout", "student_text")
PARTITION_BLOCK_FIELDS = ("block_id", "location", "visual_cues", "separate_problem",
                          "confidence", "note")
PARTITION_REQUIRED_FIELDS = (
    "action", "block_source", "blocks", "estimated_problem_count", "count_range",
    "uncertainty", "confirmation_question", "limitations",
)
PARTITION_MIN_BLOCKS = 1
PARTITION_MAX_BLOCKS = 12
PARTITION_SCORES = ("高", "中", "低")
# 分区只能给"大致"，不能把版面块说成已确认的题目边界。
PARTITION_ASSERTIVE_RE = re.compile(
    r"就是\s*\d+\s*道|一定是|已经分好|确实是|毫无疑问|肯定只有|绝对|完全确定")
# 分区出口不做错因诊断，也不许报错误。
PARTITION_ERROR_CLAIM_RE = re.compile(
    r"算错|错在|写错|这一步错了|错误是|漏了(?:根|一步|条件|符号|项|解)")
# 分区出口不读字符；"我看出这行写的是…"属于越界。
PARTITION_OCR_CLAIM_RE = re.compile(
    r"我(?:读|看)出.{0,12}(?:字|式子|内容|数字|写的是)|"
    r"识别出.{0,8}(?:文字|式子|数字)|转写|OCR")
PARTITION_LIMITATION_CUES = ("版面", "不读", "字符", "确认", "大致", "块数",
                             "不等于", "题目数", "留白", "分隔")
PARTITION_CONFIRM_CUES = ("确认", "像不像", "是不是", "哪", "对吗", "请你看",
                          "你核对", "对不对")

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
              "这样才能看草稿的版面习惯。", 2),
    "unreadable": ("草稿无法识别",
                   "草稿内容太乱或图片不清晰，无法分析。建议重新拍一张更清晰的草稿，"
                   "或把草稿内容用文字描述出来。", 2),
    "out_of_scope": ("超出范围",
                     "我只看草稿的版面习惯，不判断计算对错。"
                     "要检查解答、优化已经做对的解法，或者要变式题、复习计划，"
                     "请交给对应的技能。", 1),
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

    value = card.get(SCOPE_FIELD)
    if isinstance(value, str):
        out.append((SCOPE_FIELD, value))

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


def out_of_scope_matches(text):
    """扫描越界措辞，返回 [(code, label, matched, start, end)]。

    被否定的命中会被跳过（见 NEGATION_BEFORE_RE）。豁免只看命中措辞**紧前面**那个词：
    「这一项我没有打分」跳过，「这道题会扣分」「建议连续做 10 道题」照旧命中。
    换个说法照样绕得过去——本门从来不是语义理解，别把它当保证。
    """
    hits = []
    for code, label, pattern in OUT_OF_SCOPE:
        for match in pattern.finditer(str(text or "")):
            if NEGATION_BEFORE_RE.search(str(text or "")[:match.start()]):
                continue
            hits.append((code, label, match.group(0), match.start(), match.end()))
    return hits


def out_of_scope_codes(text):
    """只取命中的代码，去重排序。评测器与门脚本共用同一口径的入口。"""
    return sorted({code for code, _label, _matched, _start, _end in out_of_scope_matches(text)})
