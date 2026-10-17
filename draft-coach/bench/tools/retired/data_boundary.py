# -*- coding: utf-8 -*-
"""D 子集：输入边界与拒绝出口（6 条）。"""

from _common import (
    SCOPE_LAYOUT, SCOPE_NO_PROBLEM, SCOPE_SHORT, analyze_gold, dim, ev, habit,
    make, refuse_gold,
)

D = dim
H = habit

CASES = []

EMPTY_MSG = [["草稿", "没有检测到"], ["写下来", "关键步骤", "打字", "描述"]]
UNREADABLE_MSG = [["无法识别", "不清晰", "太乱", "模糊"], ["重拍", "文字描述", "口述"]]
OUT_OF_SCOPE_MSG = [
    ["只看草稿", "版面习惯"],
    ["不判断", "不查", "对错"],
    ["对应的技能", "math-error-diagnosis", "solution-refiner", "交给"],
]


# ---------------------------------------------------------------- BND-01
CASES.append(make(
    "BND-01", "boundary", "development", "easy", "answer_only", "高中",
    "请使用 $draft-coach 看看我的草稿习惯。答案我算出来了，是 x=2。",
    "",
    expected_actions=("refuse",),
    refuse_reason="empty",
    acceptable_refusal_reasons=["empty"],
    branches={"refuse": refuse_gold("empty", EMPTY_MSG)},
    notes="只有最终答案，没有草稿：不能从答案倒推草稿。",
))


# ---------------------------------------------------------------- BND-02
CASES.append(make(
    "BND-02", "boundary", "development", "easy", "unreadable_photo", "高中",
    "草稿照片很模糊，只看到一团黑，你帮我看看习惯。",
    "",
    source="image_description",
    image_note="照片模糊，反光严重，只看到一团黑色笔迹，分不清行。",
    expected_actions=("refuse",),
    refuse_reason="unreadable",
    acceptable_refusal_reasons=["unreadable"],
    branches={"refuse": refuse_gold("unreadable", UNREADABLE_MSG)},
    notes="照片无法辨认时拒绝，不硬猜记号；让学生重拍或口述。",
))


# ---------------------------------------------------------------- BND-03
CASES.append(make(
    "BND-03", "boundary", "development", "medium", "formal_solution_wrong_route", "高中",
    "请使用 $draft-coach 检查我的作业，看看这道题算得对不对。",
    "作业本上的正式解答：设 f(x)=x^3-3x，f'(x)=3x^2-3，令 f'(x)=0 得 x=±1，"
    "f(1)=-2，f(-1)=2，所以极大值2，极小值-2。",
    expected_actions=("refuse",),
    refuse_reason="out_of_scope",
    acceptable_refusal_reasons=["out_of_scope"],
    branches={"refuse": refuse_gold("out_of_scope", OUT_OF_SCOPE_MSG)},
    notes="正式解答 + 查对错：应转 math-error-diagnosis，不能当草稿做版面分析。",
))


# ---------------------------------------------------------------- BND-04
CASES.append(make(
    "BND-04", "boundary", "development", "medium", "already_solved_optimize", "高中",
    "我的解法已经全对了，帮我优化一下步骤，让它更简洁。",
    "正式解答：设 f(x)=x^3-3x，f'(x)=3x^2-3，令 f'(x)=0 得 x=±1，"
    "f(1)=-2，f(-1)=2，所以极大值2，极小值-2。",
    expected_actions=("refuse",),
    refuse_reason="out_of_scope",
    acceptable_refusal_reasons=["out_of_scope"],
    branches={"refuse": refuse_gold("out_of_scope", OUT_OF_SCOPE_MSG)},
    notes="已成立解法 + 优化：应转 solution-refiner；也不属于草稿版面分析。",
))


# ---------------------------------------------------------------- BND-05
CASES.append(make(
    "BND-05", "boundary", "validation", "hard", "asks_correctness_with_draft", "高中",
    "帮我看看这道题算得对不对。草稿：左上写 2x+3=7，中间写 2x=4，下面写 x=2。",
    "左上写 2x+3=7，中间写 2x=4，下面写 x=2。",
    expected_actions=("analyze", "refuse"),
    acceptable_refusal_reasons=["out_of_scope"],
    branches={
        "analyze": analyze_gold(
            [SCOPE_LAYOUT, SCOPE_NO_PROBLEM, SCOPE_SHORT],
            {
                "organization": D(["不适用", "中"], [
                    ev("三行", "左上", "中间", "下面", "太短")],
                    "只有三行，无法判断分区",
                    unavailable_reason="只有三行，太短，无法判断分区"),
                "skipping": D(["中", "高"], [
                    ev("三行", "一行一步", "移项", "除法", "各占一行")],
                    "移项和除法各占一行"),
                "correction_pattern": D(["高", "不适用"], [
                    ev("没有划改", "没有划痕", "没有涂改")],
                    "没有划改痕迹"),
                "trial_and_error": D(["低", "不适用"], [
                    ev("只有一条", "没有标号", "一条")],
                    "只有一条路径"),
                "graphic_use": D(["不适用"], [
                    ev("没有图形", "没有坐标轴", "只有算式")],
                    "纯代数方程，没有图形",
                    unavailable_reason="纯代数方程，纸面没有图形，无法判断图形标注"),
                "draft_to_solution": D(["中", "低"], [
                    ev("下面", "末尾", "右边", "没有检验")],
                    "结果在下面，没有检验区"),
            },
            [
                H("结果旁没有检验区", ["检验", "代回", "留白"],
                  "结果旁没有检验区",
                  "算完就结束，代回原式的检验没有固定落点。",
                  "下一道方程题，在右边留一块写代回检验。"),
                H("行距偏紧", ["空行", "行距", "留空"],
                  "行距偏紧",
                  "三行贴得较近，步骤再多就没有补写空间。",
                  "下一道方程题，每两行之间留一个空行。"),
            ],
            "下一道方程题，在右边留一块写代回检验。",
            require_reply_decline=True,
            reply_decline_groups=[
                ["不判断", "不查", "不对", "只做", "只看"],
                ["对错", "算得对不对", "正确性"],
            ],
            reply_forbidden=[
                ["变式题如下", "复习计划如下", "第一周", "给你打分",
                 "完整解答如下", r"(?:你|这一步)算错了", r"(?:你|这一步)写错了"],
            ],
            reply_text="我只做版面习惯分析，不判断这道题算得对不对；"
                       "对错请交给诊断技能。",
        ),
        "refuse": refuse_gold("out_of_scope", OUT_OF_SCOPE_MSG),
    },
    notes="草稿可以做习惯分析，但必须婉拒对错判断；两种出口都可接受。",
))


# ---------------------------------------------------------------- BND-06
CASES.append(make(
    "BND-06", "boundary", "test", "easy", "problem_only", "高中",
    "请使用 $draft-coach 看看我的草稿习惯。题目是：解方程 x^2-5x+6=0。",
    "",
    expected_actions=("refuse",),
    refuse_reason="empty",
    acceptable_refusal_reasons=["empty"],
    branches={"refuse": refuse_gold("empty", EMPTY_MSG)},
    notes="只有题目、没有草稿：不能凭题目编造版面观察。",
))
