#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""partition_check.py — 题目分区的**版面分块门**。

用法：
  partition_check.py validate --payload partition.json [--strict]

退出码：
  0 = 通过；1 = 不合格（有 error，或 --strict 下出现 warning）；2 = 输入非法。

本门只查版面分块单的形状与措辞：块 1–12 个、每块有位置与版面依据、
数量与范围自洽、有不确定说明和确认问题、有边界说明。
**它不判断分块是否真的对应题目，也不验证图片。** 块数不等于题目数；
学生确认之后的归属才算数。共用常量见 `_rules.py`。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rules import (  # noqa: E402
    PARTITION_ACTION, PARTITION_ASSERTIVE_RE, PARTITION_BLOCK_FIELDS,
    PARTITION_CONFIRM_CUES, PARTITION_ERROR_CLAIM_RE, PARTITION_LIMITATION_CUES,
    PARTITION_MAX_BLOCKS, PARTITION_MIN_BLOCKS, PARTITION_OCR_CLAIM_RE,
    PARTITION_REQUIRED_FIELDS, PARTITION_SCORES, PARTITION_SOURCES, emit, norm,
    out_of_scope_matches,
)


def load_payload(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError:
        emit({"error": "payload file not found", "path": path}, 2)
    except json.JSONDecodeError as exc:
        emit({"error": "payload is not valid JSON", "path": path, "detail": str(exc)}, 2)
    except UnicodeError as exc:
        emit({"error": "payload is not valid UTF-8", "path": path, "detail": str(exc)}, 2)
    except OSError as exc:
        emit({"error": "cannot read payload file", "path": path, "detail": str(exc)}, 2)
    if not isinstance(payload, dict):
        emit({"error": "payload must be a JSON object", "path": path,
              "got": type(payload).__name__}, 2)
    return payload


def payload_texts(payload):
    """摊平分块单里的说明性文字；block_id 不扫（它是标识，不是断言）。"""
    out = []

    def add(field, value):
        if isinstance(value, str) and value.strip():
            out.append((field, value))

    add("uncertainty", payload.get("uncertainty"))
    add("confirmation_question", payload.get("confirmation_question"))
    limitations = payload.get("limitations")
    if isinstance(limitations, list):
        for index, item in enumerate(limitations, start=1):
            add("limitations[%d]" % index, item)
    blocks = payload.get("blocks")
    if isinstance(blocks, list):
        for index, block in enumerate(blocks, start=1):
            if not isinstance(block, dict):
                continue
            for field in ("location", "visual_cues", "note"):
                add("blocks[%d].%s" % (index, field), block.get(field))
    return out


def cmd_validate(args):
    payload = load_payload(args.payload)
    errors, warnings = [], []

    for field in PARTITION_REQUIRED_FIELDS:
        if field not in payload:
            errors.append({"code": "E_MISSING_FIELD", "field": field,
                           "detail": "缺少必需字段"})
    for field in payload:
        if field not in PARTITION_REQUIRED_FIELDS:
            errors.append({"code": "E_EXTRA_FIELD", "field": field,
                           "detail": "分块单只能包含标准字段；六维分析、错误清单、"
                                     "诊断结论请放在别的出口"})

    if payload.get("action") != PARTITION_ACTION:
        errors.append({"code": "E_BAD_ACTION", "field": "action",
                       "text": payload.get("action"),
                       "detail": "action 必须是 %r" % PARTITION_ACTION})

    source = payload.get("block_source")
    if source not in PARTITION_SOURCES:
        errors.append({"code": "E_BAD_SOURCE", "field": "block_source",
                       "text": source, "allowed": list(PARTITION_SOURCES),
                       "detail": "分块来源非法"})

    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        errors.append({"code": "E_BAD_BLOCKS", "field": "blocks",
                       "detail": "必须是数组，每项是一块版面区域"})
        blocks = []
    elif not (PARTITION_MIN_BLOCKS <= len(blocks) <= PARTITION_MAX_BLOCKS):
        errors.append({"code": "E_BLOCK_COUNT", "field": "blocks", "count": len(blocks),
                       "detail": "版面块必须 %d–%d 个，实为 %d 个"
                                 % (PARTITION_MIN_BLOCKS, PARTITION_MAX_BLOCKS, len(blocks))})

    seen_ids = {}
    confidences = []
    for index, block in enumerate(blocks, start=1):
        tag = "blocks[%d]" % index
        if not isinstance(block, dict):
            errors.append({"code": "E_BAD_BLOCK", "field": tag,
                           "detail": "每块必须是 JSON 对象"})
            continue
        for field in PARTITION_BLOCK_FIELDS:
            if field not in block:
                errors.append({"code": "E_MISSING_FIELD", "field": "%s.%s" % (tag, field),
                               "detail": "缺少必需字段"})
        for field in block:
            if field not in PARTITION_BLOCK_FIELDS:
                errors.append({"code": "E_EXTRA_FIELD", "field": "%s.%s" % (tag, field),
                               "detail": "非标准字段，建议删除"})

        block_id = block.get("block_id")
        if not isinstance(block_id, str) or not block_id.strip():
            errors.append({"code": "E_EMPTY_TEXT", "field": "%s.block_id" % tag,
                           "detail": "块编号必须是非空字符串"})
        else:
            key = norm(block_id)
            if key in seen_ids:
                errors.append({"code": "E_DUPLICATE_BLOCK_ID", "field": "%s.block_id" % tag,
                               "text": block_id,
                               "detail": "与第 %d 块编号重复" % seen_ids[key]})
            else:
                seen_ids[key] = index

        for field in ("location", "visual_cues", "note"):
            value = block.get(field)
            if field in block and (not isinstance(value, str) or not value.strip()):
                errors.append({"code": "E_EMPTY_TEXT", "field": "%s.%s" % (tag, field),
                               "detail": "必须是非空字符串"})

        separate = block.get("separate_problem")
        if "separate_problem" in block and not isinstance(separate, bool):
            errors.append({"code": "E_TYPE", "field": "%s.separate_problem" % tag,
                           "detail": "必须是布尔值：这块像不像一次独立的题目尝试"})

        confidence = block.get("confidence")
        if isinstance(confidence, str):
            confidence = confidence.strip()
            confidences.append(confidence)
        if "confidence" in block and confidence not in PARTITION_SCORES:
            errors.append({"code": "E_BAD_CONFIDENCE", "field": "%s.confidence" % tag,
                           "text": block.get("confidence"),
                           "allowed": list(PARTITION_SCORES),
                           "detail": "置信度取值非法"})

    estimated = payload.get("estimated_problem_count")
    if not isinstance(estimated, int) or isinstance(estimated, bool):
        errors.append({"code": "E_TYPE", "field": "estimated_problem_count",
                       "detail": "必须是整数"})
    elif blocks and not (1 <= estimated <= len(blocks)):
        errors.append({"code": "E_BAD_ESTIMATE", "field": "estimated_problem_count",
                       "text": estimated,
                       "detail": "估计题目数必须在 1 到版面块数（%d）之间" % len(blocks)})

    count_range = payload.get("count_range")
    if not isinstance(count_range, list) or len(count_range) != 2 \
            or not all(isinstance(value, int) and not isinstance(value, bool)
                       for value in count_range):
        errors.append({"code": "E_BAD_RANGE", "field": "count_range",
                       "detail": "必须是两个整数组成的数组：[最少, 最多]"})
    else:
        low, high = count_range
        if not (1 <= low <= high):
            errors.append({"code": "E_BAD_RANGE", "field": "count_range",
                           "text": count_range,
                           "detail": "范围必须满足 1 <= 最少 <= 最多"})
        if blocks and high > len(blocks):
            errors.append({"code": "E_BAD_RANGE", "field": "count_range",
                           "text": count_range,
                           "detail": "最多不能超过版面块数（%d）" % len(blocks)})
        if isinstance(estimated, int) and not isinstance(estimated, bool) \
                and not (low <= estimated <= high):
            errors.append({"code": "E_RANGE_MISMATCH", "field": "count_range",
                           "text": count_range,
                           "detail": "估计值必须落在范围内"})

    uncertainty = payload.get("uncertainty")
    if not isinstance(uncertainty, str) or not uncertainty.strip():
        errors.append({"code": "E_EMPTY_TEXT", "field": "uncertainty",
                       "detail": "必须写明哪里分不准、为什么"})

    question = payload.get("confirmation_question")
    if not isinstance(question, str) or not question.strip():
        errors.append({"code": "E_EMPTY_TEXT", "field": "confirmation_question",
                       "detail": "必须请学生确认分块归属"})
    elif not ("？" in question or "?" in question
              or any(cue in question for cue in PARTITION_CONFIRM_CUES)):
        errors.append({"code": "E_NO_CONFIRMATION", "field": "confirmation_question",
                       "detail": "确认问题里要有明确的问句或「确认 / 像不像 / 哪」"})

    limitations = payload.get("limitations")
    if not isinstance(limitations, list) or not limitations:
        errors.append({"code": "E_BAD_LIMITATIONS", "field": "limitations",
                       "detail": "必须列出至少一条限制说明"})
    else:
        for index, item in enumerate(limitations, start=1):
            if not isinstance(item, str) or not item.strip():
                errors.append({"code": "E_EMPTY_TEXT",
                               "field": "limitations[%d]" % index,
                               "detail": "限制说明必须是非空字符串"})
        joined = " ".join(item for item in limitations if isinstance(item, str))
        if not any(cue in joined for cue in PARTITION_LIMITATION_CUES):
            errors.append({"code": "E_LIMITATION_VAGUE", "field": "limitations",
                           "detail": "至少要说清「只看版面、不读字符、块数不等于题目数、"
                                     "归属需学生确认」中的一条"})

    # 措辞扫描：越界、断言、错因、OCR 自读
    for field, text in payload_texts(payload):
        for code, label, matched, _start, _end in out_of_scope_matches(text):
            errors.append({"code": code, "field": field, "text": text, "matched": matched,
                           "detail": "越过本 skill 边界：%s" % label})
        for match in PARTITION_ASSERTIVE_RE.finditer(text):
            errors.append({"code": "E_ASSERTIVE_PARTITION", "field": field,
                           "text": text, "matched": match.group(0),
                           "detail": "只能给「大致分块」，不能把版面块说成已确认的题目边界"})
        for match in PARTITION_ERROR_CLAIM_RE.finditer(text):
            errors.append({"code": "E_ERROR_CLAIM_IN_PARTITION", "field": field,
                           "text": text, "matched": match.group(0),
                           "detail": "分区出口不查对错；要查对错请走 math-error-diagnosis"})
        for match in PARTITION_OCR_CLAIM_RE.finditer(text):
            errors.append({"code": "E_OCR_CLAIM_IN_PARTITION", "field": field,
                           "text": text, "matched": match.group(0),
                           "detail": "分区只看版面，不读字符；内容必须由学生自己给出"})

    if blocks and confidences and all(value == "高" for value in confidences) \
            and count_range == [len(blocks), len(blocks)]:
        warnings.append({"code": "W_OVERCONFIDENT_PARTITION", "field": "*",
                         "detail": "每块都标高置信、范围又收成一个数；"
                                   "手写草稿的块边界通常没有这么确定，请复核一下"})

    passed = not errors and not (args.strict and warnings)
    emit({
        "action": "partition",
        "input": {"payload": args.payload, "strict": args.strict},
        "method": "版面分块单形状检查：块 1–12 个、位置与版面依据、数量与范围自洽、"
                  "不确定说明、确认问题、限制说明；外加越界 / 断言 / 错因 / OCR 自读措辞扫描",
        "errors": errors,
        "warnings": warnings,
        "passed": passed,
        "capability_note": "本门不判断分块是否真的对应题目，也不验证图片。"
                           "块数不等于题目数；学生确认之前的归属只是候选。",
    }, 0 if passed else 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="校验分块单")
    validate.add_argument("--payload", required=True)
    validate.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.command == "validate":
        cmd_validate(args)


if __name__ == "__main__":
    main()
