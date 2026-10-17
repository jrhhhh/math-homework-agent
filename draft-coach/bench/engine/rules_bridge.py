# -*- coding: utf-8 -*-
"""按路径加载技能自己的 `scripts/_rules.py`，不重抄常量。

评测器与两道门必须用同一套维度名、评分取值、越界正则与 refuse 文案。
本模块是唯一的加载点；`_rules.py` 改了什么，这里自动跟着变。
"""

import importlib.util
import re
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parents[1]
RULES_PATH = BENCH_DIR.parent / "scripts" / "_rules.py"

if not RULES_PATH.is_file():  # pragma: no cover - 只在目录被搬走时发生
    raise ImportError("找不到技能常量文件：%s" % RULES_PATH)

_spec = importlib.util.spec_from_file_location("draft_coach_rules", str(RULES_PATH))
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)

DIM_KEYS = rules.DIM_KEYS
DIM_LABEL = rules.DIM_LABEL
SCORES_ANY = rules.SCORES_ANY
UNAVAILABLE = rules.UNAVAILABLE
UNAVAILABLE_REASON_RE = rules.UNAVAILABLE_REASON_RE
VAGUE_ACTION_RE = rules.VAGUE_ACTION_RE
META_VOCAB_RE = rules.META_VOCAB_RE
DRAFT_CORRECTION_RE = rules.DRAFT_CORRECTION_RE
PARTITION_ASSERTIVE_RE = rules.PARTITION_ASSERTIVE_RE
PARTITION_ERROR_CLAIM_RE = rules.PARTITION_ERROR_CLAIM_RE
PARTITION_OCR_CLAIM_RE = rules.PARTITION_OCR_CLAIM_RE
PARTITION_CONFIRM_CUES = rules.PARTITION_CONFIRM_CUES
PARTITION_LIMITATION_CUES = rules.PARTITION_LIMITATION_CUES
REFUSALS = rules.REFUSALS
norm = rules.norm
card_texts = rules.card_texts
out_of_scope_matches = rules.out_of_scope_matches


# 本评测额外使用的两条窄规则。技能脚本的 audit 不抓「算错」这类措辞：
# 它只管越界到别的 skill，而「本技能不判对错」是 SKILL.md 的另一条边界。
ERROR_CLAIM_RE = re.compile(
    r"算错|错在|写错|这一步错|错误是|漏了(?:根|一步|条件|符号|项|解)|正确答案"
)

# 只有“真的把图片/照片上的字符念出来”才算 OCR 越界；
# 「我不做转写」「照片上写着什么我看不清」不算。
OCR_CLAIM_RE = re.compile(
    r"(?:图片|照片|纸上)(?:上|里)?(?:写着|写的是)"
    r"|我看到.{0,6}(?:写着|写的是)"
    r"|我(?:读|看)出.{0,12}(?:字|式子|内容|数字|写的是)"
    r"|识别出.{0,8}(?:文字|式子|数字)"
    r"|转写(?:结果|如下)|OCR\s*(?:结果|识别)"
)

_NEGATION_BEFORE_RE = re.compile(
    r"(?:没有|没|不|未|无需|不需要|不能|无法|不做)\s*$")
_NEGATION_AFTER_RE = re.compile(
    r"什么|啥|看不清|看不出|无法辨认|不清晰|不认识|未经确认|未确认")


def error_claims(text):
    """返回真正的计算对错断言；假设句「若…可能…」与否定句不算。"""
    hits = []
    text = str(text or "")
    for match in ERROR_CLAIM_RE.finditer(text):
        before = text[max(0, match.start() - 10):match.start()]
        if _NEGATION_BEFORE_RE.search(before):
            continue
        if re.search(r"若|如果|一旦|可能|会|容易|也许", before):
            continue
        hits.append(match.group(0))
    return hits


def ocr_claims(text):
    """返回真正的「我读出了图上的字」措辞；拒绝转写不算。"""
    hits = []
    text = str(text or "")
    for match in OCR_CLAIM_RE.finditer(text):
        before = text[max(0, match.start() - 12):match.start()]
        after = text[match.end():match.end() + 24]
        if _NEGATION_BEFORE_RE.search(before):
            continue
        if _NEGATION_AFTER_RE.search(after):
            continue
        hits.append(match.group(0))
    return hits


def contains_any(text, alternatives):
    """归一化后做子串匹配；单个汉字锚点也保留（例如 ①）。"""
    haystack = norm(text)
    return any(norm(alt) and norm(alt) in haystack for alt in alternatives)


def matched_groups(text, groups):
    """返回每个组是否命中；空组视为不要求。"""
    return [contains_any(text, group) for group in (groups or [])]


def all_groups_match(text, groups):
    flags = [flag for group, flag in zip(groups or [], matched_groups(text, groups))
             if group]
    return all(flags) if flags else True


def any_group_match(text, groups):
    return any(matched_groups(text, groups))


def fraction(values):
    kept = [value for value in values if value is not None]
    if not kept:
        return None
    return sum(kept) / len(kept)
