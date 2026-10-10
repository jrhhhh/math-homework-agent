#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""error_card_check.py — "错题病理图"的三道门：结构 / 证据·引文 / 出题核验。

用法：
  patterns --problem "题目文本"
  validate  --card CARD.json
  audit     --card CARD.json --cases CASES.json [--strict]
  practice  --card CARD.json [--verify-answers] [--strict]

约定：
  - 所有结果以 JSON 打到 stdout；
  - 退出码：0 = 通过 / 干净；1 = 未通过（有 error，或 --strict 下出现 warning）；2 = 输入非法。
  - 仅使用 Python 标准库，无第三方依赖；不用 Decimal/NumPy，答案核验走 fractions 精确有理数。
  - 退出码语义与同伴仓库 scripts/handoff_check.py 一致（0 准入 / 1 有效但不准入 / 2 非法输入），
    但三道门查的东西完全不同，不可互相替代。

能力边界（诚实声明，别把它当数学判断）：
  - validate 只查形状，audit 只查措辞与引用，两者都不做数学判断；
    "这三条模式是不是真的共享"只能靠人读出来。
  - case_count / cause.method 都是**声明值**：脚本只能查"有没有虚报、有没有被声明为廉价核验"，
    查不出同伴那次审查是否真的做过。
  - practice --verify-answers 只在**可解析为一元/二元一次方程（组）**这一小类题上
    用精确有理数真算一次；其余题型一律 skipped，不假装验过。
  - 出题器与答案验证器由同一作者编写，存在循环依赖：即使脚本真的算了，
    这只是"工具辅助核验"，不是独立验证（同伴 SKILL.md 明确禁止把同一助手重做称为独立验证）。
  - 三道门都通过，也只说明"卡片长得对、证据绑得对、一小类答案代回成立"，不证明教学质量。
