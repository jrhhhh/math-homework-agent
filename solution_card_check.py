#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""solution_card_check.py — "正解优化卡"的结构门与越界审计。

用法：
  validate --card CARD.json
  audit    --card CARD.json --solution "学生解答" [--problem "题目文本"] [--strict]
  hint     --solution "学生解答" [--problem "题目文本"]

约定：
  - 所有结果以 JSON 打到 stdout；
  - 退出码：0 = 通过 / 干净；1 = 未通过（有 error，或 --strict 下出现 warning）；2 = 输入非法。
  - 仅使用 Python 标准库，无第三方依赖。

能力边界（诚实声明，别把它当正确性证明）：
  - 结构门只查"卡片长得对不对"：字段是否齐、方向是否恰好 3 条、方向是否在白名单内、
    短板标签与方向是否搭。**它不判断优化建议在数学上是否真的更优**——那要人来读。
  - 越界审计靠措辞规则：抓"判对错 / 诊断错因 / 出变式题 / 排复习计划 / 报置信度 / 探测理解深度"。
    它是便宜的确定性门，不是语义理解；换个说法绕过去，它抓不住。
  - "修复句"与"优化建议"在措辞上本来就难分（"把求根公式改为因式分解"两边都算），
    所以本门不单独抓修复句——但修复句的前提是判错，A_JUDGE / A_CAUSE 会把那个前提抓住。
  - W_GAP_MISMATCH 只是关键词匹配的告警，措辞换一种说法就可能误报，请人工过一眼。
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

TEXT_FIELDS = ("current_method", "overall_diagnosis", "next_step")
LIST_FIELD = "optimization_opportunities"
OPP_FIELDS = ("direction", "suggestion", "exposed_gap", "training_suggestion")
REQUIRED_FIELDS = TEXT_FIELDS + (LIST_FIELD,)
OPP_COUNT = 3

# 七类优化方向 → (对应短板标签, gap 文本里通常会出现的关键词, 典型表现)
GAP_TABLE = (
    ("更优方法", "方法选择能力弱",
     ("方法选择", "选择方法", "选方法", "方法比较", "比较方法", "工具"),
     "只会一种方法，不会比较"),
    ("更短步骤", "代数变形能力弱",
     ("代数变形", "变形", "化简", "步骤"),
     "计算冗长，不会化简"),
    ("更通用解法", "抽象推广能力弱",
     ("抽象推广", "推广", "一般化", "通法"),
     "只会特例，不会一般化"),
    ("更优雅表达", "数学语言能力弱",
     ("数学语言", "表达", "书写", "记法"),
     "步骤对但写得乱"),
    ("更少分类讨论", "逻辑结构能力弱",
     ("逻辑结构", "分类讨论", "结构", "合并"),
     "分类繁琐，不会合并"),
    ("更快计算", "数感 / 估算能力弱",
     ("数感", "估算", "计算速度", "口算", "算得慢"),
     "硬算，不会估算"),
    ("更几何直观", "数形结合能力弱",
     ("数形结合", "画图", "图象", "图像", "草图", "数轴", "直观"),
     "只会代数，不会画图"),
)

DIRECTIONS = {row[0]: row[2] for row in GAP_TABLE}
GAP_LABEL = {row[0]: row[1] for row in GAP_TABLE}
TYPICAL = {row[0]: row[3] for row in GAP_TABLE}
DIRECTION_ALIASES = {
    "更通用视角": "更通用解法",
    "更优解法": "更优方法",
    "更快运算": "更快计算",
    "更简洁表达": "更优雅表达",
}
CORE_DIRECTIONS = frozenset({"更优方法", "更短步骤", "更通用解法"})

PUNCT_RE = re.compile(r"[\s　，。？！、；：,.?!;:'\"“”‘’（）()【】\[\]]+")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
IDENT_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,7}")

