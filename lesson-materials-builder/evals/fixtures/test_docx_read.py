#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测 SKILL.md 里那条读 .docx 的命令**本身**。

    python evals/fixtures/test_docx_read.py

## 为什么要从 SKILL.md 里把命令抠出来跑

如果把命令抄一份到这个脚本里，测的就是**这个副本**，不是文档里那条。
文档哪天被人改坏了（少个引号、改错 sys.argv 下标、把 reconfigure 删了），
副本照样绿。所以这条用例把命令当数据读出来执行 —— 被测对象是文档。

## 为什么要在 PYTHONIOENCODING=gbk 下跑

Windows 上 Python 输出流默认 GBK。教案里的汉字走 GBK 没问题，但命令里若
打了 ✓ 之类的符号就会 UnicodeEncodeError —— 而且是在**成功**的时候崩，
现象是「读一份正常教案却失败」。verify_pptx 当初正是栽在这上面。
把编码钉死在 GBK，是让这个失败模式可复现，而不是指望测试机的默认值恰好合适。
"""

import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..", "..", "SKILL.md")
DOCX = os.path.join(HERE, "minimal-zh.docx")

# 教案里必然出现的字，用来确认读出来的**是正文**，不是空串或乱码
NEEDLES = ["勾股定理", "教学目标", "直角三角形"]


def extract_docx_command():
    """从 SKILL.md 的 bash 代码块里抠出读 .docx 的那条命令。"""
    text = open(SKILL, encoding="utf-8").read()
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("python -c") and "word/document.xml" in s:
            return s
    return None


def _interpreter():
    """The document writes `python`; that name is absent on Windows Store
    installs and often on macOS (only `python3` exists). Use the interpreter
    running this fixture so the rest of the command stays literal."""
    return sys.executable


def main():
    cmd = extract_docx_command()
    if cmd is None:
        print("✗ SKILL.md 里找不到读 .docx 的命令")
        print("  （找的是含 word/document.xml 的 python -c 行）")
        return 1
    print("从 SKILL.md 抠出的命令：")
    print("  %s" % (cmd[:100] + ("…" if len(cmd) > 100 else "")))

    if not os.path.exists(DOCX):
        print("✗ 缺少 %s —— 先跑 make_minimal_docx.py" % DOCX)
        return 1

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "gbk"     # 复现 Windows 默认输出编码
    # 命令里的占位参数是「教案.docx」，换成真夹具路径
    # 用 lambda 而不是字符串做替换：DOCX 是 Windows 绝对路径，
    # 里面 C:\Users 的 \U 会被 re 当成转义符，直接传字符串会 PatternError。
    # 路径含空格（如 "university learning"），必须加引号，否则 shell 会截断。
    real = re.sub(r"\s+教案\.docx\s*$", lambda m: ' "%s"' % DOCX, cmd)
    if real == cmd:
        real = cmd + ' "%s"' % DOCX
    real = re.sub(r"^python(\s+)",
                  lambda m: '"%s"%s' % (_interpreter(), m.group(1)), real, count=1)

    p = subprocess.run(real, shell=True, capture_output=True, env=env)
    if p.returncode != 0:
        print("✗ 退出码 %d" % p.returncode)
        print("  stderr: %s" % p.stderr.decode("utf-8", "replace")[:400])
        return 1

    out = p.stdout.decode("utf-8")       # 必须**是**合法 UTF-8，不是「碰巧能看」
    if not out.strip():
        print("✗ 输出为空 —— 命令跑了但没读出任何东西")
        return 1

    han = len(re.findall(r"[一-鿿]", out))
    missing = [n for n in NEEDLES if n not in out]
    print("  读出汉字 %d 个" % han)
    print("  正文首行：%s" % out.strip().splitlines()[0][:60])
    if missing:
        print("✗ 正文里缺这些字：%s —— 读出来的可能不是教案正文" % missing)
        return 1
    if han < 40:
        print("✗ 只读出 %d 个汉字，太少了，像是没读全" % han)
        return 1

    print("✓ SKILL.md 的 .docx 命令：GBK 编码下仍输出合法 UTF-8，且读到教案正文")
    return 0


if __name__ == "__main__":
    sys.exit(main())
