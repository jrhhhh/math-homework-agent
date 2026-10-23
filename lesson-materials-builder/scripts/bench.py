#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bench.py —— 课件技能的基准驱动器。

    python scripts/bench.py regress                    # ① 回归层：秒级、零模型成本
    python scripts/bench.py regress --out <目录>        # 指定产出目录
    python scripts/bench.py regress --list             # 只列探针，不跑

## 这套东西要解决的问题

技能里有一堆校验器，但没有基准。校验器只回答「刚生成的这份文件有没有毛病」，
回答不了「改了技能之后是变好了还是变坏了」。更糟的是**假绿**：报告上一切正常，
而实际上某个检查根本没跑。

所以本项目的头号恐惧是「验证环节悄悄没跑，而结论看着一切正常」。这个驱动器的
全部设计都冲着它去。

## 四态，不是两态

每条断言的结果是四态之一：

    pass     跑了，符合预期
    fail     跑了，不符合预期
    not_run  没跑（前置条件不满足 / 探针没报这一条）
    error    探针自己崩了，或报了没声明的断言

`not_run` 和 `error` **与 `fail` 一样让退出码非零**。坏掉的测试台必须是红的，
不能是「绿 + 备注」。这与 build_pptx.py 的「告警是提示不是错误」正相反 ——
故意的：告警是判断，检查缺失不是判断。

## 五条机制

1. **passed 是派生量。** `passed = (status == "pass")`。写探针的人只能填状态，
   **没法**在一条没跑的检查上手写 `passed: true`。
2. **前置条件先跑。** 不满足 → 该探针全部记 `not_run`，证据写明是哪个前置条件。
3. **期望双向核对。** 探针声明它应当报出哪些断言 id。声明了没报 → 合成 `not_run`；
   报了没声明 → `error`。专治「检查被悄悄关掉」。
4. **xfail 是记录，不是通过。** 已知漏检记 xfail：不报算过，报了算 XPASS（提示可摘）。
   让漏检**可见**，而不是假装它不存在。
