#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""think_card_check.py — "解题前思考卡"的结构门与泄漏审计。

用法：
  validate --card CARD.json
  audit    --card CARD.json --problem "题目文本" [--answer "标准答案"] [--strict]
  classify --problem "题目文本"

约定：
  - 所有结果以 JSON 打到 stdout；
  - 退出码：0 = 通过 / 干净；1 = 未通过（有 error，或 --strict 下出现 warning）；2 = 输入非法。
  - 仅使用 Python 标准库，无第三方依赖。

能力边界（诚实声明，别把它当正确性证明）：
  - "答案泄漏"靠措辞规则、结论性数值等式、以及可选的 --answer 精确匹配来抓。
    它是便宜的确定性门，不是语义理解；"把答案拆成好几步偷偷算出来"这类绕过它抓不住。
  - 本脚本只回答"卡片有没有越过这几条线"，不评价卡片的教学质量。
  - --answer 归一化后短于 2 个字符时只记 warning（例如答案就是 "9"）：
    短串几乎必然误报（会撞上题目里的普通数字），此时请人工过一眼。
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

TEXT_FIELDS = ("question_type", "first_move", "common_trap", "self_check_before_start")
LIST_FIELDS = ("knowledge_needed", "starter_questions")
REQUIRED_FIELDS = TEXT_FIELDS + LIST_FIELDS
STARTER_COUNT = 5

PUNCT_RE = re.compile(r"[\s　，。？！、；：,.?!;:'\"“”‘’（）()【】\[\]]+")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
IDENT_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,7}")

# 显式"给出答案"的措辞。
# 每条都带否定前瞻：中文子串匹配极易误伤疑问句——"检查答案是否合理" 里就藏着
# "答案是"，"运算结果是否正确" 里藏着 "结果是"。这些都不是泄漏，必须放过。
_QUESTIONAL = r"(?![否不]|正确|错误|什么|多少|几|哪|谁|吗|呢|如何)"
ANSWER_PATTERNS = (
    (re.compile(r"答案是" + _QUESTIONAL), "答案是"),
    (re.compile(r"答案为" + _QUESTIONAL), "答案为"),
    (re.compile(r"最终答案" + _QUESTIONAL), "最终答案"),
    (re.compile(r"正确答案" + _QUESTIONAL), "正确答案"),
    (re.compile(r"结果[是为]" + _QUESTIONAL), "结果是 / 结果为"),
    (re.compile(r"最终结果" + _QUESTIONAL), "最终结果"),
    (re.compile(r"答案\s*[：:]" + _QUESTIONAL), "答案："),
    (re.compile(r"answer\s+is" + _QUESTIONAL), "answer is"),
    (re.compile(r"the\s+answer" + _QUESTIONAL), "the answer"),
)

# 完整解法开篇标记：出现即意味着卡片越界，把活替学生干了
SOLUTION_MARKERS = ("证明：", "证明:", "解：", "解:", "综上所述", "综上，", "综上,", "原式=")

# 结论性措辞 + 等号右边是"非平凡纯数字" → 疑似把结果写进卡片
CONCLUSION_RE = re.compile(
    r"(?:所以|因此|故|于是|从而|可得|得到|得出)"
    r"\s*[^。；;=\n]{0,24}?=\s*(-?\d+(?:\.\d+)?)\s*(?=[。．.，,、；;\n]|$)"
)
TRIVIAL_NUMBERS = frozenset({"0", "1", "-1", "0.0", "1.0"})