# 越界措辞：命中即说明卡片跑到了别的 skill 的疆域
OUT_OF_SCOPE = (
    ("A_JUDGE", "判对错 / 否定原解法",
     re.compile(r"错了|不正确|不对的|是错误的|答案是错的|方法有误|解法有误|思路有误|有误")),
    ("A_CAUSE", "诊断错因",
     re.compile(r"错因|错误的原因|出错的原因|错误的根源|根本原因|之所以.{0,12}错")),
    ("A_VARIANT", "出变式题",
     re.compile(r"变式|再来一[道题]|下一道题|下面这道题|再试一题")),
    ("A_PLAN", "排复习计划",
     re.compile(r"复习计划|学习计划|复习安排|错题本|计划表|每周|每天|每日|一周|一个月|打卡")),
    ("A_CONFIDENCE", "报置信度",
     re.compile(r"置信度|confidence|可信度")),
    ("A_PROBE", "探测理解深度",
     re.compile(r"理解深度|你是怎么想的|你是怎么理解|为什么这样想|解释一下你的思路|说说你的思路")),
)

# 方法线索表（只作提示，不构成判断）
METHOD_CUES = (
    {"method": "求根公式法", "keywords": ("求根公式", "判别式", "-b±", "b²-4ac")},
    {"method": "因式分解法", "keywords": ("因式分解", "十字相乘", "分解因式", "提公因式")},
    {"method": "配方法", "keywords": ("配方", "完全平方")},
    {"method": "韦达定理", "keywords": ("韦达", "两根之和", "根与系数")},
    {"method": "代入消元法", "keywords": ("代入",)},
    {"method": "加减消元法", "keywords": ("加减消元", "加减法", "消元")},
    {"method": "竖式笔算", "keywords": ("竖式", "笔算")},
    {"method": "拆分凑整 / 乘法结合律", "keywords": ("结合律", "拆成", "拆分", "凑整")},
    # 导数记号与字母无关（y'、g'(x) 都算），所以除关键词外再配一条正则
    {"method": "导数法", "keywords": ("求导", "导数"),
     "regex": r"[a-z]\s*['’′]", "regex_label": "导数记号（字母加撇）"},
    {"method": "标准分部积分", "keywords": ("分部积分", "udv", "∫udv")},
    {"method": "表格法", "keywords": ("表格法", "列表法", "tabular")},
    {"method": "换元法", "keywords": ("换元", "令 t", "令 u", "令t=")},
    {"method": "作图 / 数形结合", "keywords": ("画图", "图象", "图像", "作图", "数轴", "草图")},
    {"method": "分类讨论", "keywords": ("分类讨论", "分情况")},
)

STOP_TOKENS = frozenset({"已知", "求其", "下列", "的是", "一个", "以及", "其中", "如何", "什么"})


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
    except OSError as exc:
        emit({"error": "cannot read card file", "path": path, "detail": str(exc)}, 2)
    if not isinstance(card, dict):
        emit({"error": "card must be a JSON object", "path": path,
              "got": type(card).__name__}, 2)
    return card


def card_texts(card):
    """把卡片里所有文字摊平成 [(字段名, 文本)]，便于逐条扫描。"""
    out = []
    for field in TEXT_FIELDS:
        value = card.get(field)
        if isinstance(value, str):
            out.append((field, value))
    opportunities = card.get(LIST_FIELD)
    if isinstance(opportunities, list):
        for index, opp in enumerate(opportunities, start=1):
            if not isinstance(opp, dict):
                continue
            for field in OPP_FIELDS:
                value = opp.get(field)
                if isinstance(value, str):
                    out.append(("%s[%d].%s" % (LIST_FIELD, index, field), value))
    return out


def text_tokens(text):
    """文本里的高信号线索：多位数字与 ASCII 标识符（f、x、n、a_n 之类）。

    个位数字被刻意排除：它几乎必然作为子串撞上卡片里的任何数字（"2" 命中 "25"），
    留着只会让关联度检查永远通过。代价是短数字解法会跳过这项检查。
    """
    numbers = [n for n in NUM_RE.findall(text) if len(n.replace(".", "")) >= 2]
    tokens = numbers + IDENT_RE.findall(text)
    seen, out = set(), []
    for token in tokens:
        if token in STOP_TOKENS or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


# ---------------------------------------------------------------- validate