5. **字段名沿用生态。** grading.json 用 text / passed / evidence，status 作附加键。
"""

import argparse
import json
import os
from collections import defaultdict
import re
import subprocess
import sys
import tempfile
import traceback

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(ROOT, "evals", "fixtures")
FIGURES = os.path.join(FIXTURES, "figures")

PASS, FAIL, NOT_RUN, ERROR = "pass", "fail", "not_run", "error"


# ---------------------------------------------------------------- 前置条件

def _importable(mod):
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def _privacy_ids():
    """标识符从**外部**来 —— 这个文件本身绝不能写真名。

    就是 `lint_privacy.py` 立的那条规矩：为了防泄露而泄露，是最讽刺的一种。
    技能包要发给别人，所以这个文件里只许有「去哪儿拿」，不许有「拿什么」。

    **长度 ≥ 2 这条过滤，必须和 `lint_privacy.load_ids` 完全一致。** 起初这里
    只做 strip，于是 `BENCH_IDENTIFIERS=x` 时 bench 认为「有清单」，而 lint 把它
    滤掉后报 exit 2「没跑」—— 两边对同一件事的判断不一样，报告上写的是「没跑」，
    可人明明传了东西，只能干瞪眼。四态引擎没让这次变成假绿（记的是 NOT-RUN
    不是 pass），但那句误导人的话还得靠两边对齐来消掉。
    """
    raw = os.environ.get("BENCH_IDENTIFIERS", "")
    return [x.strip() for x in raw.split(",") if len(x.strip()) >= 2]


def _need_ids():
    """返回 True 表示可跑；返回字符串表示**没跑**，且这串就是要显示的理由。

    说清楚为什么，比说一句「前置条件不满足」有用得多 —— 看到后者的人不知道
    自己该做什么。这条提示得直接给出那条能跑起来的命令。
    """
    if _privacy_ids():
        return True
    raw = os.environ.get("BENCH_IDENTIFIERS", "").strip()
    if raw and len(raw) < 2:
        return ("BENCH_IDENTIFIERS=%r 太短（少于 2 个字符）—— 单个字符会匹配到"
                "技能包里几乎所有文件，扫出来的结果没有意义，所以两边都拒收。"
                "填真名与学号" % raw)
    return ("没给标识符清单，不知道要搜什么。设 BENCH_IDENTIFIERS=真名,学号 再跑；"
            "确实不适用时才用 --no-privacy，那会在报告里显式留一条痕迹")


PRECONDITIONS = {
    "python_pptx": lambda: _importable("pptx"),
    "pillow": lambda: _importable("PIL"),
    "fixtures": lambda: os.path.isdir(FIXTURES),
    "figures": lambda: os.path.isdir(FIGURES),
    "built_decks": lambda: os.path.isdir(os.environ.get("BENCH_TMP", "")),
    "identifiers": _need_ids,
}


def unmet(requires):
    """→ [(前置条件名, 理由), ...]，空列表表示都满足。

    前置条件可以返回字符串当理由（见 `_need_ids`）。理由要一路带到 not_run
    记录里 —— 「没跑」这三个字必须自带下一步怎么跑，否则读报告的人只能干瞪眼。
    """
    out = []
    for r in requires:
        v = PRECONDITIONS[r]()
        if v is not True:
            out.append((r, v if isinstance(v, str) else ""))
    return out


# ---------------------------------------------------------------- 记录

class Records:
    """一条断言 = 一条记录。status 只能填，passed 是算出来的。"""

    def __init__(self):
        self.items = []

    def add(self, aid, text, ok, evidence, xfail=False):
        if xfail:
            # 已知漏检：预期不成立。不成立 → 记 pass（xfail 生效）；
            # 成立了 → 也记 pass，但打 XPASS 提醒把 xfail 摘掉。
            status = PASS
            evidence = ("XPASS —— 已知漏洞似乎修好了，可以摘掉 xfail："
                        if ok else "xfail（仍如预期不成立）：") + evidence
        else:
            status = PASS if ok else FAIL
        self.items.append({
            "id": aid, "text": text, "status": status,
            "passed": status == PASS,          # 派生量，不接受手填
            "evidence": evidence,
        })

    def not_run(self, aid, text, why):
        self.items.append({
            "id": aid, "text": text, "status": NOT_RUN,
            "passed": False, "evidence": why,
        })

    def error(self, aid, text, why):
        self.items.append({
            "id": aid, "text": text, "status": ERROR,
            "passed": False, "evidence": why,
        })


PROBES = []


def probe(pid, text, requires=(), expects=()):
    def deco(fn):
        PROBES.append({"id": pid, "text": text, "requires": list(requires),
                       "expects": list(expects), "fn": fn})
        return fn
    return deco


# ---------------------------------------------------------------- 工具

def render(md, out, env=None):
    """跑渲染器，返回 (ok, stdout)。"""
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([sys.executable, os.path.join(HERE, "build_pptx.py"),
                        md, "-o", out], capture_output=True, cwd=ROOT, env=e)
    return p.returncode == 0, p.stdout.decode("utf-8", "replace")


def warns_of(stdout):
    """渲染器把告警打成 '  · …'，抠出消息本体。"""
    return [l.strip()[2:].strip() for l in stdout.splitlines()
            if l.strip().startswith("· ")]


def verify(path, figures=FIGURES):
    sys.path.insert(0, HERE)
    import verify_pptx
    prs, errs, warns, info = verify_pptx.check(path, figures)
    msg = lambda x: x[1] if isinstance(x, tuple) else str(x)
    return [msg(e) for e in errs], [msg(w) for w in warns], info


def verify_rich(path, figures=FIGURES):
    """同上，但带类别标签（`scan()` 的返回）。

    产出层要**按类别**计分，不能靠正则匹配提示语里的中文散文 —— 见
    verify_pptx.scan() 的 docstring。
    """
    sys.path.insert(0, HERE)
    import verify_pptx
    return verify_pptx.scan(path, figures)


def excluded_cats():
    """从告警类别表里读出「不许当质量判据」的那些类别。

    判据是实测的：**凡是在人写的课件上也大量触发的类别，量的是「是不是用这个
    技能做的」，不是「好不好」** —— 拿它计分等于宣布人做的课件不合格。
    详见 evals/warning-categories.json 的 _calibration 一节。

    读表而不是在代码里写死一份，是为了让两边不会各自漂走：改判据要改表，
    改表这里的断言就跟着变。
    """
    p = os.path.join(ROOT, "evals", "warning-categories.json")
    try:
        with open(p, encoding="utf-8") as f:
            cats = json.load(f)["categories"]
    except Exception:
        return None
    return {c["id"] for c in cats if c.get("exclude_from_scoring")}


def rendered(R, aid, text, md, out, env=None):
    """渲染成功则返回 stdout；失败则记 error 并返回 None。

    **别把「渲染没跑成」报成 fail。** 环境缺 Pillow 时渲染会失败，若几条探针
    只顾解析告警、不看退出码，就会报成「告警里没有」—— 读起来像「技能的检查
    坏了」，实际是本机环境不全。那正是这套东西要防的假信号：把「没跑」说成
    「不符预期」。审计自己也要守这条规矩。
    """
    ok, stdout = render(md, out, env)
    if not ok:
        tail = (stdout.strip().splitlines() or ["（无输出）"])[-1][:150]
        R.error(aid, text, "渲染失败 —— 这是环境或被测代码的问题，不是断言不成立：%s" % tail)
        return None
    return stdout


def tmp(name):
    d = os.environ.get("BENCH_TMP") or os.path.join(
        os.environ.get("TEMP", "/tmp"), "lm-bench")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name)


# ---------------------------------------------------------------- 探针：语体

@probe("reg.wording", "语体检查：命中词典的必须报，词典漏洞当前不报（xfail）",
       requires=("fixtures",),
       expects=("reg.wording.hits", "reg.wording.clean", "reg.wording.gap.*"))
def p_wording(R):
    md = os.path.join(FIXTURES, "wording-defects.md")
    out = rendered(R, "reg.wording.hits", "语体检查命中", md, tmp("wording-defects.pptx"))
    if out is None:
        return
    w = " ".join(warns_of(out))
    # 断言**按句子点名**，不只看计数：写成「告警数 ≥ 5」的话，
    # 漏掉的那 3 句会被其它命中掩盖，benchmark 反而给漏洞盖章。
    for word in ("谁都会", "一下", "它"):
        R.add("reg.wording.hits", "口语词 %r 必须被告警" % word,
              word in w, "告警里%s出现 %r" % ("" if word in w else "没", word))
    for sent, tag in (("越切越薄", "越切越薄，本数变多"),
                      ("只用以前学过的知识", "要求只用以前学过的知识"),
                      ("这是已知的", "长方体 V = Sh，这是已知的")):
        R.add("reg.wording.gap.%s" % sent, "词典漏洞：「%s」应当被告警" % tag,
              sent in w, "检测器词典只有 8 个词 + 一条「它」，这句一个都不沾",
              xfail=True)

    md2 = os.path.join(FIXTURES, "wording-clean.md")
    out2 = rendered(R, "reg.wording.clean", "干净对照", md2, tmp("wording-clean.pptx"))
    if out2 is None:
        return
    style = [x for x in warns_of(out2) if "口语痕迹" in x or "一整句话被塞进" in x]
    R.add("reg.wording.clean", "干净对照必须 0 条语体告警",
          not style, "语体告警 %d 条%s" % (len(style), ("：" + style[0]) if style else ""))


# ---------------------------------------------------------------- 探针：结构告警

@probe("reg.layout_alias", "废弃别名 [分步] 必须提示已更名",
       requires=("fixtures",), expects=("reg.layout_alias.warn",))
def p_alias(R):
    out = rendered(R, "reg.layout_alias.warn", "废弃别名必须提示",
                   os.path.join(FIXTURES, "layout-alias.md"), tmp("alias.pptx"))
    if out is None:
        return
    w = " ".join(warns_of(out))
    R.add("reg.layout_alias.warn", "[分步] 必须报「已更名为 [流程]」",
          "已更名为" in w,
          "改名告警%s" % ("出现" if "已更名为" in w else "**没出现**（死代码？）"))


@probe("reg.answer_loss", "写在不渲染版式上的 !ans: 必须告警",
       requires=("fixtures",), expects=("reg.answer.invisible", "reg.answer.blank"))
def p_ans(R):
    out = rendered(R, "reg.answer.invisible", "解答静默丢失必须告警",
                   os.path.join(FIXTURES, "ans-loss.md"), tmp("ans-loss.pptx"))
    if out is None:
        return
    w = " ".join(warns_of(out))
    R.add("reg.answer.invisible", "封面/阐述上的解答必须报「版式不渲染底部块」",
          "版式不渲染底部块" in w, "告警里%s" % ("有" if "版式不渲染底部块" in w else "没有"))
    R.add("reg.answer.blank", "空 !ans: 必须报「后面是空的」",
          "后面是空的" in w, "告警里%s" % ("有" if "后面是空的" in w else "没有"))


@probe("reg.flow_caption", "流程页过长的说明必须报折行",
       requires=("fixtures", "figures"),
       expects=("reg.flow_caption.wrap",))
def p_caption(R):
    out = rendered(R, "reg.flow_caption.wrap", "流程说明折行必须告警",
                   os.path.join(FIXTURES, "flow-caption-overflow.md"),
                   tmp("flow-cap.pptx"))
    if out is None:
        return
    w = " ".join(warns_of(out))
    R.add("reg.flow_caption.wrap", "说明文字折行必须告警", "折了" in w,
          "告警里%s" % ("有「折了 N 行」" if "折了" in w else "没有折行告警"))


@probe("reg.glyph", "字形查不到时必须明说，不许静默放行",
       requires=("fixtures",), expects=("reg.glyph.unchecked",))
def p_glyph(R):
    env = {"PYTHONPATH": os.path.join(FIXTURES, "no-fonttools")}
    out = rendered(R, "reg.glyph.unchecked", "字形查不到必须明说",
                   os.path.join(FIXTURES, "mutation-base.md"),
                   tmp("nofont.pptx"), env=env)
    if out is None:
        return
    R.add("reg.glyph.unchecked", "藏掉 fontTools 后必须报「字形覆盖未检查」",
          "字形覆盖未检查" in out,
          "用 evals/fixtures/no-fonttools 挡板注入 ImportError 后，%s"
          % ("报出了" if "字形覆盖未检查" in out else "**没有任何提示**"))


# ---------------------------------------------------------------- 探针：变异矩阵

@probe("reg.mutate", "变异矩阵：每条几何检查各配一个必须触发它的坏件",
       requires=("fixtures", "figures", "python_pptx", "pillow"),
       expects=("reg.mutate.base", "reg.mutate.*"))
def p_mutate(R):
    sys.path.insert(0, FIXTURES)
    import mutate_pptx as M

    base_md = os.path.join(FIXTURES, "mutation-base.md")
    base = tmp("mutation-base.pptx")
    ok, out = render(base_md, base)
    if not ok:
        R.error("reg.mutate.base", "变异基准必须渲染成功", "渲染失败")
        return

    errs, warns, _ = verify(base)
    R.add("reg.mutate.base", "变异基准必须 0 ERROR 0 WARN",
          not errs and not warns,
          "ERROR %d / WARN %d%s" % (len(errs), len(warns),
                                    ("：" + errs[0][:70]) if errs else ""))

    from pptx import Presentation
    for name in sorted(M.MUTATIONS):
        doc, fn, expect, xfail = M.MUTATIONS[name]
        out_p = tmp("mut-%s.pptx" % name)
        try:
            import shutil
            shutil.copyfile(base, out_p)
            prs = Presentation(out_p)
            fn(prs)
            prs.save(out_p)
        except Exception as e:
            R.error("reg.mutate.%s" % name, doc, "变异本身出错：%r" % e)
            continue
        try:
            errs, warns, _ = verify(out_p)
        except Exception as e:
            R.error("reg.mutate.%s" % name, doc,
                    "复核这个坏件时崩了：%r" % e)
            continue
        hit = [m for m in (errs + warns) if expect in m]
        R.add("reg.mutate.%s" % name, "%s → 必须报「%s」" % (doc, expect),
              bool(hit), (hit[0][:80] if hit else "ERROR %d / WARN %d，没报这一条"
                          % (len(errs), len(warns))), xfail=xfail)


# ---------------------------------------------------------------- 探针：对照

@probe("reg.control", "对照必须干净：见谁都报的检查等于没有检查",
       requires=("fixtures", "figures", "python_pptx"),
       expects=("reg.control.twocol_left",))
def p_control(R):
    md = os.path.join(FIXTURES, "two-col-img-left.md")
    deck = tmp("two-col-left.pptx")
    if rendered(R, "reg.control.twocol_left", "两栏左图右文对照", md, deck) is None:
        return
    errs, warns, _ = verify(deck)
    R.add("reg.control.twocol_left", "[两栏] 图放 ## 左 必须 0 ERROR",
          not errs, "ERROR %d%s" % (len(errs), ("：" + errs[0][:70]) if errs else ""))


# ---------------------------------------------------------------- 探针：静态

@probe("reg.independence", "复核脚本必须独立于被检代码",
       requires=("fixtures",), expects=("reg.independence.no_import",))
def p_indep(R):
    src = open(os.path.join(HERE, "verify_pptx.py"), encoding="utf-8").read()
    bad = re.findall(r"^[ \t]*(?:import|from)[ \t]+build_pptx", src, re.M)
    R.add("reg.independence.no_import", "verify_pptx.py 不得 import build_pptx",
          not bad, "复核必须独立于被检代码，否则是自证；命中 %d 处" % len(bad))


# 基线组作业里**不许出现**的、技能自己的方法内容。
# 注意这里查的是**方法本身**，不是文件的名字 —— 配置段必须点名 `SKILL.md`/
# `references/` 才能禁止它们，把名字算进来会立刻误报。
LEAK_WORDS = ("认知台阶", "verify_pptx")
# 上面每个词都必须**同时**出现在有技能组的作业里，否则「删干净」也能让基线过。
LEAK_CONTROL = LEAK_WORDS


@probe("reg.job_leak", "基线组的作业文件里不得抄进技能的方法",
       requires=("fixtures",),
       expects=("reg.job_leak.baseline_clean", "reg.job_leak.control"))
def p_job_leak(R):
    """r1 的基线组被作业文件抄了技能的核心主张，于是 with/without 那组对照不成立。

    出事的那句是 `JOB_TEMPLATE` 要求 2 的末尾「切页要按**认知台阶**，不是按教案
    标题」（`SKILL.md:21-24` 的核心主张）。它是**共用段落**，于是两组都拿到了；
    上一轮只把 `flow` 与 `selfcheck` 按配置拆开了，漏了这一句。

    这个漏点不会让作业跑不动，所以不会有任何东西报错 —— 它只会静静地让
    「技能加了多少值」这个数字失去意义。这条断言就是为它设的。

    **必须配正向对照**：只查基线干净的话，把两边的这段内容一起删掉也能过 ——
    那就成了「修漏点修成静默关掉检查」，正是本项目最防的失败模式。
    """
    try:
        slot = {"scope": "（回归探针，无 slot）"}
        tb = JOB_TEMPLATE.format(**job_fields(
            "without_skill", "mini-1__without_skill", "<src>", "<out>", slot))
        tw = JOB_TEMPLATE.format(**job_fields(
            "with_skill", "mini-1__with_skill", "<src>", "<out>", slot))
    except KeyError as e:
        R.error("reg.job_leak.baseline_clean", "作业模板渲染", "缺字段 %s" % e)
        return
    hits = [w for w in LEAK_WORDS if w in tb]
    R.add("reg.job_leak.baseline_clean",
          "基线组作业里不得出现技能的方法内容",
          not hits, "命中 %r —— 基线被污染，with/without 对照不成立" % hits
          if hits else "")
    missing = [w for w in LEAK_CONTROL if w not in tw]
    R.add("reg.job_leak.control",
          "有技能组必须仍含这些内容（否则是把内容删了，不是把漏点修了）",
          not missing, "缺失 %r" % missing if missing else "")


@probe("reg.skill_md", "SKILL.md 里那条读 .docx 的命令必须真的能用",
       requires=("fixtures",), expects=("reg.skill_md.docx_cmd",))
def p_docx(R):
    p = subprocess.run([sys.executable, os.path.join(FIXTURES, "test_docx_read.py")],
                       capture_output=True, cwd=ROOT)
    out = p.stdout.decode("utf-8", "replace")
    R.add("reg.skill_md.docx_cmd", "命令从 SKILL.md 抠出，在 GBK 下仍读到教案正文",
          p.returncode == 0,
          (out.strip().splitlines() or ["（无输出）"])[-1][:100])


@probe("reg.privacy", "技能包里不得带真名 / 学号",
       requires=("fixtures", "identifiers"), expects=("reg.privacy.clean",))
def p_privacy(R):
    """扫技能目录。这是唯一一条**检查对象是技能包本身**的断言。

    别的探针都在问「技能产出的东西对不对」，这一条问的是「这个包能不能发出去」。
    它必须有 —— 因为漏一个真名进分享包这件事，靠人记是不可靠的：这次记得，
    下次打包时未必。而且它是**唯一一条失败后果不可逆**的检查：别的错误改一改
    重跑就是，名字泄露出去就收不回来了。

    标识符经环境变量递给子进程（见 `_need_ids` 与 lint 那边的注释）。
    """
    env = dict(os.environ)
    env["LINT_PRIVACY_IDENTIFIERS"] = ",".join(_privacy_ids())
    p = subprocess.run([sys.executable, os.path.join(HERE, "lint_privacy.py")],
                       capture_output=True, cwd=ROOT, env=env)
    out = p.stdout.decode("utf-8", "replace")
    hits = [l.strip() for l in out.splitlines() if l.strip().startswith(("references", "scripts", "evals", "assets", "SKILL"))]
    # 退出码 2 = 脚本自己说「没跑」。绝不能当成通过 —— 那正是它被设计成
    # 与 0 区分开的原因，这儿若不认，等于把它那点设计又抹平了。
    if p.returncode == 2:
        R.not_run("reg.privacy.clean", "隐私扫描",
                  "lint_privacy.py 说这一项没跑：" + (out.strip().splitlines() or [""])[-1][:90])
        return
    ok = p.returncode == 0
    R.add("reg.privacy.clean", "技能目录里搜不到已配置的标识符", ok,
          "干净" if ok else "命中 %d 处：%s" % (len(hits), " ｜ ".join(hits[:3])))


@probe("reg.emph_spacing", "两行强调块也必须显式写行距",
       requires=("fixtures", "python_pptx"), expects=("reg.emph_spacing.clean",))
def p_emph(R):
    """夹具 `emph-wrap.md` 抓到的缺陷（产出层第一次真跑时暴露的）。

    `emph_height()` 按 `EMPH_LINE = 0.62` 算强调块的高度 —— 底部堆叠区的预算
    和框高都靠它。但 `add_emph()` **从不把行距写进 XML**，于是真正渲染出来的
    行高由字体自然行高决定，跟 0.62 未必相等：模型说这个块多高，渲染出来是
    另一个高度。这正是 `check_spacing_written` 的 docstring 自己警告的
    「静默脱钩」。

    两个校验器覆盖面还不一样：`verify_pptx` 查**所有**高度 ≥1.0in 的文字块，
    `check_spacing_written` 只查 `body-block` / `answer-block`。于是任何折成
    两行的 `!!!` 都会被 verify 报「行距未显式指定」，而作者从 `课件.md` 里
    **改不掉** —— 唯一的出路是把句子压到一行，那是绕过内容，不是修好。

    这条断言钉的就是「两行强调块也不许出现那条告警」。一行那个块作对照：
    它高 0.78in，落回 verify 自己 1.0in 的阈值之下，两边都不该报。
    """
    md = os.path.join(FIXTURES, "emph-wrap.md")
    out = tmp("emph-wrap.pptx")
    stdout = rendered(R, "reg.emph_spacing.clean", "两行强调块不得报行距缺失",
                      md, out)
    if stdout is None:
        return
    _, warns_v, _ = verify(out, "")
    bad = [w for w in warns_v if "行距未显式指定" in w]
    R.add("reg.emph_spacing.clean",
          "两行 `!!!` 不得触发「行距未显式指定」", not bad,
          "没有这条告警" if not bad else
          "报了 %d 条：%s（作者从 课件.md 里改不掉，只能把句子压成一行）"
          % (len(bad), " ｜ ".join(bad[:2])))


@probe("reg.ink", "着墨一致性检查：两个方向都要钉",
       requires=("fixtures", "figures", "python_pptx", "pillow"),
       expects=("reg.ink.real_clean", "reg.ink.bad_caught"))
def p_ink(R):
    p = subprocess.run([sys.executable, os.path.join(FIXTURES, "test_ink_check.py")],
                       capture_output=True, cwd=ROOT)
    out = p.stdout.decode("utf-8", "replace")
    for aid, label, needle in (
            ("reg.ink.real_clean", "渲染器产出必须干净", "① 渲染器产出干净"),
            ("reg.ink.bad_caught", "坏渲染器必须被抓", "② 坏渲染器被抓")):
        R.add(aid, label, needle in out,
              "test_ink_check.py：%s" % ("通过" if needle in out else "这一环没通过"))


# ---------------------------------------------------------------- 产出层
#
# 产出层与回归层有一个根本区别：**它要花钱**。每跑一条 slot 就是一次完整的
# 执行子代理（10–20 分钟、15–40 万 token），所以默认只跑一份，其余按需展开。
#
# 还有一条：**bench.py 不调模型。** 生成课件必须由 agent 完成，脚本起不了子代理。
# 所以这里是三段式，人在中间：
#   plan  → 出 job 文件（告诉调用方该让子代理干什么）
#   [调用方 Claude 起子代理跑]
#   grade → 对产物跑脚本断言
#   report→ 汇总

RUN_LAYOUT = """
runs/<时间戳>/
  jobs/<slot>__<config>.md    plan 产出：给执行子代理的指令
  out/<slot>__<config>/       子代理把 课件.md / 课件.pptx / figures/ 写这儿
  grading.json                grade 产出
  benchmark.json              report 产出