"""

import argparse
import hashlib
import json
import re
import sys
from fractions import Fraction
from itertools import combinations

try:  # Windows 控制台默认编码可能是 GBK，统一成 UTF-8，免得中文与数学符号炸掉
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------- 词表

# 跨题聚合维度（学生维度）：pattern -> (能力假设, 同义写法, 关键词)
# 与同伴的六类错误分类**不同维**：同伴那六类是题目维度的判断尺度，
# 这里说的是"多道题合起来反复出现哪种加工失败"。
PATTERNS = {
    "条件加工缺位": {
        "gaps": ("条件提取与转译",),
        "synonyms": ("审题不清", "审题漏条件", "漏条件", "条件遗漏"),
        "keywords": ("定义域", "范围", "非零", "约束", "条件", "分母", "被开方"),
    },
    "分支穷尽不足": {
        "gaps": ("逻辑完备性",),
        "synonyms": ("分类讨论不全", "漏讨论", "讨论不全"),
        "keywords": ("分类", "情形", "分支", "边界", "端点", "讨论"),
    },
    "前提检验缺位": {
        "gaps": ("定理适用性判断",),
        "synonyms": ("前提检验", "定理误用", "没验证前提"),
        "keywords": ("前提", "定理", "条件", "验证", "判别式", "适用"),
    },
    "概念边界混淆": {
        "gaps": ("概念辨析",),
        "synonyms": ("概念混淆", "定义不清"),
        "keywords": ("充分", "必要", "定义", "概念", "混淆", "充要"),
    },
    "过程规范松动": {
        "gaps": ("步骤留痕与记录",),
        "synonyms": ("计算跳步", "条理不清", "跳步", "书写不规范"),
        "keywords": ("跳步", "心算", "步骤", "书写", "省略", "过程"),
    },
    "结果自检缺位": {
        "gaps": ("自我验证",),
        "synonyms": ("检验缺位", "不检验", "不自检"),
        "keywords": ("代回", "检验", "验算", "自检", "估算", "核对"),
    },
    "表达精度不足": {
        "gaps": ("数学语言",),
        "synonyms": ("表达不严谨", "表述不清"),
        "keywords": ("单位", "范围", "约为", "精确", "表述", "符号语言"),
    },
}

# 同伴 math-error-diagnosis/references/error-types.md 的六类判断尺度。
# 原样沿用，不改名、不细分。
CAUSE_TYPES = ("运算错误", "条件失效", "分支/边界遗漏", "逻辑错误", "定理误用", "论证缺口")
CAUSE_TYPE_SYNONYMS = {"分支边界遗漏": "分支/边界遗漏", "边界遗漏": "分支/边界遗漏"}

# 同伴 scripts/handoff_check.py 同款枚举：核验方式。
# numeric_only / none 不足以支持完整过程，不准入。
CAUSE_METHODS = ("assistant_review", "independent_review",
                 "tool_assisted_review", "numeric_only", "none")
WEAK_METHODS = ("numeric_only", "none")

TOP_LEVEL_FIELDS = ("error_patterns", "cross_case_commonality", "strength_kept",
                    "capability_profile", "next_training_target",
                    "practice_authorized", "practice_items", "generation_basis")
PATTERN_FIELDS = ("pattern", "cause_type", "evidence", "case_count",
                  "capability_hypothesis", "countermeasure")
PRACTICE_FIELDS = ("id", "pattern_ref", "difficulty", "student_prompt",
                   "answer", "solution_steps", "source_pattern")

PATTERN_COUNT = 3
PRACTICE_COUNT = 5
MIN_CASE_COUNT = 2
MIN_THICK_PATTERNS = 2
DIFFICULTIES = ("同型巩固", "变式迁移", "综合拔高")

TENTATIVE_WORDS = ("假设", "待验证", "暂定", "初步", "疑似", "可能")
STATISTICAL_WORDS = ("反复", "多次", "这批", "屡次", "若干次", "几次", "三次以上")

# 明确"自产错因"的句式：错因只能引用同伴结论，不能自己下。
NEW_CAUSE_PATTERNS = (
    re.compile(r"根本原因"),
    re.compile(r"真正的问题"),
    re.compile(r"你之所以[^，。；\n]{0,12}(是因为|错在|问题在)"),
    re.compile(r"错的?真正原因"),
)
OVERRIDE_PATTERNS = (
    re.compile(r"不是[^，。；\n]{0,8}(问题|原因)"),
    re.compile(r"其实不是"),
    re.compile(r"并非[^，。；\n]{0,8}(问题|原因)"),
)
STABLE_JUDGMENT_PATTERNS = (
    re.compile(r"一直很?弱"),
    re.compile(r"长期(能力)?(不足|偏弱|薄弱)"),
    re.compile(r"天生"),
    re.compile(r"就是不会"),
    re.compile(r"能力(差|很差|不行)"),
)
VERDICT_PATTERNS = (
    re.compile(r"你[^，。；\n]{0,6}算错了"),
    re.compile(r"这一步(就)?错了"),
    re.compile(r"你(做|答)错了"),
)
LANGUAGE_PATTERNS = (
    re.compile(r"你(太|就是)?(粗心|马虎|不细心|不认真)"),
    re.compile(r"你[^，。；\n]{0,4}(笨|蠢|差)"),
)
# 越界：这些是别的 skill 的疆域
SOLVE_MARKERS = ("解：", "解:", "证明：", "证明:", "综上所述", "原式=", "答案是", "答案为")
VARIANT_PATTERNS = (
    re.compile(r"变式题"),
    re.compile(r"下面这道题"),
    re.compile(r"试试这道"),
    re.compile(r"再来一道"),
    re.compile(r"同类练习"),
)
PLAN_PATTERNS = (
    re.compile(r"每天[^。；\n]{0,6}\d*\s*道"),
    re.compile(r"一周(内|后)?"),
    re.compile(r"复习计划"),
    re.compile(r"\d+\s*天内"),
    re.compile(r"每天练"),
)
SCORE_PATTERNS = (re.compile(r"得分"), re.compile(r"扣\s*\d+\s*分"), re.compile(r"正确率\s*\d"))
CONFIDENCE_PATTERNS = (re.compile(r"置信度"), re.compile(r"可信度"))
PROBE_PATTERNS = (re.compile(r"你真的理解"), re.compile(r"再讲讲为什么"), re.compile(r"说说你的思路"))
TEMPLATE_PATTERNS = (re.compile(r"多练练"), re.compile(r"注意一下"), re.compile(r"认真点"),
                     re.compile(r"小心一点"), re.compile(r"以后注意"))
NUMERIC_ONLY_ANSWER = re.compile(r"^\s*-?\d+(?:\.\d+)?\s*$")

EVIDENCE_RE = re.compile(r"^\s*[\[【]([^\]】#]+)#([0-9a-f]{12})[\]】]")
PUNCT_RE = re.compile(r"[\s　，。？！、；：,.?!;:'\"“”‘’（）()【】\[\]]+")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
IDENT_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,7}")
CASE_ID_RE = re.compile(r"[\[【]([^\]】#]+)#[0-9a-f]{12}[\]】]")
# 共同点里可能写 [T1#指纹] 也可能只写 [T1]：两种都算"点到了这个题号"
PLAIN_ID_RE = re.compile(r"[\[【]([^\]】#\s]+)(?:#[0-9a-f]{12})?[\]】]")
# 正文里题号也常直接写成"第 T1、T3 题"，不套方括号，用它来认出题依据
CASE_ID_LIKE_RE = re.compile(r"\bT\d+\b")
TENTATIVE_RE = re.compile("|".join(TENTATIVE_WORDS))
STOP_TOKENS = frozenset({"已知", "求其", "下列", "的是", "一个", "以及", "其中", "如何", "什么"})

# PATTERN_HINTS: 从题面给关键词初判（只是提示，不能替代读题）
PROBLEM_HINTS = [
    {"name": "一元一次方程 / 方程组", "keywords": ("一元一次", "方程组", "代入法", "加减消元", "解方程")},
    {"name": "一元二次方程", "keywords": ("一元二次", "判别式", "求根公式", "因式分解")},
    {"name": "函数与导数", "keywords": ("导数", "极值", "最值", "单调")},
    {"name": "三角", "keywords": ("三角", "正弦", "余弦", "sin", "cos", "tan")},
    {"name": "数列", "keywords": ("数列", "等差", "等比", "通项")},
    {"name": "圆锥曲线", "keywords": ("椭圆", "双曲线", "抛物线", "焦点", "准线")},
    {"name": "概率统计", "keywords": ("概率", "分布列", "期望", "方差")},
    {"name": "几何证明", "keywords": ("证明", "平行", "垂直", "全等", "相似")},
]


# ---------------------------------------------------------------- 工具

def emit(payload, code):
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(code)


def norm(text):
    """归一化：去掉空白与标点、转小写。用于重复检测与关联度检查。"""
    return PUNCT_RE.sub("", str(text)).lower()


def high_signal_tokens(text):
    """高信号线索：多位数/小数 + ASCII 标识符。

    与同伴"忽略个位数字"的口径一致：单个数字字符太容易误撞（"2" 会撞上 "25"），
    所以这里只保留长度 >= 2 的纯数字串；一位数只在带小数点时保留。
    """
    tokens = []
    for token in NUM_RE.findall(text):
        if len(token) >= 2:
            tokens.append(token)
    tokens += IDENT_RE.findall(text)
    seen, out = set(), []
    for token in tokens:
        low = token.lower()
        if low in STOP_TOKENS or low in seen:
            continue
        seen.add(low)
        out.append(token)
    return out


def compute_fingerprint(problem, solution, grade_level="高中"):
    """内容指纹：算法与同伴 scripts/handoff_check.py 的 version() 逐字相同，取前 12 位。

    同伴用完整 SHA-256 判"解答版本过期"（单题准入）；这里取前 12 位，
    只用于"这条证据引用的是不是当前这份题面/过程"。
    """
    data = {"grade_level": grade_level, "problem": problem, "student_solution": solution}
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def load_json(path, label):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        emit({"error": "%s file not found" % label, "path": path}, 2)
    except json.JSONDecodeError as exc:
        emit({"error": "%s file is not valid JSON" % label, "path": path, "detail": str(exc)}, 2)
    except OSError as exc:
        emit({"error": "cannot read %s file" % label, "path": path, "detail": str(exc)}, 2)
    return payload


def load_card(path):
    card = load_json(path, "card")
    if not isinstance(card, dict):
        emit({"error": "card must be a JSON object", "path": path,
              "got": type(card).__name__}, 2)
    return card


def load_cases(path):
    cases = load_json(path, "cases")
    if not isinstance(cases, list):
        emit({"error": "cases must be a JSON array", "path": path,
              "got": type(cases).__name__}, 2)
    index = {}
    for position, item in enumerate(cases):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
            emit({"error": "each case must be an object with a non-empty string id",
                  "path": path, "index": position}, 2)
        index[item["id"].strip()] = item
    return cases, index


def first_segment_texts(card):
    """第一段（归因）的文本，供引文门/越界门扫描。

    practice_items 里的 student_prompt 天然就是题目正文，必须排除——
    否则"下面这道题"这类合法题干会被 A_VARIANT 误伤。
    """
    out = []
    patterns = card.get("error_patterns")
    if isinstance(patterns, list):
        for index, item in enumerate(patterns, start=1):
            if not isinstance(item, dict):
                continue
            for field in ("pattern", "cause_type", "evidence", "capability_hypothesis",
                          "countermeasure"):
                value = item.get(field)
                if isinstance(value, str):
                    out.append(("error_patterns[%d].%s" % (index, field), value))
    for field in ("cross_case_commonality", "strength_kept",
                  "capability_profile", "next_training_target", "generation_basis"):
        value = card.get(field)
        if isinstance(value, str) and value.strip():
            out.append((field, value))
    return out


def pattern_by_name(name):
    return PATTERNS.get(name)


def gap_belongs(pattern, gap):
    spec = PATTERNS.get(pattern)
    return bool(spec) and gap in spec["gaps"]


def referable_patterns(card):
    """可以拿来做 pattern_ref 的模式序号（1 基）：case_count >= 2 才准出题。"""
    out = {}
    patterns = card.get("error_patterns")
    if not isinstance(patterns, list):
        return out
    for index, item in enumerate(patterns, start=1):
        if not isinstance(item, dict):
            continue
        count = item.get("case_count")
        if isinstance(count, int) and count >= MIN_CASE_COUNT:
            out[index] = item.get("pattern")
    return out


# ---------------------------------------------------------------- patterns

def cmd_patterns(args):
    problem = (args.problem or "").strip()
    if not problem:
        emit({"error": "--problem must be a non-empty string"}, 2)

    low = problem.lower()
    hits = []
    for hint in PROBLEM_HINTS:
        matched = [kw for kw in hint["keywords"] if kw.lower() in low]
        if matched:
            hits.append({"question_type": hint["name"], "matched_keywords": matched})

    emit({
        "action": "patterns",
        "input": {"problem": problem},
        "method": "打印两份菜单 + 关键词启发式初判（未命中只代表关键词表没覆盖）",
        "aggregation_dimensions": [
            {"pattern": name, "capability_hypothesis": spec["gaps"][0],
             "synonyms": list(spec["synonyms"]), "keywords": list(spec["keywords"])}
            for name, spec in PATTERNS.items()
        ],
        "peer_cause_types": list(CAUSE_TYPES),
        "note": "聚合维度是**学生维度**（哪种加工反复失败）；cause_type 是**题目维度**"
                "（同伴 error-types.md 的六类判断尺度）。两者不同维，互不替代、互不细分。",
        "topic_hints": hits,
        "authority": "heuristic-hint-only",
        "capability_note": "关键词命中只是提示，可能误判；必须以读题结论为准，"
                           "不得用本输出替代对学生错题的理解。",
    }, 0)


# ---------------------------------------------------------------- validate

def cmd_validate(args):
    card = load_card(args.card)
    errors, warnings = [], []

    extra = [f for f in card if f not in TOP_LEVEL_FIELDS]
    missing = [f for f in TOP_LEVEL_FIELDS if f not in card]
    if extra or missing:
        errors.append({"code": "E_FIELDS", "missing": missing, "extra": extra,
                       "detail": "顶层必须恰好 %d 个字段" % len(TOP_LEVEL_FIELDS)})

    for field in ("cross_case_commonality", "strength_kept", "capability_profile",
                  "next_training_target"):
        value = card.get(field)
        if field in card and (not isinstance(value, str) or not value.strip()):
            errors.append({"code": "E_FIELDS", "field": field,
                           "detail": "必须是非空字符串"})

    patterns = card.get("error_patterns")
    if isinstance(patterns, list):
        if len(patterns) != PATTERN_COUNT:
            errors.append({"code": "E_COUNT", "count": len(patterns),
                           "detail": "error_patterns 必须恰好 %d 条" % PATTERN_COUNT})
        thick = 0
        seen_patterns = {}
        for index, item in enumerate(patterns, start=1):
            if not isinstance(item, dict):
                errors.append({"code": "E_ITEM_FIELDS", "index": index,
                               "detail": "每条必须是 JSON 对象"})
                continue
            extra_item = [f for f in item if f not in PATTERN_FIELDS]
            missing_item = [f for f in PATTERN_FIELDS if f not in item]
            if extra_item or missing_item:
                errors.append({"code": "E_ITEM_FIELDS", "index": index,
                               "missing": missing_item, "extra": extra_item,
                               "detail": "每条必须恰好 %d 个字段" % len(PATTERN_FIELDS)})

            name = item.get("pattern")
            if isinstance(name, str):
                resolved = name
                if resolved not in PATTERNS:
                    for canonical, spec in PATTERNS.items():
                        if resolved in spec["synonyms"]:
                            resolved = canonical
                            break
                if resolved not in PATTERNS:
                    errors.append({"code": "E_PATTERN_UNKNOWN", "index": index, "pattern": name,
                                   "detail": "不在跨题聚合维度表内；如为同义写法请核对 2.1 表"})
                else:
                    if resolved in seen_patterns:
                        errors.append({"code": "E_PATTERN_DUP", "index": index, "pattern": resolved,
                                       "detail": "与第 %d 条重复" % seen_patterns[resolved]})
                    else:
                        seen_patterns[resolved] = index

            cause = item.get("cause_type")
            if isinstance(cause, str):
                canonical = CAUSE_TYPE_SYNONYMS.get(cause, cause)
                if canonical not in CAUSE_TYPES:
                    errors.append({"code": "E_CAUSE_TYPE_UNKNOWN", "index": index,
                                   "cause_type": cause,
                                   "detail": "只能取同伴六类：" + " / ".join(CAUSE_TYPES)})

            count = item.get("case_count")
            if isinstance(count, bool) or not isinstance(count, int):
                errors.append({"code": "E_ITEM_FIELDS", "index": index, "field": "case_count",
                               "detail": "case_count 必须是整数"})
            elif count < MIN_CASE_COUNT:
                errors.append({"code": "E_CASE_COUNT_THIN", "index": index, "case_count": count,
                               "detail": "一条模式至少要有 %d 道不同题目支撑，"
                                         "否则就是对单题下长期判断" % MIN_CASE_COUNT})
            else:
                thick += 1

            evidence = item.get("evidence")
            if isinstance(evidence, str) and not EVIDENCE_RE.match(evidence):
                errors.append({"code": "E_EVIDENCE_FORM", "index": index, "evidence": evidence,
                               "detail": "必须以 [题号#12位内容指纹] 开头"})

            gap = item.get("capability_hypothesis")
            if isinstance(gap, str):
                known = any(gap in spec["gaps"] for spec in PATTERNS.values())
                if not known:
                    errors.append({"code": "E_GAP_UNKNOWN", "index": index, "gap": gap,
                                   "detail": "不在聚合维度表的能力假设取值域内"})
                elif isinstance(name, str) and resolved in PATTERNS and not gap_belongs(resolved, gap):
                    warnings.append({"code": "W_GAP_MISMATCH", "index": index,
                                     "pattern": resolved, "gap": gap,
                                     "detail": "能力假设与聚合维度不搭（关键词匹配，可能误报）"})

            counter = item.get("countermeasure")
            if isinstance(counter, str):
                if len(norm(counter)) < 8:
                    warnings.append({"code": "W_SHORT", "index": index, "field": "countermeasure",
                                     "detail": "过短，可能敷衍"})
                for template in TEMPLATE_PATTERNS:
                    if template.search(counter):
                        warnings.append({"code": "W_TEMPLATE", "index": index, "text": counter,
                                         "detail": "命中不可执行模板：%s" % template.pattern})
                        break

        if len(patterns) == PATTERN_COUNT and thick < MIN_THICK_PATTERNS:
            errors.append({"code": "E_PATTERN_EVIDENCE_THIN", "thick": thick,
                           "detail": "%d 条模式里达到 case_count >= %d 的少于 %d 条"
                                     % (PATTERN_COUNT, MIN_CASE_COUNT, MIN_THICK_PATTERNS)})

    common = card.get("cross_case_commonality")
    if isinstance(common, str):
        ids = set(m.group(1).strip() for m in PLAIN_ID_RE.finditer(common))
        if len(ids) < MIN_CASE_COUNT:
            errors.append({"code": "E_COMMONALITY_NO_IDS", "found": sorted(ids),
                           "detail": "必须点到至少 %d 个不同题号" % MIN_CASE_COUNT})

    strength = card.get("strength_kept")
    if isinstance(strength, str) and len(norm(strength)) < 8:
        warnings.append({"code": "W_SHORT", "field": "strength_kept", "detail": "过短，可能敷衍"})

    profile = card.get("capability_profile")
    if isinstance(profile, str):
        mentioned = set()
        for name, spec in PATTERNS.items():
            for gap in spec["gaps"]:
                if gap and gap in profile:
                    mentioned.add(gap)
        if not mentioned:
            errors.append({"code": "E_PROFILE_UNKNOWN", "profile": profile,
                           "detail": "画像里没有任何能力假设标签"})
        elif len(mentioned) > 1:
            errors.append({"code": "E_PROFILE_MULTI", "found": sorted(mentioned),
                           "detail": "画像必须聚焦一个能力标签"})
        if not TENTATIVE_RE.search(profile):
            warnings.append({"code": "W_TENTATIVE", "profile": profile,
                             "detail": "缺少'假设/待验证/暂定/初步'类限定词，读起来像稳定判定"})

    target = card.get("next_training_target")
    if isinstance(target, str):
        found = set()
        for name, spec in PATTERNS.items():
            for gap in spec["gaps"]:
                if gap and gap in target:
                    found.add(gap)
            if name in target:
                found.add(name)
        if not found:
            errors.append({"code": "E_TARGET_UNKNOWN", "target": target,
                           "detail": "至少要出现一个能力标签或聚合维度名"})
        elif len(found) > 1:
            warnings.append({"code": "W_TARGET_MULTI", "found": sorted(found),
                             "detail": "应恰好聚焦一个"})

    emit({
        "action": "validate",
        "input": {"card": args.card},
        "method": "字段完整性 + 恰好 3 条模式 + 双词表白名单 + case_count 样本量 + "
                  "证据格式（含内容指纹）+ 画像聚焦与限定词",
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
        "capability_note": "结构门不是数学判断：card 字段齐、样本量达标，不等于归因成立。",
    }, 0 if not errors else 1)


# ---------------------------------------------------------------- audit

def cmd_audit(args):
    card = load_card(args.card)
    cases, case_index = load_cases(args.cases)
    errors, warnings = [], []

    if len(cases) < MIN_CASE_COUNT:
        errors.append({"code": "E_TOO_FEW_CASES", "count": len(cases),
                       "detail": "归纳至少需要 %d 道题：一题无法跨题，"
                                 "请先用同伴 math-error-diagnosis 再攒几道" % MIN_CASE_COUNT})

    # 每题的内容指纹与同伴结论状态
    for case_id, item in case_index.items():
        problem = item.get("problem") if isinstance(item.get("problem"), str) else ""
        solution = item.get("student_solution") if isinstance(item.get("student_solution"), str) else ""
        item["_fingerprint"] = compute_fingerprint(problem, solution,
                                                   item.get("grade_level", "高中"))
        cause = item.get("cause")
        if not isinstance(cause, dict) or not str(cause.get("summary", "")).strip():
            errors.append({"code": "E_CAUSE_MISSING", "case": case_id,
                           "detail": "该题没有可引用的同伴结论（cause.summary 为空）"})
            item["_cause_ok"] = False
            continue
        item["_cause_ok"] = True
        canonical = CAUSE_TYPE_SYNONYMS.get(cause.get("type"), cause.get("type"))
        if canonical not in CAUSE_TYPES:
            errors.append({"code": "E_CAUSE_TYPE_MISMATCH", "case": case_id,
                           "cause_type": cause.get("type"),
                           "detail": "cause.type 不在同伴六类内，无法作为引用来源"})
        method = cause.get("method")
        if method in WEAK_METHODS:
            errors.append({"code": "E_CAUSE_UNVERIFIED", "case": case_id, "method": method,
                           "detail": "核验方式不足以支持完整过程（沿用同伴 handoff_check 标准）"})
        elif method not in CAUSE_METHODS:
            errors.append({"code": "E_CAUSE_UNVERIFIED", "case": case_id, "method": method,
                           "detail": "method 取值非法；合法五值见 SKILL.md"})
        unresolved = cause.get("unresolved_items")
        if not isinstance(unresolved, list):
            errors.append({"code": "E_CAUSE_UNRESOLVED", "case": case_id,
                           "detail": "unresolved_items 必须是数组（空数组表示已闭合）"})
        elif unresolved:
            errors.append({"code": "E_CAUSE_UNRESOLVED", "case": case_id,
                           "items": unresolved, "detail": "该题还有待解决事项，不能当作已闭合证据"})
        item["_cause_type"] = canonical

    # 证据门
    patterns = card.get("error_patterns")
    touched_cases = set()
    cause_types_used = []
    if isinstance(patterns, list):
        for index, item in enumerate(patterns, start=1):
            if not isinstance(item, dict):
                continue
            evidence = item.get("evidence")
            if not isinstance(evidence, str):
                continue
            match = EVIDENCE_RE.match(evidence)
            if not match:
                continue  # 格式已在 validate 里报过
            case_id, fingerprint = match.group(1).strip(), match.group(2)
            touched_cases.add(case_id)
            target = case_index.get(case_id)
            if target is None:
                errors.append({"code": "E_EVIDENCE_NO_CASE", "index": index, "case": case_id,
                               "detail": "引用了没有交上来的题"})
                continue
            if fingerprint != target["_fingerprint"]:
                errors.append({"code": "E_EVIDENCE_STALE", "index": index, "case": case_id,
                               "cited": fingerprint, "current": target["_fingerprint"],
                               "detail": "指纹与当前题面/过程不符：引用的是旧版本证据"})
            # 证据里的关键词必须排除引用前缀本身（[题号#指纹] 会被正则切出
            # "T2" / "f98b1134" / "11345" 这类碎片，不排掉会稳定误报）。
            body = EVIDENCE_RE.sub(" ", evidence, count=1)
            # 证据里还会顺手提到别的题号（"同批题里 [T1#...] 也……"），
            # 那些是引用而不是内容关键词，必须一起排掉，否则稳定误报"找不到"。
            body = PLAIN_ID_RE.sub(" ", body)
            # 正文里光写题号（"T2 在 Δ=4>0 时……"）同样是引用，不是内容。
            cited = [t for t in high_signal_tokens(body)
                     if t.upper() not in {cid.upper() for cid in case_index}]
            haystack = norm(" ".join(str(target.get(k, "")) for k in
                                     ("problem", "student_solution"))) + \
                norm(str((target.get("cause") or {}).get("summary", "")))
            if cited and not any(norm(t) in haystack for t in cited):
                errors.append({"code": "E_EVIDENCE_UNSUPPORTED", "index": index, "case": case_id,
                               "tokens": cited[:8],
                               "detail": "证据里的关键词在该题原文与同伴结论里都找不到"})
            if target.get("_cause_ok") and item.get("cause_type") is not None:
                claimed = CAUSE_TYPE_SYNONYMS.get(item.get("cause_type"), item.get("cause_type"))
                if claimed in CAUSE_TYPES and target.get("_cause_type") != claimed:
                    errors.append({"code": "E_CAUSE_TYPE_MISMATCH", "index": index, "case": case_id,
                                   "claimed": claimed, "actual": target.get("_cause_type"),
                                   "detail": "cause_type 与该题同伴结论不一致：引用要忠实原结论"})
            if target.get("_cause_type"):
                cause_types_used.append(target["_cause_type"])

            count = item.get("case_count")
            if isinstance(count, int) and not isinstance(count, bool):
                # 证据必须自己证明样本量：`evidence` 里点名了几道不同的题，
                # 就最多只能声明几道。一题一句话不算跨题证据。
                referenced = [cid for cid in case_index if cid in evidence]
                if count > len(referenced):
                    errors.append({"code": "E_CASE_COUNT_MISMATCH", "index": index,
                                   "case_count": count, "cited": referenced,
                                   "detail": "声明的样本量大于证据里实际点名的题数；"
                                             "跨题证据要在 evidence 里把题号都写出来"})

    if len(cause_types_used) >= PATTERN_COUNT and len(set(cause_types_used)) == 1:
        warnings.append({"code": "W_ALL_SAME_CAUSE", "cause_type": cause_types_used[0],
                         "detail": "三条模式的判断尺度全同，可疑"})

    common = card.get("cross_case_commonality")
    if isinstance(common, str):
        has_pattern_word = any(name in common or kw in common
                               for name, spec in PATTERNS.items()
                               for kw in (name,) + spec["keywords"])
        if not has_pattern_word:
            warnings.append({"code": "W_COMMONALITY_WEAK", "text": common,
                             "detail": "只点到题号、没点到任何聚合维度关键词"})

    # 引文门 + 越界门（只扫第一段文本）
    texts = first_segment_texts(card)
    for field, text in texts:
        for pattern in NEW_CAUSE_PATTERNS:
            if pattern.search(text):
                errors.append({"code": "A_NEW_CAUSE", "field": field, "text": text,
                               "detail": "自产错因：错因只能引用同伴结论"})
                break
        for pattern in OVERRIDE_PATTERNS:
            if pattern.search(text):
                errors.append({"code": "A_OVERRIDE", "field": field, "text": text,
                               "detail": "否定同伴结论"})
                break
        for pattern in STABLE_JUDGMENT_PATTERNS:
            if pattern.search(text):
                errors.append({"code": "A_STABLE_JUDGMENT", "field": field, "text": text,
                               "detail": "稳定能力判定措辞：跨题归因只能下统计假设"})
                break
        for pattern in VERDICT_PATTERNS:
            if pattern.search(text):
                errors.append({"code": "A_SINGLE_CASE_CAUSE", "field": field, "text": text,
                               "detail": "单题判错/诊断是同伴的活"})
                break
        for marker in SOLVE_MARKERS:
            if marker in text:
                errors.append({"code": "A_SOLVE", "field": field, "text": text,
                               "detail": "出现完整解法/答案措辞：%s" % marker})
                break
        for pattern in VARIANT_PATTERNS:
            if pattern.search(text):
                errors.append({"code": "A_VARIANT", "field": field, "text": text,
                               "detail": "归因字段里夹带题目：练习只能放进 practice_items"})
                break
        for pattern in PLAN_PATTERNS:
            if pattern.search(text):
                errors.append({"code": "A_PLAN", "field": field, "text": text,
                               "detail": "排复习计划（训练动作应是一次能做完的动作）"})
                break
        for pattern in SCORE_PATTERNS:
            if pattern.search(text):
                errors.append({"code": "A_SCORE", "field": field, "text": text, "detail": "给评分"})
                break
        for pattern in CONFIDENCE_PATTERNS:
            if pattern.search(text):
                errors.append({"code": "A_CONFIDENCE", "field": field, "text": text,
                               "detail": "报置信度"})
                break
        for pattern in PROBE_PATTERNS:
            if pattern.search(text):
                errors.append({"code": "A_PROBE", "field": field, "text": text,
                               "detail": "探测理解深度"})
                break
        for pattern in LANGUAGE_PATTERNS:
            if pattern.search(text):
                warnings.append({"code": "W_LANGUAGE", "field": field, "text": text,
                                 "detail": "语气对人不对事"})
                break

    passed = not errors and not (args.strict and warnings)
    emit({
        "action": "audit",
        "input": {"card": args.card, "cases": args.cases, "strict": args.strict},
        "method": "证据门（题号/内容指纹/原文支持/样本量/同伴结论状态）+ "
                  "引文门（自产错因/否定同伴/稳定判定/单题诊断）+ 越界门",
        "cases_seen": sorted(case_index),
        "cases_touched": sorted(touched_cases),
        "errors": errors,
        "warnings": warnings,
        "passed": passed,
        "capability_note": "证据门是关键词匹配且忽略个位数字；case_count 与 cause.method 都是"
                           "声明值，脚本查不出声明是否为真。",
    }, 0 if passed else 1)


# ---------------------------------------------------------------- 答案核验

LINEAR_DECL_RE = re.compile(r"([a-zA-Z])\s*(>=|<=|>|<)\s*(-?\d+(?:/\d+)?)")
MEMBER_DECL_RE = re.compile(r"([a-zA-Z])\s*[∈∉]\s*([A-Za-z])")
MULTI_UNKNOWN_RE = re.compile(r"([a-zA-Z])\s*\^")
EQ_SPLIT_RE = re.compile(r"[，,。；;]|且|其中")
TOKEN_SPLIT_RE = re.compile(r"(?=[+-])")

# 形如 "2x+3y=12" / "3(x-1)=2x+5" / "x/2 - 1 = 3" 的方程项
TERM_RE = re.compile(
    r"^\s*([+-]?\s*\d*(?:\.\d+)?\s*\*?\s*[a-zA-Z]?(?:\s*/\s*\d+)?)"
    r"(?:\s*([+-])\s*(\d*(?:\.\d+)?\s*\*?\s*[a-zA-Z]?(?:\s*/\s*\d+)?))?\s*$")


def _to_fraction(text):
    text = text.strip().replace(" ", "")
    if not text:
        return None
    if "/" in text and re.match(r"^-?\d+/\d+$", text):
        numerator, denominator = text.split("/")
        if int(denominator) == 0:
            return None
        return Fraction(int(numerator), int(denominator))
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None


def normalize_equation(text):
    """剥掉题干里的指令前缀，便于解析。

    只处理"箭头/冒号之前的纯文字指令"（解方程、解方程组、已知、若……），
    不碰数字与符号；剥不掉就原样返回，交给解析器判"不可判定"。
    """
    text = text.strip()
    match = re.match(r"^[^=]*?[：:、\u3001]\s*", text)
    if match:
        head = match.group(0)
        if not re.search(r"[0-9a-zA-Z]", head):
            text = text[match.end():].strip()
    return text


def parse_linear_equation(text):
    """把一条方程解析成 ({变量: 系数}, 常数项)，使得 Σ 系数·变量 = 常数项。

    只接受一元/二元一次式。采用**前缀校验式分词**：先切出各项，
    再确认拼回去与原文一致——不一致就放弃（返回 None，即"跳过，不假装验过"）。
    含变量平方、乘积、函数调用、括号展开等一律放弃。
    """
    text = normalize_equation(text)
    if not text or text.count("=") != 1:
        return None
    if MULTI_UNKNOWN_RE.search(text) or "sqrt" in text or "sin" in text or "(" in text:
        return None
    left, right = text.split("=")
    coefficients, constant = {}, Fraction(0)
    variable_re = re.compile(r"^\d+\s*/\s*\d+$|^\d+(?:\.\d+)?$")

    def feed(side, sign):
        nonlocal constant
        side = side.replace(" ", "")
        if not side:
            return False
        # 注意：零宽前瞻不能用 findall（对 (?=[+-]) 会返回一堆空串），
        # 也不能用 str.split（"a+b".split("+") 丢掉分隔符）。用 re.split 保留符号。
        parts = TOKEN_SPLIT_RE.split(side)
        if parts and parts[0] == "":
            parts = parts[1:]
        if not parts or "".join(parts) != side:
            return False  # 分词拼不回原文 → 不可判定
        for part in parts:
            term_sign = sign
            if part[0] in "+-":
                if part[0] == "-":
                    term_sign = -sign
                part = part[1:]
            if not part:
                return False
            match = re.match(r"^(\d+(?:\.\d+)?|[a-zA-Z]|[a-zA-Z]/\d+|\d+\s*/\s*\d+)\s*\*?\s*([a-zA-Z])$", part)
            if match:
                factor, var = match.group(1), match.group(2)
                if factor == var:
                    value = Fraction(1)          # "xx" 不是一次项，放过
                elif factor.isalpha():
                    value = Fraction(1)          # "ax"
                else:
                    value = _to_fraction(factor.replace(" ", ""))
                    if variable_re.match(factor.replace(" ", "")) is None:
                        return False
                if value is None:
                    return False
                coefficients[var] = coefficients.get(var, Fraction(0)) + term_sign * value
                continue
            if variable_re.match(part):
                value = _to_fraction(part)
                if value is None:
                    return False
                constant += -term_sign * value
                continue
            return False
        return True

    if not feed(left, Fraction(1)):
        return None
    if not feed(right, Fraction(-1)):
        return None
    if not coefficients:
        return None
    return coefficients, constant


def solve_linear_system(equations):
    """精确有理数高斯消元。返回 (变量顺序, 解字典) 或 None（欠定 / 矛盾 / 解析失败）。"""
    variables = sorted({var for coefficients, _ in equations for var in coefficients})
    if not variables or len(variables) > 2:
        return None
    rows = []
    for coefficients, constant in equations:
        rows.append([coefficients.get(var, Fraction(0)) for var in variables] + [constant])
    pivot_row = 0
    for column in range(len(variables)):
        pivot = None
        for row in range(pivot_row, len(rows)):
            if rows[row][column] != 0:
                pivot = row
                break
        if pivot is None:
            continue
        rows[pivot_row], rows[pivot] = rows[pivot], rows[pivot_row]
        factor = rows[pivot_row][column]
        rows[pivot_row] = [value / factor for value in rows[pivot_row]]
        for row in range(len(rows)):
            if row != pivot_row and rows[row][column] != 0:
                multiplier = rows[row][column]
                rows[row] = [a - multiplier * b for a, b in zip(rows[row], rows[pivot_row])]
        pivot_row += 1
    for row in rows:
        if all(value == 0 for value in row[:-1]) and row[-1] != 0:
            return None  # 矛盾
    if pivot_row < len(variables):
        return None  # 欠定：自由变量，无法唯一核验
    solution = {}
    for index, var in enumerate(variables):
        if rows[index][index] == 0:
            return None
        solution[var] = rows[index][-1]
    return variables, solution


def parse_answer_values(answer, variables):
    """从答案文本里把变量取值抠出来：支持 x=2、x₁=2 与 "-2, 3" 这类并列值。"""
    values = {}
    pattern = re.compile(r"([a-zA-Z])[₁₂₃₁-₉\d]*\s*=\s*(-?\d+(?:\s*/\s*\d+)?)")
    for match in pattern.finditer(answer):
        value = _to_fraction(match.group(2))
        if value is not None:
            values[match.group(1)] = value
    if values:
        return values
    bare = re.findall(r"-?\d+(?:\s*/\s*\d+)?", answer)
    parsed = [v for v in (_to_fraction(x) for x in bare) if v is not None]
    if len(variables) == 1 and len(parsed) == 4:
        pass
    if len(variables) == 1 and parsed:
        return {variables[0]: parsed[0]}
    if len(variables) == 2 and len(parsed) >= 2:
        # 无变量名时按题面变量顺序配（不可靠 → 交给调用方只做弱判定）
        return dict(zip(variables, parsed[:2]))
    return values


def _render_equation(equation):
    """把 ({'x': Fraction(2)}, Fraction(4)) 还原成可读的 "2x=4"。"""
    coefficients, constant = equation
    left = []
    for var in sorted(coefficients):
        value = coefficients[var]
        left.append("%s%s" % ("" if abs(value) == 1 else str(value), var))
    return "%s=%s" % ("+".join(left).replace("+-", "-"), constant)


def verify_answers(card):
    """对每道练习题做可判定范围内的答案核验。返回 (findings, skipped)。"""
    findings, skipped = [], []
    items = card.get("practice_items")
    if not isinstance(items, list):
        return findings, skipped
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id", "?")
        prompt = item.get("student_prompt")
        answer = item.get("answer")
        steps = item.get("solution_steps")
        if not isinstance(prompt, str) or not isinstance(answer, str):
            continue
        if not answer.strip() or not isinstance(steps, str) or not steps.strip():
            findings.append({"code": "E_ANSWER_MISSING", "id": item_id,
                             "detail": "answer 或 solution_steps 为空"})
            continue

        if norm(answer) and norm(answer) in norm(prompt):
            findings.append({"code": "E_ANSWER_IN_PROMPT", "id": item_id, "answer": answer,
                             "detail": "答案的实质内容出现在学生可见题干里（泄漏）"})

        answer_tokens = set(high_signal_tokens(answer))
        prompt_tokens = set(high_signal_tokens(prompt))
        if answer_tokens and prompt_tokens and not (answer_tokens & prompt_tokens):
            findings.append({"code": "E_ANSWER_UNRELATED", "id": item_id,
                             "answer_tokens": sorted(answer_tokens)[:6],
                             "detail": "答案与题干没有任何共享数字或符号，疑似对不上"})

        # 声明域：题干里的 x>0 之类
        domain = {}
        for match in LINEAR_DECL_RE.finditer(prompt):
            var, operator, value = match.group(1), match.group(2), match.group(3)
            domain.setdefault(var, []).append((operator, _to_fraction(value)))

        # 整数集/实数集一类成员约束：线性求解器不处理，明确跳过而不是硬算
        membership = {}
        for match in MEMBER_DECL_RE.finditer(prompt):
            membership[match.group(1)] = match.group(2)

        cleaned = MEMBER_DECL_RE.sub(" ", prompt)
        segments = [s for s in EQ_SPLIT_RE.split(cleaned)
                    if "=" in s and not s.strip().startswith("求")]
        # 注意：某一条解析不了时不能立刻 break——多方程题干里后面的方程
        # 还要用来判定"整体是否可解析"，一 break 就会把完整方程组误判成 skipped。
        equations = []
        for segment in segments:
            equation = segment.strip()
            if "求" in equation:
                equation = equation.split("求")[0].strip()
            equations.append(parse_linear_equation(equation))
        if not equations or any(e is None for e in equations):
            skipped.append({"id": item_id, "reason": "题干不是可解析的一元/二元一次方程（组）",
                            "status": "skipped"})
            continue

        solved = solve_linear_system(equations)
        if solved is None:
            skipped.append({"id": item_id, "reason": "方程组欠定/矛盾或超出可判定范围",
                            "status": "skipped"})
            continue
        variables, solution = solved

        if any(var in membership for var in variables):
            skipped.append({"id": item_id, "reason": "答案受集合成员约束（如 x∈Z），"
                                                     "本门不处理，需人工核验", "status": "skipped"})
            continue

        claimed = parse_answer_values(answer, variables)

        if not claimed:
            skipped.append({"id": item_id, "reason": "无法从答案文本解析出变量取值",
                            "status": "skipped"})
            continue

        # 先判取值域，再判方程：答案跑到定义域外是更具体、更有教学意义的失败，
        # 不能因为"顺带也不满足方程"就被 E_ANSWER_LINEAR_UNSAT 顶掉。
        violated = []
        for var, value in claimed.items():
            for operator, bound in domain.get(var, []):
                if bound is None:
                    continue
                ok = {"<": value < bound, "<=": value <= bound,
                      ">": value > bound, ">=": value >= bound}[operator]
                if not ok:
                    violated.append("%s %s %s（答案 %s）" % (var, operator, bound, value))
        if violated:
            findings.append({"code": "E_ANSWER_DOMAIN_VIOLATION", "id": item_id,
                             "violations": violated,
                             "detail": "答案落在题干声明的取值范围之外"})
            continue

        mismatched = {var: (claimed[var], solution[var]) for var in claimed
                      if var in solution and claimed[var] != solution[var]}
        if mismatched:
            findings.append({"code": "E_ANSWER_LINEAR_UNSAT", "id": item_id,
                             "equations": [_render_equation(e) for e in equations],
                             "claimed": {k: str(v) for k, v in claimed.items()},
                             "solved": {k: str(v) for k, v in solution.items()},
                             "detail": "代入答案不成立：本门唯一真算一次的地方"})
            continue

        findings.append({"id": item_id, "status": "verified",
                         "solved": {k: str(v) for k, v in solution.items()},
                         "note": "精确有理数代回成立（工具辅助核验，非独立验证）"})
    return findings, skipped


# ---------------------------------------------------------------- practice

def cmd_practice(args):
    card = load_card(args.card)
    errors, warnings = [], []

    authorized = card.get("practice_authorized")
    items = card.get("practice_items")
    if not isinstance(authorized, bool):
        errors.append({"code": "E_PRACTICE_UNAUTHORIZED", "got": authorized,
                       "detail": "practice_authorized 必须是布尔值"})
        authorized = False
    if isinstance(items, list) and items and not authorized:
        errors.append({"code": "E_PRACTICE_UNAUTHORIZED", "count": len(items),
                       "detail": "用户没有明确请求出题，practice_items 必须为空数组"})
    if authorized and (not isinstance(items, list) or not items):
        errors.append({"code": "E_PRACTICE_MISSING",
                       "detail": "标记为已授权，但 practice_items 为空：用户要了却没出题"})

    basis = card.get("generation_basis")
    if isinstance(basis, str):
        pattern_hits = [name for name in PATTERNS if name in basis]
        # 中文写作里题号常常直接写成"第 T1、T3 题"，不套方括号，两种都要认
        basis_ids = {m.group(0) for m in CASE_ID_LIKE_RE.finditer(basis)}
        if not (pattern_hits and len(basis_ids) >= MIN_CASE_COUNT):
            warnings.append({"code": "W_NO_GENERATION_BASIS", "basis": basis,
                             "patterns": pattern_hits, "case_ids": sorted(basis_ids),
                             "detail": "出题依据应点名至少一个聚合维度与至少两个题号"})
    elif authorized:
        warnings.append({"code": "W_NO_GENERATION_BASIS",
                         "detail": "缺少 generation_basis"})

    referable = referable_patterns(card)
    if isinstance(items, list) and items:
        if len(items) != PRACTICE_COUNT:
            errors.append({"code": "E_PRACTICE_COUNT", "count": len(items),
                           "detail": "必须恰好 %d 道题" % PRACTICE_COUNT})
        covered, difficulties, prompts = set(), set(), {}
        for position, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                errors.append({"code": "E_PRACTICE_ITEM_FIELDS", "index": position,
                               "detail": "每道题必须是 JSON 对象"})
                continue
            extra = [f for f in item if f not in PRACTICE_FIELDS]
            missing = [f for f in PRACTICE_FIELDS if f not in item]
            if extra or missing:
                errors.append({"code": "E_PRACTICE_ITEM_FIELDS", "index": position,
                               "missing": missing, "extra": extra,
                               "detail": "每道题必须恰好 %d 个字段" % len(PRACTICE_FIELDS)})
            ref = item.get("pattern_ref")
            if isinstance(ref, bool) or not isinstance(ref, int):
                errors.append({"code": "E_PRACTICE_ITEM_FIELDS", "index": position,
                               "field": "pattern_ref", "detail": "pattern_ref 必须是整数"})
            else:
                if not 1 <= ref <= PATTERN_COUNT:
                    errors.append({"code": "E_PATTERN_REF_RANGE", "index": position,
                                   "pattern_ref": ref,
                                   "detail": "pattern_ref 必须是 1..%d 的序号" % PATTERN_COUNT})
                elif ref not in referable:
                    errors.append({"code": "E_PATTERN_REF_THIN", "index": position,
                                   "pattern_ref": ref,
                                   "detail": "该模式 case_count < %d：一道题错的模式不准用来出题"
                                             % MIN_CASE_COUNT})
                else:
                    covered.add(ref)
            difficulty = item.get("difficulty")
            if difficulty not in DIFFICULTIES:
                errors.append({"code": "E_DIFFICULTY_UNKNOWN", "index": position,
                               "difficulty": difficulty,
                               "detail": "difficulty 只能取：" + " / ".join(DIFFICULTIES)})
            else:
                difficulties.add(difficulty)
            source = item.get("source_pattern")
            if isinstance(ref, int) and not isinstance(ref, bool) and 1 <= ref <= PATTERN_COUNT:
                patterns = card.get("error_patterns")
                if isinstance(patterns, list) and len(patterns) >= ref:
                    expected = patterns[ref - 1].get("pattern") if \
                        isinstance(patterns[ref - 1], dict) else None
                    if isinstance(source, str) and isinstance(expected, str) and \
                            source.strip() != expected.strip():
                        errors.append({"code": "E_SOURCE_MISMATCH", "index": position,
                                       "source_pattern": source, "expected": expected,
                                       "detail": "source_pattern 必须与 pattern_ref 对应的模式一致"})
            prompt = item.get("student_prompt")
            if isinstance(prompt, str):
                key = norm(prompt)
                if key in prompts:
                    errors.append({"code": "E_PRACTICE_DUP", "index": position,
                                   "duplicate_of": prompts[key],
                                   "detail": "与第 %d 题重复" % prompts[key]})
                else:
                    prompts[key] = position
        if len(prompts) and len(prompts) < PRACTICE_COUNT and \
                not any(e["code"] == "E_PRACTICE_DUP" for e in errors):
            errors.append({"code": "E_PRACTICE_DUP", "unique": len(prompts),
                           "detail": "去重后不足 %d 道题" % PRACTICE_COUNT})
        if len(difficulties) < len(DIFFICULTIES):
            missing = [d for d in DIFFICULTIES if d not in difficulties]
            errors.append({"code": "E_DIFFICULTY_UNKNOWN", "missing": missing,
                           "detail": "三档难度必须全部出现"})
        for ref in referable:
            if ref not in covered:
                errors.append({"code": "E_PATTERN_UNCOVERED", "pattern_ref": ref,
                               "pattern": referable[ref],
                               "detail": "该模式一道题都没覆盖：三块短板漏一块等于没做个性化"})
    elif authorized:
        errors.append({"code": "E_PRACTICE_MISSING", "detail": "已授权但没有可用的题目"})

    quality, skipped = [], []
    if args.verify_answers:
        quality, skipped = verify_answers(card)
        for finding in quality:
            if finding.get("status") == "verified":
                continue
            if finding["code"] in ("E_ANSWER_MISSING", "E_ANSWER_IN_PROMPT",
                                   "E_ANSWER_UNRELATED", "E_ANSWER_LINEAR_UNSAT",
                                   "E_ANSWER_DOMAIN_VIOLATION"):
                errors.append(finding)
        if args.verify_answers:
            quality, skipped = verify_answers(card)
            for finding in quality:
                if finding.get("status") == "verified":
                    continue
                if finding["code"] in ("E_ANSWER_MISSING", "E_ANSWER_IN_PROMPT",
                                       "E_ANSWER_UNRELATED", "E_ANSWER_LINEAR_UNSAT",
                                       "E_ANSWER_DOMAIN_VIOLATION"):
                    errors.append(finding)
        # 这里不拿"缺 solution_steps"当数值题的判据——那会和 E_ANSWER_MISSING 打架，
        # 同一个事实报两次。只统计"答案是个光秃秃的数、且步骤里也没有数字支撑"的题。
        numeric_only = 0
        items_list = card.get("practice_items")
        if isinstance(items_list, list) and items_list:
            for item in items_list:
                if not isinstance(item, dict):
                    continue
                answer = item.get("answer")
                steps = item.get("solution_steps")
                if not isinstance(answer, str) or not NUMERIC_ONLY_ANSWER.match(answer):
                    continue
                if isinstance(steps, str) and NUM_RE.search(steps):
                    continue  # 步骤里有算式，不算"只有数值"
                numeric_only += 1
            if numeric_only * 2 > len(items_list):
                warnings.append({"code": "W_ANSWER_NUMERIC_ONLY", "count": numeric_only,
                                 "detail": "过半题目只有数值答案、无解法支撑"})
        for entry in skipped:
            warnings.append({"code": "W_NO_SOLUTION_BASIS", "id": entry["id"],
                             "reason": entry["reason"], "status": "skipped",
                             "detail": "超出可判定范围，明确跳过——不假装验过"})

    passed = not errors and not (args.strict and warnings)
    payload = {
        "action": "practice",
        "input": {"card": args.card, "verify_answers": args.verify_answers,
                  "strict": args.strict},
        "method": "授权门 + 绑定门（pattern_ref / 样本量 / 覆盖 / 难度三档 / 去重）"
                  + ("+ 答案核验门（精确有理数代回）" if args.verify_answers else ""),
        "referable_patterns": {str(k): v for k, v in referable.items()},
        "errors": errors,
        "warnings": warnings,
        "passed": passed,
        "capability_note": "答案核验只覆盖可解析为一元/二元一次方程（组）的题；其余一律 skipped。"
                           "出题器与验证器同源，这是工具辅助核验，不是独立验证。",
    }
    if args.verify_answers:
        payload["answer_verification"] = {
            "checked": [f for f in quality if f.get("status") == "verified"],
            "problems": [f for f in quality if f.get("status") != "verified"],
            "skipped": skipped,
        }
    emit(payload, 0 if passed else 1)


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(
        description="Three gates for an error-atlas pathology card.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_patterns = sub.add_parser("patterns", help="print both vocabularies + topic hints")
    p_patterns.add_argument("--problem", required=True, help="the problem text")
    p_patterns.set_defaults(func=cmd_patterns)

    p_validate = sub.add_parser("validate", help="structural gate")
    p_validate.add_argument("--card", required=True, help="path to the card JSON file")
    p_validate.set_defaults(func=cmd_validate)

    p_audit = sub.add_parser("audit", help="evidence + citation + boundary gates")
    p_audit.add_argument("--card", required=True)
    p_audit.add_argument("--cases", required=True,
                         help="path to the cases JSON file (each case carries a peer cause)")
    p_audit.add_argument("--strict", action="store_true", help="treat warnings as failures")
    p_audit.set_defaults(func=cmd_audit)

    p_practice = sub.add_parser("practice", help="practice authorization + binding + answer check")
    p_practice.add_argument("--card", required=True)
    p_practice.add_argument("--verify-answers", action="store_true",
                            help="run exact rational back-substitution where parseable")
    p_practice.add_argument("--strict", action="store_true", help="treat warnings as failures")
    p_practice.set_defaults(func=cmd_practice)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
