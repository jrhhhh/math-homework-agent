# -*- coding: utf-8 -*-
"""构建版面习惯基准时的公共小工具。

数据文件（cases.jsonl / ground_truth.jsonl）是**交付物**；本目录下的脚本只负责
把它们生成出来，便于审阅与重建。改案例时改这里，再跑 build_dataset.py。
"""

from __future__ import annotations

# 与当前技能边界一致的通用禁词。卡片里出现这些，说明跑到了别的 skill 的地盘。
ERROR_TERMS = ["算错", "错在", "写错", "这一步错", "漏了根", "错误是"]
LABEL_TERMS = ["粗心", "马虎", "思维混乱", "不认真", "基础差", "态度不端正"]
PLAN_TERMS = ["复习计划", "学习计划", "错题本", "每天", "每周", "连续做"]
VARIANT_TERMS = ["变式题", "练习题", "再出几道"]
SCORE_TERMS = ["打分", "评分", "扣分", "得分", "满分", "零分"]
SOLUTION_TERMS = ["完整解答", "完整解法", "整题重写", "把整道题重写"]
BAIT_TERMS = (ERROR_TERMS + LABEL_TERMS + PLAN_TERMS
              + VARIANT_TERMS + SCORE_TERMS + SOLUTION_TERMS)

# 延迟导入技能常量，保证「禁词 / 维度名 / 评分取值」只有一份来源。
# 实际读取发生在 bench/engine/rules_bridge.py；构建器这里只做静态校验，
# 因此不依赖技能运行时。


def ev(*alternatives):
    """一组可互相替代的证据锚点；调用方用 `[ev(...)]` 组成组列表。"""
    return list(alternatives)


def dim(scores, groups, topic=None, unavailable_reason=None, min_groups=1):
    return {
        "acceptable_scores": list(scores),
        "evidence_groups": [list(group) for group in groups],
        "evidence_min_groups": min_groups,
        "topic": topic,
        "unavailable_reason": unavailable_reason,
    }


def habit(name, any_terms, habit_text, impact, training):
    return {
        "name": name,
        "any": list(any_terms),
        "habit": habit_text,
        "impact": impact,
        "training": training,
    }


def analyze_gold(scope_groups, dimensions, habits, next_step, *,
                 scope_forbidden=None, require_positive=False,
                 positive_groups=None, positive_text=None,
                 require_strength=False, strength_terms=None,
                 forbidden=None, draft_source="text_reconstruction",
                 grade_level="高中", structure_warnings_allowed=None,
                 audit_warnings_allowed=None, ocr_check=False):
    return {
        "branch": "analyze",
        "scope_groups": [list(group) for group in scope_groups],
        "scope_forbidden": list(scope_forbidden or
                                ["已核对题意", "检查过计算", "确认算对",
                                 "题目没有问题", "题目没问题"]),
        "dimensions": dimensions,
        "require_positive": bool(require_positive),
        "positive_groups": [list(group) for group in (positive_groups or [])],
        "positive_text": positive_text,
        "habits": habits,
        "next_step": next_step,
        "require_strength": bool(require_strength),
        "strength_terms": list(strength_terms or []),
        "forbidden": list(forbidden or BAIT_TERMS),
        "draft_source": draft_source,
        "grade_level": grade_level,
        "structure_warnings_allowed": list(structure_warnings_allowed or []),
        "audit_warnings_allowed": list(audit_warnings_allowed or []),
        "ocr_check": bool(ocr_check),
    }


def partition_gold(block_count_range, true_problem_range, max_range_width,
                   oracle, *, required_block_source="image_layout",
                   uncertainty_groups=None, limitations_must=None,
                   must_mention_groups=None, require_non_high_confidence=False,
                   forbidden=None):
    return {
        "branch": "partition",
        "block_count_range": list(block_count_range),
        "true_problem_range": list(true_problem_range),
        "max_range_width": int(max_range_width),
        "required_block_source": required_block_source,
        "uncertainty_groups": [list(group) for group in (uncertainty_groups or [])],
        "limitations_must": [list(group) for group in (limitations_must or [])],
        "must_mention_groups": [list(group) for group in (must_mention_groups or [])],
        "require_non_high_confidence": bool(require_non_high_confidence),
        "forbidden": list(forbidden or
                          ["就是4道题", "一定是4道", "已经分好", "算错",
                           "错在", "我看出", "识别出", "OCR"]),
        "oracle": oracle,
    }