"""

# 下界的默认值。**别拍脑袋定，跑了再定。**
#
# min_chars_per_page 一开始拍的是 40，结果在**已知良好**的那份参考卡组上就报了
# 「第 1 页过空」（封面 34 字）。实测两份真卡组的每页字符数：
#   好·祖暅原理 [34,54,71,74,47,54,50,63,64,61,143,114]
#   坏·盲跑     [34,55,52,56,73,52,34,43,49,52,49,201,176]
# 最低 34，两处 —— 封面（本来就字少）与流程页（三张图为主）。40 在这两份上
# 都误报。一条见谁都报的断言会被无视，那比没有还糟。20 能抓住真掉内容的页面
# （那种接近 0–10 字），又放行合法的稀疏页。
#
# 这个数是**从这两份数据来的**，不是普适常数。换了语料要重测。
DEFAULT_BOUNDS = {"min_pages": 5, "min_chars_per_page": 20,
                  "min_figures": 1, "max_warns": 4}


def load_corpus(path):
    """读 corpus.json。出错返回 None 并打清楚原因。

    这个文件在技能目录**外面**：它同时装着私有教案的绝对路径和标识符清单，
    两样都不能进分享包。技能目录里那三份自制语料是通用无隐私的，所以那三条
    slot 的 path 是相对技能目录的。
    """
    if not path or not os.path.isfile(path):
        print("读不到语料清单：%s" % (path or "（没给 --corpus）"))
        print("  它应放在技能目录**外面** —— 里面有私有教案路径与标识符。")
        return None
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:
        print("语料清单不是合法 JSON：%r" % (e,))
        return None
    slots = d.get("slots") or []
    if not slots:
        print("语料清单里没有 slots。")
        return None
    for s in slots:
        s.setdefault("default", False)
        s.setdefault("ship", False)
        for k, v in DEFAULT_BOUNDS.items():
            s.setdefault(k, v)
    d["_path"] = os.path.abspath(path)
    return d


def resolve_slot(corpus, slot):
    """把 slot 的 path 解成真实路径。ship=true 的相对技能目录，其余是绝对路径。

    不复制文件 —— 私有教案带真名与学号，只存路径。缺文件是**正常情况**
    （别人拿到包就没有这些），上层记 not_run，不报错。
    """
    p = slot["path"]
    if not os.path.isabs(p):
        p = os.path.join(ROOT, p)
    return os.path.normpath(p)


def pick_slots(corpus, only=None, all_slots=False):
    slots = corpus["slots"]
    if only:
        want = [x.strip() for x in only.split(",") if x.strip()]
        miss = [w for w in want if not any(s["id"] == w for s in slots)]
        if miss:
            print("语料清单里没有这些 slot：%s" % "、".join(miss))
            print("  有的：%s" % "、".join(s["id"] for s in slots))
            return None
        return [s for s in slots if s["id"] in want]
    if all_slots:
        return list(slots)
    d = [s for s in slots if s.get("default")] or [s for s in slots if s.get("ship")]
    return d[:1]


# ---------------------------------------------------------------- plan

JOB_TEMPLATE = """# 产出层作业：{sid}（{config}）

