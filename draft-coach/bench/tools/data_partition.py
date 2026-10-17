# -*- coding: utf-8 -*-
"""C 子集：整张草稿纸的版面分块（partition 出口，5 条）。"""

from _common import make, partition_gold

CASES = []


def oracle(blocks, estimated, count_range, confidences, uncertainty,
           confirmation_question, limitations):
    return {
        "blocks": blocks,
        "estimated": estimated,
        "count_range": list(count_range),
        "confidences": list(confidences),
        "uncertainty": uncertainty,
        "confirmation_question": confirmation_question,
        "limitations": list(limitations),
    }


LIMITS = ["只看版面，不读字符", "块数不等于题目数", "归属需要学生确认"]


# ---------------------------------------------------------------- PAR-01
CASES.append(make(
    "PAR-01", "partition", "development", "easy", "four_clear_blocks", "高中",
    "请使用 $draft-coach 看一下这张草稿纸，大概做了几道题？",
    "",
    source="image_description",
    image_note="一张 A4 草稿纸，中间有一条竖向折痕，把纸分成左右两栏；左栏上下各有一块，"
              "中间隔了约三行空白；右栏上半一块、下半一块，两块之间有一条手画的横线；"
              "四块大小接近，没有跨栏的箭头。",
    expected_actions=("partition",),
    branches={"partition": partition_gold(
        [3, 5], [3, 4], 3,
        oracle(
            4, 3, [3, 4], ["高", "中", "中", "高"],
            "中间折痕把纸分成左右两栏，右栏下半块与左栏下半块是否同一题、"
            "跨栏内容是否连续，只看版面分不清。",
            "我大致看到 4 块、像 3–4 道题；右栏下半块和左栏下半块是同一题吗？",
            LIMITS,
        ),
        uncertainty_groups=[
            ["折痕", "左右", "跨栏"],
            ["分不清", "可能", "不确定", "低置信"],
        ],
        limitations_must=[["块数", "不等于", "题目数"]],
    )},
    notes="四块分明，但仍要给范围并请学生确认；不能因为分隔清楚就断言题数。",
))


# ---------------------------------------------------------------- PAR-02
CASES.append(make(
    "PAR-02", "partition", "development", "medium", "ambiguous_adjacent_blocks", "高中",
    "请使用 $draft-coach 看一下这张草稿纸，大概做了几道题？",
    "",
    source="image_description",
    image_note="一张草稿纸，左边一大块从上写到下；右上角一小块，和左边之间有一条竖向"
              "留白；右下角一块紧接右上角，中间只隔一行，书写方向相同。右上和右下的"
              "大小不同。",
    expected_actions=("partition",),
    branches={"partition": partition_gold(
        [2, 4], [2, 3], 3,
        oracle(
            3, 2, [2, 3], ["高", "中", "低"],
            "右下块紧接右上块，中间只隔一行，可能是同一题的第二问，也可能是一次新尝试；"
            "只看版面分不清。",
            "我大致看到 3 块、像 2–3 道题；右下角这块是接着右上角那道题的吗？",
            LIMITS,
        ),
        uncertainty_groups=[
            ["只隔一行", "一行", "紧接"],
            ["同一题", "第二问", "新尝试", "分不清", "可能"],
        ],
        require_non_high_confidence=True,
        limitations_must=[["块数", "不等于", "题目数"]],
    )},
    notes="相邻块只隔一行时应标低置信并写入 uncertainty；不能硬判成两道题。",
))


# ---------------------------------------------------------------- PAR-03
CASES.append(make(
    "PAR-03", "partition", "development", "easy", "single_block", "高中",
    "请使用 $draft-coach 看一下这张草稿纸，大概做了几道题？",
    "",
    source="image_description",
    image_note="整张纸只有一块书写区域：从左到右一行行写下来，周围留白很宽，"
              "没有分隔线、折痕或第二块区域。",
    expected_actions=("partition",),
    branches={"partition": partition_gold(
        [1, 1], [1, 1], 0,
        oracle(
            1, 1, [1, 1], ["中"],
            "版面只有一块，周围留白很宽，没有分隔线；这一块里是否含多个小问，"
            "只看版面无法确认。",
            "我大致看到 1 块、像 1 道题；这块里面是不是还有别的小问？",
            LIMITS,
        ),
        uncertainty_groups=[
            ["只有一块", "没有分隔", "周围", "留白"],
            ["可能", "无法确认", "不排除", "小问"],
        ],
        require_non_high_confidence=True,
        limitations_must=[["块数", "不等于", "题目数"]],
    )},
    notes="单块也要给不确定说明；高置信 + 精确范围会触发分区门的过度自信警告。",
))


# ---------------------------------------------------------------- PAR-04
CASES.append(make(
    "PAR-04", "partition", "validation", "hard", "dense_with_crossed_blocks", "高中",
    "请使用 $draft-coach 看一下这张草稿纸，大概做了几道题？",
    "",
    source="image_description",
    image_note="整页写得很满：左上、右上、中间、左下、右下各有书写块，中下部还有两块"
              "小区域被划掉；块与块之间有的只隔半行，有的被一条斜线分开；"
              "没有清晰的题号栏。",
    expected_actions=("partition",),
    branches={"partition": partition_gold(
        [5, 9], [4, 7], 4,
        oracle(
            7, 5, [4, 7],
            ["高", "中", "中", "低", "中", "低", "中"],
            "中下部有两块被划掉的区域，可能只是废弃的尝试，不算独立题目；"
            "相邻块有的只隔半行，边界分不清。",
            "我大致看到 7 块、像 4–7 道题；中下部被划掉的两块还要算吗？",
            LIMITS,
        ),
        uncertainty_groups=[
            ["划掉", "划去"],
            ["不算", "废弃", "可能不是", "尝试", "分不清"],
        ],
        must_mention_groups=[
            ["划掉", "划去", "涂掉"],
            ["不算", "废弃", "可能不是", "尝试"],
        ],
        require_non_high_confidence=True,
        limitations_must=[["块数", "不等于", "题目数"]],
    )},
    notes="密集且含划掉区域：必须说明废弃块可能不算题目；块数不等于题目数。",
))


# ---------------------------------------------------------------- PAR-05
CASES.append(make(
    "PAR-05", "partition", "test", "medium", "two_attempts_connected", "高中",
    "请使用 $draft-coach 看一下这张草稿纸，大概做了几道题？",
    "学生描述：纸面分三块：左上第一块写了半页；右上第二块和左上块之间有一条横向空白；"
    "下方第三块横跨整页，左半和右上的内容用箭头连到第三块；右上块和下方块的"
    "字迹方向一致，像是接着写。",
    source="text_reconstruction",
    expected_actions=("partition",),
    branches={"partition": partition_gold(
        [3, 4], [2, 3], 3,
        oracle(
            3, 2, [2, 3], ["高", "中", "低"],
            "右上块和下方块用箭头连到第三块，字迹方向一致，像是接着写；它们可能是"
            "同一题的第二问或两次尝试，只看版面分不清。",
            "我大致看到 3 块、像 2–3 道题；右上和下方是同一题的两次尝试吗？",
            LIMITS,
        ),
        uncertainty_groups=[
            ["箭头", "连到", "接着", "方向一致"],
            ["同一题", "第二问", "两次尝试", "分不清", "可能"],
        ],
        limitations_must=[["块数", "不等于", "题目数"]],
        required_block_source="student_text",
    )},
    notes="学生用文字描述整张纸；block_source 应为 student_text。"
          "箭头把两块连到第三块：分块数不等于题目数；不能把一次换方法的尝试算成新题。",
))