def refuse_gold(reason, message_groups, forbidden=None):
    return {
        "branch": "refuse",
        "refusal_reason": reason,
        "message_groups": [list(group) for group in message_groups],
        # 拒绝话术会提到「变式题 / 复习计划」来说明自己不做，不能按卡片禁词扫；
        # 只有明确传入的禁词才扫（例如将来边界套件里的 OCR 自读）。
        "forbidden": list(forbidden or []),
    }


def clarify_gold(ask_groups, oracle_reply, forbidden=None):
    return {
        "branch": "clarify",
        "ask_groups": [list(group) for group in ask_groups],
        "forbidden": list(forbidden or
                          ["图片上写着", "照片上写的是", "我看出写的是",
                           "识别出文字：", "转写结果", "转写如下",
                           "OCR结果", "OCR识别"]),
        "oracle_reply": oracle_reply,
    }


def make(case_id, subset, split, difficulty, category, grade_level,
         request, draft, *, source="text_reconstruction",
         has_problem_statement=False, audit_draft=None, image_note=None,
         expected_actions=("analyze",), refuse_reason=None,
         acceptable_refusal_reasons=None, severity="normal",
         provenance="synthetic", branches=None, notes=""):
    if not branches:
        raise ValueError("%s 没有 gold branch" % case_id)
    case_row = {
        "case_id": case_id,
        "subset": subset,
        "split": split,
        "difficulty": difficulty,
        "category": category,
        "grade_level": grade_level,
        "input": {
            "request": request,
            "draft": draft,
            "draft_source": source,
            "has_problem_statement": bool(has_problem_statement),
            "audit_draft": audit_draft,
            "image_note": image_note,
        },
        "expected_actions": list(expected_actions),
        "acceptable_refusal_reasons": list(acceptable_refusal_reasons or []),
        "refuse_reason": refuse_reason,
        "severity": severity,
        "provenance": provenance,
    }
    gt_row = {
        "case_id": case_id,
        "branches": branches,
        "notes": notes,
    }
    return case_row, gt_row


# 常用 scope 组
SCOPE_LAYOUT = ["只看版面", "仅看版面", "未读字符", "不读字符", "版面观察",
                "只看草稿的版面"]
SCOPE_NO_PROBLEM = ["未核对题意", "缺原题", "没有原题", "题意未核对", "不看题意",
                    "未核对题目", "没看题目"]
SCOPE_IMAGE = ["你的文字描述", "你的描述", "学生描述", "文字描述", "内容来自",
               "转述"]
SCOPE_BLOCK = ["第二题这一块", "这一块", "该块", "题目边界", "归属"]
SCOPE_SHORT = ["草稿太短", "信息不足", "只有一行", "只有三行", "无法判断",
               "需要确认", "请补充"]
SCOPE_CONFLICT = ["前后不一致", "对不上", "冲突", "请确认", "需要你确认"]
SCOPE_IMAGE_UNCONFIRMED = ["内容未经确认", "未核对内容", "只看了版面",
                           "不读字符", "看不出写的是什么"]

# 通用风险句。必须是「若…可能…」的假设句，且不出现算错类判断。
RISK_TEXT = {
    "organization": "若区域继续增多，可能不容易找到某一步。",
    "skipping": "若其中一步需要回看，可能定位不到具体位置。",
    "correction_pattern": "若之后复盘，可能分不清旧值和新值。",
    "trial_and_error": "若第一条路径走不通，可能没有另一条路可以对照。",
    "graphic_use": "若题目需要数形结合，可能少一个直观核对的角度。",
    "draft_to_solution": "若结果需要代回检验，可能只能在边上挤着写。",
}

DIM_LABEL = {
    "organization": "分区与边距",
    "skipping": "步骤分行与密度",
    "correction_pattern": "划改与自纠",
    "trial_and_error": "多路径标记",
    "graphic_use": "图形与标注",
    "draft_to_solution": "留白与检验区",
}
