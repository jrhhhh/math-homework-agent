#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""扫技能目录，看有没有把不该带出去的东西带出去。

    python scripts/lint_privacy.py --identifier <真名> --identifier <学号>
    python scripts/lint_privacy.py --identifiers-file <工作区外>/corpus.json

退出码：0 = 干净；1 = 命中；2 = **没跑**（没给标识符清单）。

## 为什么这个脚本自己不带标识符

技能包是要发给别人的。若把真名、学号直接写进这个脚本，那它就成了泄露源本身 ——
为了防泄露而泄露。所以标识符一律从**外部**传入：命令行，或工作区外的
`corpus.json` 里的 `identifiers` 字段。

没给清单时**退出码 2、明说没跑**，而不是安静地报「干净」。这正是本项目那条
规矩：查不到 ≠ 没问题。一个不打招呼就绿的隐私检查，比没有还危险 ——
它会给「打包好了」这件事盖章。

## 为什么做成回归测试

「我有没有把真名漏进分享包」这件事，靠人记是不可靠的：这次记得，下次打包时
未必。接进 `bench.py regress` 之后，每次改动都会顺带扫一遍。
"""

import argparse
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEXT_EXT = {".md", ".txt", ".py", ".json", ".ps1", ".sh", ".yml", ".yaml",
            ".html", ".css", ".js", ".csv"}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}


def load_ids(args):
    ids = list(args.identifier or [])
    # 环境变量这条路是给 bench.py 用的：它得把标识符递给子进程，而
    # 中文真名直接进 argv 的话，在 Windows 上要过一层 shell 编码，
    # 走到这儿可能已经成了乱码 —— 于是「搜不到」被当成「干净」。
    # 搜索词坏掉必须表现为崩，不能表现为绿，所以宁可走环境变量。
    env = os.environ.get("LINT_PRIVACY_IDENTIFIERS", "")
    ids += [x.strip() for x in env.split(",") if x.strip()]
    if args.identifiers_file:
        try:
            with open(args.identifiers_file, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print("读不了 %s：%r" % (args.identifiers_file, e))
            return None
        if isinstance(data, dict):
            ids += list(data.get("identifiers") or [])
            for s in data.get("slots") or []:
                ids += list(s.get("identifiers") or [])
        elif isinstance(data, list):
            ids += [str(x) for x in data]
    return [i for i in dict.fromkeys(ids) if i and len(str(i)) >= 2]


def scan(root, ids):
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            path = os.path.join(dirpath, fn)
            if os.path.splitext(fn)[1].lower() not in TEXT_EXT:
                continue
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                for ident in ids:
                    if str(ident) in line:
                        hits.append((os.path.relpath(path, root), i,
                                     str(ident), line.strip()[:80]))
    return hits


def main():
    ap = argparse.ArgumentParser(description="技能目录隐私扫描")
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--identifier", action="append", default=[])
    ap.add_argument("--identifiers-file", default=None)
    a = ap.parse_args()

    ids = load_ids(a)
    if ids is None:
        return 2
    if not ids:
        print("没提供标识符清单 —— **这一项没有跑**，不等于干净。")
        print("  用法：--identifier <真名> --identifier <学号>")
        print("   或：--identifiers-file <工作区外>/corpus.json")
        print("   或：环境变量 LINT_PRIVACY_IDENTIFIERS=真名,学号")
        return 2

    print("扫描 %s" % a.root)
    print("标识符 %d 个：%s" % (len(ids), "、".join(ids[:6])
                                + ("…" if len(ids) > 6 else "")))
    hits = scan(a.root, ids)
    if not hits:
        print("✓ 干净，没有命中")
        return 0
    print("✗ 命中 %d 处 —— 技能包要发给别人，这些不能带出去：" % len(hits))
    for path, ln, ident, ctx in hits[:40]:
        print("   %s:%d  「%s」  %s" % (path, ln, ident, ctx))
    if len(hits) > 40:
        print("   …另有 %d 处" % (len(hits) - 40))
    return 1


if __name__ == "__main__":
    sys.exit(main())