# 题型启发式关键词表（只作提示，不构成判断）
TOPIC_HINTS = [
    {"name": "函数极值 / 最值", "keywords": ("极值", "最值", "极大", "极小"),
     "knowledge": ("导数", "极值判定", "一元二次方程")},
    {"name": "函数单调性", "keywords": ("单调", "递增", "递减", "增区间", "减区间"),
     "knowledge": ("导数", "导数符号与函数单调性的关系")},
    {"name": "数列", "keywords": ("数列", "等差", "等比", "通项", "前n项和"),
     "knowledge": ("数列通项公式", "等差 / 等比中项", "函数观点看数列")},
    {"name": "三角函数", "keywords": ("三角", "正弦", "余弦", "sin", "cos", "tan"),
     "knowledge": ("诱导公式", "和差角公式", "周期与图象")},
    {"name": "概率与统计", "keywords": ("概率", "分布列", "期望", "方差", "抽样"),
     "knowledge": ("古典概型", "分布列与期望", "独立性与条件概率")},
    {"name": "平面 / 立体几何证明", "keywords": ("证明", "三角形", "圆", "平行", "垂直", "相似", "全等"),
     "knowledge": ("几何性质定理", "辅助线", "全等 / 相似判定")},
    {"name": "方程与不等式", "keywords": ("方程", "不等式", "解集", "判别式", "取值范围"),
     "knowledge": ("因式分解", "判别式", "分类讨论")},
    {"name": "导数与微积分", "keywords": ("导数", "积分", "极限", "微分", "定积分"),
     "knowledge": ("求导法则", "导数应用", "极限的定义")},
    {"name": "级数收敛性", "keywords": ("级数", "收敛", "发散", "判别法"),
     "knowledge": ("比较判别法", "p-级数", "比值判别法")},
    {"name": "分数与四则运算", "keywords": ("分数", "通分", "约分", "还剩"),
     "knowledge": ("分数的意义", "通分", "求一个数的几分之几")},
]

STOP_TOKENS = frozenset({"已知", "求其", "下列", "的是", "一个", "以及", "其中", "如何", "什么"})


# ---------------------------------------------------------------- 工具

def emit(payload, code):
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(code)


def norm(text):
    """归一化：去掉空白与标点、转小写。用于重复检测与答案匹配。"""
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
    for field in LIST_FIELDS:
        value = card.get(field)
        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str):
                    out.append(("%s[%d]" % (field, index), item))
    return out


def problem_tokens(problem):
    """题目里的高信号线索：数字与 ASCII 标识符（f、x、n、a_n 之类）。"""
    tokens = NUM_RE.findall(problem) + IDENT_RE.findall(problem)
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

    for field in LIST_FIELDS:
        if field in card:
            value = card[field]
            if not isinstance(value, list) or not value or \
                    not all(isinstance(i, str) and i.strip() for i in value):
                errors.append({"code": "E_BAD_LIST", "field": field,
                               "detail": "必须是非空的字符串列表"})

    questions = card.get("starter_questions")
    if isinstance(questions, list) and all(isinstance(q, str) for q in questions):
        if len(questions) != STARTER_COUNT:
            errors.append({"code": "E_STARTER_COUNT", "count": len(questions),
                           "detail": "starter_questions 必须恰好 %d 条，实为 %d 条"
                                     % (STARTER_COUNT, len(questions))})

        seen = {}
        for index, question in enumerate(questions, start=1):
            if not question.strip().endswith(("？", "?")):
                errors.append({"code": "E_NOT_QUESTION", "index": index, "text": question,
                               "detail": "启动问题应以问号结尾：只问'想什么'，不问'答案是什么'"})
            if len(norm(question)) < 5:
                warnings.append({"code": "W_TOO_SHORT", "index": index, "text": question,
                                 "detail": "问题过短，可能起不到启动思路的作用"})
            key = norm(question)
            if key in seen:
                errors.append({"code": "E_DUPLICATE_QUESTION", "index": index, "text": question,
                               "detail": "与第 %d 条重复" % seen[key]})
            else:
                seen[key] = index

    emit({
        "action": "validate",
        "input": {"card": args.card},
        "method": "字段完整性 + 恰好 5 条启动问题 + 疑问句形式 + 去重",
        "errors": errors,
        "warnings": warnings,
        "passed": not errors,
    }, 0 if not errors else 1)


# ---------------------------------------------------------------- audit