def cmd_validate(args):
    card = load_card(args.card)
    errors, warnings = [], []

    for field in REQUIRED_FIELDS:
        if field not in card:
            errors.append({"code": "E_MISSING_FIELD", "field": field,
                           "detail": "缺少必需字段"})

    for field in TEXT_FIELDS:
        if field in card:
            value = card[field]
            if not isinstance(value, str) or not value.strip():
                errors.append({"code": "E_EMPTY_TEXT", "field": field,
                               "detail": "必须是非空字符串"})

    opportunities = card.get(LIST_FIELD)
    if LIST_FIELD in card:
        if not isinstance(opportunities, list):
            errors.append({"code": "E_BAD_LIST", "field": LIST_FIELD,
                           "detail": "必须是数组，数组里每条是一个优化方向"})
            opportunities = None
        elif len(opportunities) != OPP_COUNT:
            errors.append({"code": "E_OPP_COUNT", "count": len(opportunities),
                           "detail": "优化方向必须恰好 %d 条，实为 %d 条"
                                     % (OPP_COUNT, len(opportunities))})

    if isinstance(opportunities, list):
        seen, core_hits = {}, 0
        for index, opp in enumerate(opportunities, start=1):
            tag = "%s[%d]" % (LIST_FIELD, index)
            if not isinstance(opp, dict):
                errors.append({"code": "E_BAD_OPP", "field": tag,
                               "detail": "每条优化方向必须是 JSON 对象"})
                continue

            for field in OPP_FIELDS:
                if field not in opp:
                    errors.append({"code": "E_MISSING_FIELD",
                                   "field": "%s.%s" % (tag, field),
                                   "detail": "缺少必需字段"})
                elif not isinstance(opp[field], str) or not opp[field].strip():
                    errors.append({"code": "E_EMPTY_TEXT",
                                   "field": "%s.%s" % (tag, field),
                                   "detail": "必须是非空字符串"})
            for field in opp:
                if field not in OPP_FIELDS:
                    warnings.append({"code": "W_EXTRA_FIELD",
                                     "field": "%s.%s" % (tag, field),
                                     "detail": "非标准字段，建议删除"})

            direction = opp.get("direction")
            if isinstance(direction, str) and direction.strip():
                canonical = DIRECTION_ALIASES.get(direction.strip(), direction.strip())
                if canonical not in DIRECTIONS:
                    errors.append({"code": "E_BAD_DIRECTION",
                                   "field": "%s.direction" % tag, "text": direction,
                                   "detail": "方向必须取自白名单七类之一",
                                   "allowed": list(DIRECTIONS)})
                else:
                    if canonical in seen:
                        errors.append({"code": "E_DUPLICATE_DIRECTION",
                                       "field": "%s.direction" % tag, "text": direction,
                                       "detail": "与第 %d 条方向重复" % seen[canonical]})
                    else:
                        seen[canonical] = index
                    if canonical in CORE_DIRECTIONS:
                        core_hits += 1

                    gap = opp.get("exposed_gap")
                    if isinstance(gap, str) and gap.strip():
                        if not any(kw in gap for kw in DIRECTIONS[canonical]):
                            warnings.append({
                                "code": "W_GAP_MISMATCH",
                                "field": "%s.exposed_gap" % tag, "text": gap,
                                "detail": "短板描述与方向「%s」不搭；该方向通常对应「%s」"
                                          % (canonical, GAP_LABEL[canonical])})

            suggestion = opp.get("suggestion")
            if isinstance(suggestion, str) and suggestion.strip() \
                    and len(norm(suggestion)) < 6:
                warnings.append({"code": "W_TOO_SHORT",
                                 "field": "%s.suggestion" % tag, "text": suggestion,
                                 "detail": "建议过短，学生看不出'怎么做才更好'"})

        if opportunities and core_hits == 0 and \
                not any(e["code"] == "E_BAD_DIRECTION" for e in errors):
            warnings.append({"code": "W_DIRECTION_MONOTONY", "field": LIST_FIELD,
                             "detail": "三个方向都没落在核心三路"
                                       "（更优方法 / 更短步骤 / 更通用解法）里"})

    emit({
        "action": "validate",
        "input": {"card": args.card},
        "method": "字段完整性 + 恰好 3 个优化方向 + 方向白名单 + 方向去重 + 短板标签一致性",
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }, 0 if not errors else 1)