**你是执行子代理。** 这一步是**端到端做一份课件**：把下面这份教案做成课件。
做完不要自行评分，评分由 `bench.py grade` 做。

## 输入

- 教案：`{src}`
- 口径：{scope}
- 输出目录：`{outdir}`

## 配置

- `{config}` —— {config_note}

## 要求

1. {flow}
2. 产物写到 `{outdir}`：`课件.md`（源）、`课件.pptx`（成品）、`figures/`（配图）。
   另外把**切页依据**写进 `{outdir}/大纲.md` —— 评分时要靠它看出你是怎么切的页。
   {paging}
3. {selfcheck}
4. **不要去读 `{skill}/evals/` 下的任何东西。** 那是基准的夹具，看了就污染了这次测量 ——
   本作业要的是「自然产出」，不是「照着夹具凑出来的产出」。

## 边界

- 教案里有的环节不许漏；教案里没有的不许编（数学内容尤其）。
- 卡住了、有疑问、或判断这一步做不下去 —— **如实写在报告里**，不要为了交差硬做。
  一份「我没做出来，因为 X」的报告，比一份凑出来的课件有用得多。
"""


def job_fields(cfg, sid, src, outdir, slot):
    """一份作业里**因配置而异**的那几段话。

    原来整张模板是共用的，于是基线组（`without_skill`）收到的是同一段要求：
    开头「照 SKILL.md 走完整流程」、第 3 条「必须跑 verify_pptx.py」—— 而它的
    配置说明白写着「不要读 SKILL.md、不要调 scripts/ 里的任何东西」。一条要求里
    两个命令互相打架，基线组的子代理如实把这件事报了上来。

    这类矛盾不会让作业跑不动（子代理自己会挑一条照做），但它**毁掉可比性**：
    基线组若真去跑了 verify，它就被技能的复核脚本影响过了，那还叫什么基线。
    所以这几段必须按配置分开生成，不能共用。

    ⚠ **`paging` 是同一处的第二漏点，r1 跑完之后才补上。** 上一版把 `flow` 与
    `selfcheck` 分开生成了，却漏掉「要求 2」末尾那句「切页要按**认知台阶**，
    不是按教案标题」—— 它是 JOB_TEMPLATE 的共用段落，于是 r1 的基线组照样
    拿到了技能的核心主张（`SKILL.md:21-24`）。**证据不是推测**：那份基线自己写的
    `out/.../大纲.md` 开头就是「切页按**认知台阶**排，不按教案的小标题」，
    并据此把教案的 4 个环节拆成 6 级台阶。它没读技能文件，但**被告知了技能的方法**。
    r1 的 with/without 对照因此不成立，要重跑基线组才能谈「技能加了多少值」。
    """
    kw = dict(sid=sid, config=cfg, src=src, outdir=outdir,
              scope=slot.get("scope", "（未标注）"), skill=ROOT, script_dir=HERE)
    if cfg == "with_skill":
        kw["paging"] = "切页要按**认知台阶**，不是按教案标题。"
        kw["config_note"] = "完整使用技能：读 SKILL.md，走完全部 6 步。"
        kw["flow"] = ("**照 `{skill}/SKILL.md` 走完整流程**，包括第 3 步「输出大纲，"
                      "请用户确认」—— 那一步没有人可确认，自行判断后继续。").format(**kw)
        kw["selfcheck"] = ("渲染完**必须**跑 `python {script_dir}/verify_pptx.py "
                           "课件.pptx --figures figures/`，把结果一并留在 "
                           "`{outdir}/自检.txt`。").format(**kw)
    else:
        # 不给切页判据 —— 给了就是把技能的核心主张抄给基线。只要求它交代自己怎么切的。
        kw["paging"] = "怎么切由你自己判断，把这样切的理由写清楚就行。"
        kw["config_note"] = ("**不用技能**。这是基线 —— 直接照教案做一份课件，"
                             "不要读 SKILL.md、references/、也不要调 scripts/ 里的"
                             "任何东西。产出的形态会明显更随意，那是**预期的**，别去补。")
        kw["flow"] = ("**不许碰技能包**：不要读 `{skill}/SKILL.md` 或 `references/`，"
                      "也不要调用 `{skill}/scripts/` 里的任何脚本。就用你手头本来"
                      "有的工具（包括自己现写的脚本）把这份教案做成课件。").format(**kw)
        kw["selfcheck"] = ("成品要你自己设法确认没有明显的几何/字体毛病 —— "
                           "**只能用技能包之外的办法**（自己写脚本查，或肉眼逐页看）。"
                           "把你怎么查的、查出什么，留在 `{outdir}/自检.txt`。"
                           "基线组不做 `verify` 断言，这份记录只是留个底。").format(**kw)
    return kw


def cmd_plan(a):
    corpus = load_corpus(a.corpus)
    if corpus is None:
        return 2
    slots = pick_slots(corpus, a.only, a.all)
    if slots is None:
        return 2

    run = a.run or os.path.join(os.getcwd(), "runs")
    os.makedirs(os.path.join(run, "jobs"), exist_ok=True)
    configs = ["with_skill"] if a.config == "with_skill" else \
              ([a.config] if a.config != "both" else ["with_skill", "without_skill"])

    print("产出层作业 —— %d 个 slot × %d 个配置" % (len(slots), len(configs)))
    planned, missing = [], []
    for s in slots:
        src = resolve_slot(corpus, s)
        if not os.path.isfile(src):
            # 缺文件不是错误：别人拿到分享包就没有私有教案，slot 照样留在清单里。
            missing.append((s["id"], src))
            continue
        for cfg in configs:
            sid = "%s__%s" % (s["id"], cfg)
            outdir = os.path.join(run, "out", sid)
            os.makedirs(outdir, exist_ok=True)
            jp = os.path.join(run, "jobs", sid + ".md")
            with open(jp, "w", encoding="utf-8") as f:
                f.write(JOB_TEMPLATE.format(**job_fields(cfg, sid, src, outdir, s)))
            planned.append((sid, jp, outdir))
            print("  · %-28s %s" % (sid, jp))

    for sid, src in missing:
        print("  ~ %-28s 教案不在（%s）—— 跳过，别人拿到分享包时也是这样"
              % (sid, src))
    if not planned:
        print("\n没有可跑的作业。")
        return 2
    print("\n下一步：由调用方起执行子代理跑上面这些 job，把产物（课件.md / 课件.pptx /")
    print("figures/）放进各自的 out 目录，然后：")
    print("  python scripts/bench.py grade  --corpus %s --run \"%s\"" % (corpus["_path"], run))
    print("  python scripts/bench.py report --run \"%s\"" % run)
    return 0


# ---------------------------------------------------------------- grade

def deck_stats(path):
    """→ [(正文字符数, 图片数), ...]，每页一项。"""
    from pptx import Presentation
    prs = Presentation(path)
    out = []
    for sl in prs.slides:
        chars = pics = 0
        for sh in sl.shapes:
            if sh.shape_type == 13 or sh.__class__.__name__ == "Picture":
                pics += 1
            if getattr(sh, "has_text_frame", False):
                chars += len("".join(sh.text_frame.text.split()))
        out.append((chars, pics))
    return out


def grade_one(R, slot, sid, outdir, corpus):
    """对一个产物目录跑全部脚本断言。产物不在 → not_run，不是 fail。"""
    tag = "out.%s" % sid
    label = "%s（%s）" % (sid, slot.get("scope", ""))

    if not os.path.isdir(outdir):
        R.not_run(tag + ".produced", label, "还没跑：产物目录不存在 %s" % outdir)
        return
    decks = [f for f in os.listdir(outdir) if f.lower().endswith(".pptx")]
    if not decks:
        R.not_run(tag + ".produced", label,
                  "还没跑：%s 里没有 .pptx。先起子代理跑 job，再回来 grade。" % outdir)
        return
    if len(decks) > 1:
        R.error(tag + ".produced", label,
                "产物目录里有 %d 个 .pptx，不知道该评哪个：%s" % (len(decks), decks))
        return
    deck = os.path.join(outdir, decks[0])
    srcs = [f for f in os.listdir(outdir) if f.lower().endswith(".md")]
    R.add(tag + ".produced", label + " 产出存在", True, os.path.basename(deck))

    # —— 几何复核。这是产出层最硬的一条：它不依赖任何模型判断。
    figs = os.path.join(outdir, "figures")
    rec = verify_rich(deck, figs if os.path.isdir(figs) else "")
    errs = [x["msg"] for x in rec["errors"]]
    R.add(tag + ".verify", label + " verify_pptx 无 ERROR", not errs,
          "0 ERROR" if not errs else "%d 条：%s" % (len(errs), " ｜ ".join(errs[:3])))

    # —— 校准后的缺陷数。
    #
    # **这条不是区分度断言，别把它读成「技能更好」。** 实测结论：目前没有一条
    # 脚本信号能把技能产出和基线产出按「质量」分开 —— 基线那几十条告警里，
    # 大部分（行距写法、版心居中、页脚规矩）人写的参赛稿一样触发，量的是
    # 「是不是用这个技能做的」；唯一一条技能 0 / 基线 5 的（图文间隙偏大），
    # 又还没经过人写课件的校准（人写那份配不上文字块，检查在那份上没生效）。
    #
    # 它真正的用处是**防误报回归**：技能产出里不该出现任何一条「连人写的课件
    # 都从不触发」的缺陷。哪天渲染器开始把正文顶到标题带上、或把图拉变形，
    # 这条会红，而 verify 那条 ERROR 断言不一定抓得住（它是 WARN 级）。
    exc = excluded_cats()
    if exc is None:
        R.not_run(tag + ".defects", label,
                  "读不到 evals/warning-categories.json，不知道该排除哪些类别")
    else:
        bad = [x for x in (rec["errors"] + rec["warns"]) if x["cat"] not in exc]
        # 断言文案里带着「校准未完成」——**因为它现在唯一的区分力来自一条
        # 没人写课件背书的判据**（gap.large：人写那份配不上文字块，检查在那份上
        # 没生效，所以拿不到「老师会不会认为 0.93in 是缺陷」这个答案）。
        # 报告不给好看的绿，也不给好看的红。
        R.add(tag + ".defects",
              label + " 校准后的缺陷 = 0（人写课件也从不触发的那些类别；"
                      "其中 gap.large 的校准未完成，见 warning-categories.json）",
              not bad,
              "0 条" if not bad else "%d 条：%s" % (
                  len(bad), " ｜ ".join("%s P%s" % (x["cat"], x["page"]) for x in bad[:4])))

    # —— 下界。**每条都要**，否则基准会向「什么都不渲染」漂移：
    #    0 ERROR 和「无告警」都是可以靠交白卷满足的。
    try:
        pages = deck_stats(deck)
    except Exception as e:
        R.error(tag + ".pages", label, "读不了成品：%r" % (e,))
        return
    R.add(tag + ".pages", label + " 页数 ≥ %d" % slot["min_pages"],
          len(pages) >= slot["min_pages"], "实际 %d 页" % len(pages))

    thin = [i + 1 for i, (c, _) in enumerate(pages)
            if c < slot["min_chars_per_page"]]
    R.add(tag + ".density",
          label + " 每页正文 ≥ %d 字（防空页）" % slot["min_chars_per_page"],
          not thin, "全部达标" if not thin else "第 %s 页过空" % thin)

    nfig = sum(p for _, p in pages)
    R.add(tag + ".figures", label + " 图片数 ≥ %d" % slot["min_figures"],
          nfig >= slot["min_figures"], "实际 %d 张" % nfig)

    # —— 渲染告警数。告警是**判断**不是错误（见 build_pptx 的定位），所以这里
    #    只设上限、且放宽，不追求 0。真正该做的事是让人去看那几条告警写了什么。
    #
    # 两个坑，都踩过：
    #
    # ① **不能拿 srcs[0] 当课件源。** 子代理的产物目录里通常不止一个 .md
    #    （`_做法说明.md`、`大纲.md`、`课件.md`），而 listdir 的顺序是任意的。
    #    挑错了就会拿「做法说明」去重渲染，数出一堆毫无意义的告警 —— 报告上
    #    写着「告警 12 条」，看着像技能产出很糟，实际是评分器挑错了文件。
    #    假信号比漏报更有破坏力，因为它是**主动误导**。认死 `课件.md`
    #    （SKILL.md 与 slides-spec 里写明的那个名字），认不出就说认不出。
    #
    # ② **基线组不该跑这一条。** 技能的渲染器不是基线产出管线的一部分 ——
    #    「拿技能渲染器去读一份不是技能格式的 markdown」量到的是两种格式的
    #    阻抗失配，不是质量。那既不是 PASS 也不是 FAIL，是**不适用**。
    cfg = sid.rsplit("__", 1)[-1] if "__" in sid else ""
    src_md = next((f for f in srcs if f == "课件.md"), None)
    if cfg == "without_skill":
        R.not_run(tag + ".warns", label,
                  "基线组不适用：这条量的是技能渲染器对技能格式源的告警数，"
                  "而基线组不走那条管线")
    elif src_md is None:
        R.not_run(tag + ".warns", label,
                  "找不到 `课件.md`（目录里的 .md 是 %s）—— 认不出哪个才是课件源，"
                  "与其乱挑一个数出假告警，不如不数" % (srcs or "无"))
    else:
        # 重渲染必须写到**被评目录之外**。早先写的是 outdir/_regrade.pptx，
        # 于是 grade 跑第二遍就会在产物目录里看见两个 .pptx 而直接报 ERROR ——
        # 「评分跑两次结果不一样」是最难查的一类毛病：第一次看着好好的。
        scratch = tempfile.mkdtemp(prefix="bench-regrade-")
        ok, stdout = render(os.path.join(outdir, src_md),
                            os.path.join(scratch, "_regrade.pptx"))
        if ok:
            w = warns_of(stdout)
            R.add(tag + ".warns",
                  label + " 渲染告警 ≤ %d 条" % slot["max_warns"],
                  len(w) <= slot["max_warns"],
                  "%d 条%s" % (len(w), ("：" + " ｜ ".join(w[:3])) if w else ""))
        else:
            R.not_run(tag + ".warns", label, "重渲染没跑成，数不出告警")


def cmd_grade(a):
    corpus = load_corpus(a.corpus)
    if corpus is None:
        return 2
    run = a.run
    if not os.path.isdir(run):
        print("没有这个 run 目录：%s" % run)
        return 2

    R = Records()
    outroot = os.path.join(run, "out")
    found = os.listdir(outroot) if os.path.isdir(outroot) else []
    if not found:
        print("%s 里还没有任何产物。" % outroot)
        return 2

    print("产出层评分 —— %s" % run)
    for sid in sorted(found):
        base = sid.split("__")[0]
        slot = next((s for s in corpus["slots"] if s["id"] == base), None)
        if slot is None:
            R.error("out.%s.produced" % sid, sid,
                    "这个 slot 不在语料清单里 —— 是清单改了，还是产物放错了目录？")
            continue
        for k, v in DEFAULT_BOUNDS.items():
            slot.setdefault(k, v)
        grade_one(R, slot, sid, os.path.join(outroot, sid), corpus)

    n = summarize(R.items)
    gpath = os.path.join(run, "grading.json")
    with open(gpath, "w", encoding="utf-8") as f:
        json.dump({"layer": "output", "corpus": corpus["_path"],
                   "records": R.items}, f, ensure_ascii=False, indent=2)
    print("\n→ %s" % gpath)
    return 1 if (n[FAIL] or n[ERROR] or n[NOT_RUN]) else 0


# ---------------------------------------------------------------- report

def _split_aid(aid):
    """'out.mini-1__with_skill.verify' → ('mini-1', 'with_skill', 'verify')。"""
    if not aid.startswith("out.") or "." not in aid[4:]:
        return None
    head, suffix = aid[4:].split(".", 1)
    if "__" not in head:
        return None
    slot, config = head.rsplit("__", 1)
    return slot, config, suffix


def _human(text, suffix):
    """把 'mini-1__with_skill（10 分钟…） verify_pptx 无 ERROR' 里的人话部分抠出来。"""
    return text.split("）", 1)[-1].strip() if "）" in text else suffix


def _mark(r):
    """行首记号。**别把 NOT-RUN 画成「技能赢了」。**

    早先的写法是 `"←" if with_skill == PASS else "!"`，于是「有技能 pass、
    无技能 not_run」也标成 ← —— 那道箭头在表里的意思明明是「技能更强」，
    而 not_run 是**这条对基线根本不适用**（技能渲染器的告警数，基线不走那条
    管线）。把「没量」画成「赢了」，正是这个项目从头到尾在防的那件事，
    而且这次是发生在**我自己写的报告**里。
    """
    w, o = r["with_skill"], r["without_skill"]
    if NOT_RUN in (w, o) or ERROR in (w, o):
        return "· "          # 不可比，记号的缺席本身就是信息
    if w == o:
        return "  "
    return "← " if w == PASS else "! "   # ← 技能更强；! 技能更差（更该看）


def compare_configs(items):
    """同一轮里 with_skill 与 without_skill 的逐条对照。

    **这才是「技能加了多少值」的直接答案。** 跨轮基线（compare_baseline）回答的是
    「这次改动有没有把上次搞坏」，两者问的不是一件事：基线组是**同一个技能的历史**，
    对照组是**没有技能**。

    只在两个配置都跑过的时候才有意义。缺一个就返回 None —— 与其拿半张表充数，
    不如说清楚这次答不上来。
    """
    pairs = defaultdict(dict)
    for x in items:
        s = _split_aid(x["id"])
        if s:
            pairs[(s[0], s[2])][s[1]] = x
    rows = {k: v for k, v in pairs.items()
            if "with_skill" in v and "without_skill" in v}
    if not rows:
        return None
    # 按断言该有的阅读顺序排，不按字母 —— 「产出了吗 → 干净吗 → 够不够」
    # 是有叙事的，字母序（density→figures→pages→produced→verify→warns）
    # 会把这条线索打散，读的人得自己在脑子里重排。
    ORDER = ["produced", "verify", "defects", "pages", "density", "figures", "warns"]
    rank = {s: i for i, s in enumerate(ORDER)}
    out = {}
    for (slot, suffix), v in rows.items():
        out.setdefault(slot, []).append({
            "suffix": suffix,
            "what": _human(v["with_skill"]["text"], suffix),
            "with_skill": v["with_skill"]["status"],
            "without_skill": v["without_skill"]["status"],
        })
    for rows_ in out.values():
        rows_.sort(key=lambda r: (rank.get(r["suffix"], 99), r["suffix"]))
    return out


def compare_baseline(items, baseline_dir):
    """把这次的结果和基线逐条比。→ {regressed, fixed, gone, added, summary}

    四类里最要紧的是 `gone`：**基线里有、这次没有**的断言。
    它不该被当成「这次更干净了」—— 更可能是那条检查被悄悄关掉了。这正是
    整个 benchmark 想防的那件事，所以它单独成一类，印在最显眼的位置。

    基线就是某个 run 目录（通常存成 runs/baseline/）。没有它的时候一切照常，
    只是「变好还是变坏」这个问题答不上来 —— 那就别假装答得上来。
    """
    bp = os.path.join(baseline_dir, "grading.json")
    if not os.path.isfile(bp):
        print("基线目录里没有 grading.json：%s —— 跳过对比。" % baseline_dir)
        return None
    with open(bp, encoding="utf-8") as f:
        old = {x["id"]: x for x in json.load(f)["records"]}
    new = {x["id"]: x for x in items}

    regressed, fixed, added = [], [], []
    for aid, x in new.items():
        o = old.get(aid)
        if o is None:
            added.append(x)
        elif o["status"] == PASS and x["status"] != PASS:
            regressed.append(x)
        elif o["status"] != PASS and x["status"] == PASS:
            fixed.append(x)
    gone = [x for aid, x in old.items() if aid not in new]

    def rate(d):
        return (round(sum(1 for x in d.values() if x["status"] == PASS) / len(d), 4)
                if d else None)
    return {
        "regressed": regressed, "fixed": fixed, "gone": gone, "added": added,
        "summary": {"pass_rate": rate(old), "pass_rate_now": rate(new),
                    "regressed": len(regressed), "fixed": len(fixed),
                    "gone": len(gone), "added": len(added)},
    }


def cmd_report(a):
    """把 run 目录汇总成 benchmark.json + 一份人读的 md。

    字段名沿用生态（runs[] / run_summary），但聚合自己写 —— 生态那个脚本住在
    skill-creator 插件目录里，收到分享包的人没有。本技能要能独立分享。
    """
    run = a.run
    gp = os.path.join(run, "grading.json")
    if not os.path.isfile(gp):
        print("没有 %s —— 先跑 grade。" % gp)
        return 2
    with open(gp, encoding="utf-8") as f:
        g = json.load(f)
    items = g["records"]
    n = {k: sum(1 for x in items if x["status"] == k)
         for k in (PASS, FAIL, NOT_RUN, ERROR)}

    summary = {
        "pass": n[PASS], "fail": n[FAIL],
        "not_run": n[NOT_RUN], "errored": n[ERROR], "total": len(items),
        # 分数只在「全跑完了」时才有意义。没跑完就给个 0.xx，读的人会
        # 拿它去比较两次迭代 —— 而两次的 not_run 未必一样多。
        "pass_rate": (round(n[PASS] / len(items), 4) if items and
                      not (n[NOT_RUN] or n[ERROR]) else None),
        "complete": not (n[NOT_RUN] or n[ERROR]),
    }
    bench = {"runs": [{"run": os.path.basename(os.path.abspath(run)),
                       "layer": g.get("layer"), "records": items}],
             "run_summary": summary}
    # —— 与基线的差异。**这是整套东西的回报。**
    # 没有它，每跑一次只是又得到一份孤立的结果，「这次改动让它变好了吗」还是答不上来。
    diff = compare_baseline(items, a.baseline) if a.baseline else None
    if diff:
        bench["baseline"] = {"path": os.path.abspath(a.baseline), **diff["summary"]}

    cc = compare_configs(items)
    if cc:
        bench["config_compare"] = cc

    bp = os.path.join(run, "benchmark.json")
    with open(bp, "w", encoding="utf-8") as f:
        json.dump(bench, f, ensure_ascii=False, indent=2)
    print("→ %s" % bp)

    if cc:
        print()
        print("技能加了多少值（同轮两配置对照）")
        for slot, rows in cc.items():
            ws = sum(1 for r in rows if r["with_skill"] == PASS)
            wo = sum(1 for r in rows if r["without_skill"] == PASS)
            print("\n  %s —— 有技能 %d/%d，无技能 %d/%d"
                  % (slot, ws, len(rows), wo, len(rows)))
            for r in rows:
                print("    %s%-38s 有 %-8s 无 %s"
                      % (_mark(r), r["what"][:38],
                         r["with_skill"], r["without_skill"]))
            # 只看**可比**的行。NOT-RUN 的行本来就不参与比较，把它算进去会让
            # 「没有区分度」这句提示算错 —— 六条里一条真分得出来、五条不适用，
            # 读起来却像「有区分度」。
            cmp_ = [r for r in rows
                    if NOT_RUN not in (r["with_skill"], r["without_skill"])
                    and ERROR not in (r["with_skill"], r["without_skill"])]
            diff_ = [r for r in cmp_ if r["with_skill"] != r["without_skill"]]
            if not cmp_:
                print("    ⚠ 没有一条可比 —— 这张表答不了「技能加了多少值」。")
            elif not diff_:
                print("    ⚠ 可比的 %d 条两边结果完全一样 —— 这组断言对这条 slot "
                      "**没有区分度**。可能断言太松，也可能这条 slot 太简单。"
                      "**不能据此说技能没用**，只能说这几条量不出来。"
                      % len(cmp_))
            else:
                print("    —— 上面 %d 条里只有 %d 条两边不同。"
                      "**别把这张表当「技能全面更好」的证据**，它只说明这几条。"
                      % (len(cmp_), len(diff_)))
        print()

    if diff:
        print()
        for k, title, brief in (("regressed", "退步了", "这些原来是通过的"),
                                ("fixed", "修好了", "这些原来是不通过的"),
                                ("gone", "**检查消失了**", "基线里有、这次没跑 —— 先确认是不是被关掉了"),
                                ("added", "新增断言", "基线里没有，这次新加的")):
            rows = diff[k]
            if not rows:
                continue
            print("%s（%d）—— %s：" % (title, len(rows), brief))
            for r in rows[:8]:
                print("   %s  %s" % (r["status"], r["text"][:74]))
            if len(rows) > 8:
                print("   …另有 %d 条" % (len(rows) - 8))
        print()

    lines = ["# 产出层报告 —— %s" % os.path.basename(os.path.abspath(run)), "",
             "PASS %d / FAIL %d / NOT-RUN %d / ERROR %d（共 %d 条）"
             % (n[PASS], n[FAIL], n[NOT_RUN], n[ERROR], len(items)), ""]
    if not summary["complete"]:
        lines += ["> **这一轮没有跑完**（有 NOT-RUN 或 ERROR），"
                  "所以**没有 pass_rate** —— 拿一个没跑完的分数去比较两次迭代，"
                  "比出来的多半是「哪次跳过的少」。", ""]
    else:
        lines += ["> pass_rate = %.4f" % summary["pass_rate"], ""]
    if cc:
        lines += ["## 技能加了多少值（同轮两配置对照）", ""]
        for slot, rows in cc.items():
            ws = sum(1 for r in rows if r["with_skill"] == PASS)
            wo = sum(1 for r in rows if r["without_skill"] == PASS)
            lines += ["### %s —— 有技能 %d/%d，无技能 %d/%d"
                      % (slot, ws, len(rows), wo, len(rows)), "",
                      "| 断言 | 有技能 | 无技能 |", "|---|---|---|"]
            for r in rows:
                lines.append("| %s | %s | %s | %s |"
                             % (_mark(r).strip() or "", r["what"],
                                r["with_skill"], r["without_skill"]))
            cmp_ = [r for r in rows
                    if NOT_RUN not in (r["with_skill"], r["without_skill"])
                    and ERROR not in (r["with_skill"], r["without_skill"])]
            diff_ = [r for r in cmp_ if r["with_skill"] != r["without_skill"]]
            lines.append("")
            if not cmp_:
                lines += ["> ⚠ **没有一条可比 —— 这张表答不了「技能加了多少值」。**"]
            elif not diff_:
                lines += ["> ⚠ 可比的 %d 条两边结果完全一样 —— **这组断言对这条 slot "
                          "没有区分度**。可能断言太松，也可能这条 slot 太简单。"
                          "不能据此说技能没用，只能说这几条量不出来。" % len(cmp_)]
            else:
                lines += ["> 可比 %d 条，其中 %d 条两边不同（`←` 技能更强，"
                          "`!` 技能更差）。其余为不可比。" % (len(cmp_), len(diff_))]
            lines.append("")

    if diff:
        s = diff["summary"]
        lines += ["## 与基线的差异", "",
                  "pass_rate %s → %s" % (s["pass_rate"], s["pass_rate_now"]), ""]
        for key, title, brief in (
                ("regressed", "退步了", "原来通过、现在不通过 —— **先看这些**"),
                ("fixed", "修好了", "原来不通过、现在通过"),
                ("gone", "**检查消失了**",
                 "基线里有、这次没跑。别读成「更干净了」—— 更可能是那条检查被关掉了"),
                ("added", "新增断言", "基线里没有的")):
            rows = diff[key]
            if not rows:
                continue
            lines += ["### %s（%d）" % (title, len(rows)), "", brief, ""]
            for r in rows:
                lines.append("- %s — %s" % (r["text"], r["evidence"][:120]))
            lines.append("")

    for k, title in ((FAIL, "不符合预期"), (ERROR, "出错"),
                     (NOT_RUN, "**没跑**（不等于通过）")):
        bad = [x for x in items if x["status"] == k]
        if bad:
            lines += ["## %s" % title, ""]
            for x in bad:
                lines += ["- **%s** — %s" % (x["text"], x["evidence"][:160])]
            lines += [""]
    rp = os.path.join(run, "RUN-NOTES.md")
    with open(rp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("→ %s" % rp)
    return 0


# ---------------------------------------------------------------- 驱动器

def run_probes():
    R = Records()
    for p in PROBES:
        missing = unmet(p["requires"])
        if missing:
            why = "；".join("%s%s" % (n, ("：%s" % r) if r else "")
                            for n, r in missing)
            for aid in p["expects"] or [p["id"]]:
                R.not_run(aid, p["text"], "前置条件不满足 —— %s" % why)
            continue
        before = len(R.items)
        try:
            p["fn"](R)
        except Exception:
            R.error(p["id"], p["text"],
                    "探针崩了：%s" % traceback.format_exc(limit=2).splitlines()[-1])
        # 双向核对。
        # 两个方向都要，缺一个就有漏洞：
        #   声明了没报 → 检查可能被悄悄关掉了 → 合成 not_run
        #   报了没声明 → 有人加了条没人盯着的断言 → error
        # 声明支持尾部通配（"reg.mutate.*"），但**必须显式写出来**。
        # 早先图省事写成「id 以探针 id 开头就豁免」，结果随便什么
        # reg.independence.whatever 都能溜过去 —— 那等于这条核对形同虚设。
        got = {x["id"] for x in R.items[before:]}
        for aid in p["expects"]:
            if aid.endswith("*"):
                continue          # 通配声明只在反方向核对时用
            if aid not in got and not any(x["id"] == aid for x in R.items):
                R.not_run(aid, p["text"], "探针没报出这条断言（检查被关掉了？）")
        for x in R.items[before:]:
            if not _declared(x["id"], p["expects"]):
                x["status"] = ERROR
                x["passed"] = False
                x["evidence"] = "未在探针的 expects 里声明：" + x["evidence"]
    return R


def _declared(aid, expects):
    for e in expects:
        if e == aid:
            return True
        if e.endswith("*") and aid.startswith(e[:-1]):
            return True
    return False


def summarize(items):
    n = {k: sum(1 for x in items if x["status"] == k)
         for k in (PASS, FAIL, NOT_RUN, ERROR)}
    print()
    print("=" * 64)
    print("PASS %d  /  FAIL %d  /  NOT-RUN %d  /  ERROR %d   （共 %d 条）"
          % (n[PASS], n[FAIL], n[NOT_RUN], n[ERROR], len(items)))
    for k, title in ((FAIL, "不符合预期"), (ERROR, "探针出错"),
                     (NOT_RUN, "**没跑**（不等于通过）")):
        bad = [x for x in items if x["status"] == k]
        if bad:
            print("\n%s：" % title)
            for x in bad:
                print("  · %s\n      %s" % (x["text"], x["evidence"][:120]))
    xp = [x for x in items if x["evidence"].startswith("XPASS")]
    if xp:
        print("\nXPASS（可以摘掉 xfail 了）：")
        for x in xp:
            print("  · %s" % x["text"])
    print("=" * 64)
    return n


def main():
    ap = argparse.ArgumentParser(description="课件技能基准驱动器")
    ap.add_argument("cmd",
                    choices=["regress", "list", "plan", "grade", "report",
                             "blind-prep", "blind-grade"])
    ap.add_argument("--out", default=None, help="产出目录，默认临时目录")
    ap.add_argument("--no-privacy", action="store_true",
                    help="不跑隐私扫描（只在确实不适用时用；报告里会留痕）")
    ap.add_argument("--corpus", default=os.environ.get("BENCH_CORPUS"),
                    help="语料清单 JSON（技能目录**外面**那份）")
    ap.add_argument("--run", default=None, help="run 目录，默认 runs/")
    ap.add_argument("--baseline", default=None,
                    help="基线 run 目录，给出则 report 列出逐条差异")
    ap.add_argument("--only", default=None, help="只跑这些 slot，逗号分隔")
    ap.add_argument("--all", action="store_true", help="跑满全部 slot（贵）")
    ap.add_argument("--config", default="with_skill",
                    choices=["with_skill", "without_skill", "both"])
    ap.add_argument("--pair", action="append", default=None,
                    help="盲评成对：名字=A.pptx:B.pptx（可给多次）")
    ap.add_argument("--identifier", action="append", default=None,
                    help="脱敏要替换掉的标识符；也可用环境变量 BENCH_IDENTIFIERS")
    ap.add_argument("--expect", action="append", default=None,
                    help="盲评参照：名字=A（认为 A 那份更好）。没有它就判不了闸门")
    a = ap.parse_args()

    if a.cmd in ("blind-prep", "blind-grade"):
        # 盲评装置单搁一个文件 —— bench.py 已经一千多行，塞进来只会让人不敢改。
        sys.path.insert(0, HERE)
        import blind
        if not a.run:
            print("%s 要指定 run 目录：bench.py %s --run <run 目录>" % (a.cmd, a.cmd))
            return 2
        return blind.cmd_prep(a) if a.cmd == "blind-prep" else blind.cmd_grade(a)

    if a.cmd == "plan":
        return cmd_plan(a)
    if a.cmd == "grade":
        if not a.run:
            print("grade 要指定 run 目录：bench.py grade --run <run 目录>")
            return 2
        return cmd_grade(a)
    if a.cmd == "report":
        if not a.run:
            print("report 要指定 run 目录：bench.py report --run <run 目录>")
            return 2
        return cmd_report(a)

    if a.cmd == "list":
        for p in PROBES:
            mark = "  （--no-privacy 时不跑）" if p["id"] == "reg.privacy" else ""
            print("  %-18s %s%s" % (p["id"], p["text"], mark))
        return 0

    if a.out:
        os.environ["BENCH_TMP"] = a.out
        os.makedirs(a.out, exist_ok=True)

    skipped = []
    if a.no_privacy:
        skipped = [p for p in PROBES if p["id"] == "reg.privacy"]
        PROBES[:] = [p for p in PROBES if p["id"] != "reg.privacy"]

    print("回归层 —— %d 个探针" % len(PROBES))
    R = run_probes()
    n = summarize(R.items)

    # --no-privacy 抹掉的是一条检查，而「检查不在场」和「检查通过」在摘要里
    # 长得一模一样 —— 两种都是「没有 FAIL」。所以不能只把探针摘掉就完事：
    # 必须在结论**之后**再喊一次，让人翻到任何一页都知道这次少了哪一项。
    # 这条和 build_pptx 的「告警是提示不是错误」不冲突：那是判断，这是缺失。
    if skipped:
        print()
        print("!" * 64)
        for p in skipped:
            print("!! 未执行：%s —— %s" % (p["id"], p["text"]))
        print("!! --no-privacy：上面这份摘要里**没有**隐私这一项。")
        print("!! 「没有 FAIL」不等于「干净」—— 别把这次结果当作可发布的依据。")
        print("!" * 64)

    if a.out:
        gpath = os.path.join(a.out, "grading.json")
        # skipped 也要落盘。屏幕上的横幅关了终端就没了，而 grading.json 是
        # 要被下一次迭代、甚至被别人读的 —— 只留在 stdout 里，等于留给
        # 「后来翻文件的人」一个看起来一切正常的报告。
        with open(gpath, "w", encoding="utf-8") as f:
            json.dump({"layer": "regress",
                       "skipped": [{"id": p["id"], "text": p["text"],
                                    "why": "--no-privacy"} for p in skipped],
                       "records": R.items}, f, ensure_ascii=False, indent=2)
        print("\n→ %s" % gpath)

    # 坏掉的测试台必须是红的。not_run / error 与 fail 同等对待 ——
    # 「没跑」被读成「通过」正是本项目最怕的那件事。
    return 1 if (n[FAIL] or n[ERROR] or n[NOT_RUN]) else 0


if __name__ == "__main__":
    sys.exit(main())