def cmd_audit(args):
    card = load_card(args.card)
    problem = (args.problem or "").strip()
    if not problem:
        emit({"error": "--problem must be a non-empty string"}, 2)

    errors, warnings = [], []
    texts = card_texts(card)

    # A1 显式给出答案的措辞
    for field, text in texts:
        low = text.lower()
        for pattern, label in ANSWER_PATTERNS:
            if pattern.search(low):
                errors.append({"code": "A_ANSWER_PHRASE", "field": field, "text": text,
                               "detail": "出现给出答案的措辞：%s" % label})

    # A2 与标准答案精确匹配（信号最强，但需 --answer）
    if args.answer and args.answer.strip():
        target = norm(args.answer)
        if target:
            level = "error" if len(target) >= 2 else "warning"
            bucket = errors if level == "error" else warnings
            code = "A_ANSWER_MATCH" if level == "error" else "A_ANSWER_MATCH_SHORT"
            note = ("卡片文本与标准答案 %r 匹配" % args.answer if level == "error"
                    else "答案过短（归一化后 %d 字符），匹配结果仅供参考" % len(target))
            for field, text in texts:
                if target in norm(text):
                    bucket.append({"code": code, "field": field, "text": text, "detail": note})

    # A3 完整解法开篇标记
    for field, text in texts:
        for marker in SOLUTION_MARKERS:
            if marker in text:
                errors.append({"code": "A_FULL_SOLUTION", "field": field, "text": text,
                               "detail": "出现完整解法开篇标记：%s" % marker})

    # W1 结论性数值等式（疑似把结果写进卡片）
    for field, text in texts:
        for match in CONCLUSION_RE.finditer(text):
            number = match.group(1)
            if number in TRIVIAL_NUMBERS:
                continue
            warnings.append({"code": "W_NUMERIC_RESULT", "field": field, "text": match.group(0),
                             "detail": "出现结论性数值等式，疑似泄漏结果 %s" % number})

    # W2 卡片与题目是否脱节（题目线索太少时不判）
    tokens = problem_tokens(problem)
    if len(tokens) >= 3:
        joined = " ".join(norm(text) for _, text in texts)
        if not any(norm(token) in joined for token in tokens):
            warnings.append({"code": "W_DETACHED", "field": "*", "problem_tokens": tokens[:12],
                             "detail": "卡片没有引用题目里的任何数字或符号，可能脱离原题"})

    passed = not errors and not (args.strict and warnings)
    emit({
        "action": "audit",
        "input": {"card": args.card, "problem": problem,
                  "answer": args.answer, "strict": args.strict},
        "method": "规则扫描：答案措辞 / 与标准答案精确匹配 / 完整解法标记 / "
                  "结论性数值等式 / 与原题的关联",
        "errors": errors,
        "warnings": warnings,
        "passed": passed,
        "capability_note": "规则门而非语义理解：passed 只说明卡片没越过这几条线，不等于卡片正确。",
    }, 0 if passed else 1)


# ---------------------------------------------------------------- classify

def cmd_classify(args):
    problem = (args.problem or "").strip()
    if not problem:
        emit({"error": "--problem must be a non-empty string"}, 2)

    low = problem.lower()
    candidates = []
    for hint in TOPIC_HINTS:
        hits = [kw for kw in hint["keywords"] if kw.lower() in low]
        if hits:
            candidates.append({
                "question_type": hint["name"],
                "matched_keywords": hits,
                "knowledge_needed_hint": list(hint["knowledge"]),
            })

    emit({
        "action": "classify",
        "input": {"problem": problem},
        "method": "关键词表启发式初判（未命中不代表无题型，只代表关键词表没覆盖）",
        "candidates": candidates,
        "authority": "heuristic-hint-only",
        "capability_note": "关键词命中只是提示，可能误判；必须以读题结论为准，"
                           "不得用本输出替代对题目的理解。",
    }, 0)


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(
        description="Validate and audit a pre-solve thinking card.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="structural gate for a thinking card")
    p_validate.add_argument("--card", required=True, help="path to the card JSON file")
    p_validate.set_defaults(func=cmd_validate)

    p_audit = sub.add_parser("audit", help="scan a card for answer leakage and detachment")
    p_audit.add_argument("--card", required=True, help="path to the card JSON file")
    p_audit.add_argument("--problem", required=True, help="the original problem text")
    p_audit.add_argument("--answer", default=None,
                         help="optional known answer, for exact-match leakage detection")
    p_audit.add_argument("--strict", action="store_true",
                         help="treat warnings as failures")
    p_audit.set_defaults(func=cmd_audit)

    p_classify = sub.add_parser("classify", help="heuristic topic hint for a problem")
    p_classify.add_argument("--problem", required=True, help="the problem text")
    p_classify.set_defaults(func=cmd_classify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