# ---------------------------------------------------------------- audit

def cmd_audit(args):
    card = load_card(args.card)
    solution = (args.solution or "").strip()
    if not solution:
        emit({"error": "--solution must be a non-empty string"}, 2)
    problem = (args.problem or "").strip()

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

    # W 组：卡片与学生的实际解法/原题是否脱节
    tokens = text_tokens(solution)
    if len(tokens) >= 3:
        joined = " ".join(norm(text) for _, text in texts)
        if not any(norm(token) in joined for token in tokens):
            warnings.append({"code": "W_DETACHED_SOLUTION", "field": "*",
                             "solution_tokens": tokens[:12],
                             "detail": "卡片没有引用学生解法里的任何数字或符号，可能脱离原解答"})
    if problem:
        problem_tokens = text_tokens(problem)
        if len(problem_tokens) >= 3:
            joined = " ".join(norm(text) for _, text in texts)
            if not any(norm(token) in joined for token in problem_tokens):
                warnings.append({"code": "W_DETACHED_PROBLEM", "field": "*",
                                 "problem_tokens": problem_tokens[:12],
                                 "detail": "卡片没有引用原题里的任何数字或符号，可能脱离原题"})

    passed = not errors and not (args.strict and warnings)
    emit({
        "action": "audit",
        "input": {"card": args.card, "solution": solution,
                  "problem": problem or None, "strict": args.strict},
        "method": "规则扫描：判对错 / 诊断错因 / 变式题 / 复习计划 / 置信度 / 理解深度探测，"
                  "外加与原解答及原题的关联度",
        "errors": errors,
        "warnings": warnings,
        "passed": passed,
        "capability_note": "规则门而非语义理解：passed 只说明卡片没越过这几条线，"
                           "不等于优化建议在数学上真的更优。",
    }, 0 if passed else 1)


# ---------------------------------------------------------------- hint

def cmd_hint(args):
    solution = (args.solution or "").strip()
    if not solution:
        emit({"error": "--solution must be a non-empty string"}, 2)
    problem = (args.problem or "").strip()

    blob = (problem + "\n" + solution).lower()
    detected = []
    for cue in METHOD_CUES:
        hits = [kw for kw in cue["keywords"] if kw.lower() in blob]
        pattern = cue.get("regex")
        if pattern and re.search(pattern, blob):
            hits.append(cue.get("regex_label", "regex-match"))
        if hits:
            detected.append({"method": cue["method"], "matched_keywords": hits})

    emit({
        "action": "hint",
        "input": {"solution": solution, "problem": problem or None},
        "method": "方法关键词表启发式初判（未命中不代表没方法，只代表关键词表没覆盖）",
        "detected_methods": detected,
        "direction_menu": [
            {"direction": row[0], "gap_label": row[1], "typical": row[3]}
            for row in GAP_TABLE
        ],
        "authority": "heuristic-hint-only",
        "capability_note": "关键词命中只是提示，可能误判；必须以读完题目与学生解法后的判断为准，"
                           "不得用本输出替代对解法的理解。解答里没写方法时，直接问学生用的是哪种做法。",
    }, 0)


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(
        description="Validate and audit a correct-solution optimization card.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="structural gate for an optimization card")
    p_validate.add_argument("--card", required=True, help="path to the card JSON file")
    p_validate.set_defaults(func=cmd_validate)

    p_audit = sub.add_parser("audit", help="scan a card for out-of-scope moves and detachment")
    p_audit.add_argument("--card", required=True, help="path to the card JSON file")
    p_audit.add_argument("--solution", required=True, help="the student's correct solution text")
    p_audit.add_argument("--problem", default=None, help="optional original problem text")
    p_audit.add_argument("--strict", action="store_true",
                         help="treat warnings as failures")
    p_audit.set_defaults(func=cmd_audit)

    p_hint = sub.add_parser("hint", help="heuristic method hint for a solution")
    p_hint.add_argument("--solution", required=True, help="the student's solution text")
    p_hint.add_argument("--problem", default=None, help="optional original problem text")
    p_hint.set_defaults(func=cmd_hint)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
