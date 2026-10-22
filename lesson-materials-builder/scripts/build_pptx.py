#!/usr/bin/env python3
"""课件.md → .pptx

用法:
    python build_pptx.py 课件.md -o 课件.pptx
    python build_pptx.py 课件.md -o 课件.pptx --template assets/base.pptx

语法见 references/slides-spec.md。渲染时会执行结构校验并打印告警；
告警不中断渲染 —— 有些页面确实需要破例，把判断权留给人比强行拦截有用。
"""

import argparse
import math
import os
import re
import sys

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.util import Emu, Inches, Pt

# Windows 控制台默认走 GBK，打印 ✓ 这类符号会抛 UnicodeEncodeError 而中断整个
# 渲染 —— 明明 pptx 已经写好了，却因为一行提示语前功尽弃。这里把输出流切到
# UTF-8；拿不到 reconfigure 的老解释器退化为替换不可编码字符，不再中断。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

# --------------------------------------------------------------------------
# 版式常量（与 references/slides-spec.md 的几何表一一对应）
# --------------------------------------------------------------------------
# 16:9 的精确宽度是 12192000 EMU。写成 13.333 会得到 12191695，差 305 EMU ——
# 肉眼看不出来，但成品套进任何标准 16:9 底版都会错位，而且 --template 的尺寸校验
# 又拿这个数当基准，等于给自己立了个错标准。所以按 EMU 定义，不写小数英寸。
EMU_PER_IN = 914400
SLIDE_W = 12192000 / EMU_PER_IN     # 13.33333…in，正好 16:9
SLIDE_H = 6858000 / EMU_PER_IN      # 7.5in
MARGIN_X = 0.76
CONTENT_W = SLIDE_W - 2 * MARGIN_X  # 11.8133…，与示例版心 11.81 一致

# 页标题与正文区的位置、高度都取自用户示例 PPT 的占位符实测值。
# 页脚删除后 BODY_BOTTOM 从 6.1 放到 6.85 —— 正文区因此比上一版高 20%~25%，
# 这是本轮版面改善的主要来源。
TITLE_Y, TITLE_H = 0.39, 0.79
BODY_Y = 1.42
BODY_BOTTOM = 6.85
MIN_BODY_H = 1.60                  # 底部堆叠区挤占后的正文下限（低于此值告警）

# 底部堆叠区（强调块 / 驱动问题）按行数动态算高。旧版四处各手算一遍且数值
# 与元素真实高度对不上（强调块高 0.7 却扣 0.85，驱动问题高 0.85 却只扣 0.75），
# 两者同时出现时问题框会压住强调块 0.1in。现在统一由 bottom_stack() 分配。
EMPH_PAD = 0.16                    # 强调块上下内边距合计
EMPH_LINE = 0.62                   # 32pt 一行的高度
QUESTION_LINE = 0.47               # 24pt 一行的高度
GAP_BLOCK = 0.18                   # 强调块与驱动问题之间

# 封面：70pt 单行标题比正文宽，给多一点边距和更高的位置
COVER_TITLE_Y, COVER_TITLE_H = 2.05, 2.30
COVER_SUB_Y = 4.70

# 字族按角色分：示例里标题走主题的 +mj-ea（微软雅黑），正文则在 run 上把
# a:latin 与 a:ea 都硬编码成华文中宋。照搬这个分工 —— 西文与数学变量也跟着
# 正文走华文中宋，和示例一致，不另设 Times New Roman。
# 显式写死而不是靠继承：换 --template 底版时主题中文字体会变，而字体是契约。
FONT_TITLE = "微软雅黑"
FONT_BODY = "华文中宋"

SIZE_COVER, SIZE_COVER_LONG, SIZE_COVER_XLONG = 70, 54, 44
COVER_SHORT_CHARS, COVER_LONG_CHARS = 10, 14
SIZE_TITLE = 32
SIZE_BODY = 28
SIZE_SUB = 24
SIZE_SUB_MIN = 20                  # 二级要点字号下限
SUB_RATIO = SIZE_SUB / SIZE_BODY   # 二级/一级 = 0.857
SIZE_EMPH = 32                     # 结论句（!!!）唯一的渲染字号
SIZE_QUESTION = 24
SIZE_DETAIL = 16
SIZE_CAPTION = 20                  # 流程页图下的说明文字

COLOR = {
    "title": "1A202C",
    "body": "2D3748",
    "emph": "C05621",
    "question": "2B6CB0",
    "aux": "718096",
    "accent": "2B6CB0",
    "emph_bg": "FEF3E2",
    # 与 make_figures.py 的 C["main"] 同值：图里的主曲线和版面上的流程箭头
    # 同色，是"同一套视觉语言"最省力的达成方式。
    "arrow": "2B6CB0",
}

# 需要配图的"概念建构段"版式。封面/重点/阐述属结论段，不要求配图。
CONSTRUCT_LAYOUTS = {"标题", "两栏", "纯图", "流程"}
LAYOUTS = {"封面", "标题", "两栏", "重点", "纯图", "流程", "阐述", "例题"}
# 这几个版式的渲染函数根本不读图片。作者在它们上面写 !img: 时，图会**无声消失** ——
# 渲染不出来的东西最危险，因为没有任何迹象提示"这里本来该有张图"。
# 所以 validate 必须专门为它们报一条，不能只靠"多图只渲染第 1 张"那条兜底。
NO_IMAGE_LAYOUTS = {"封面", "重点", "阐述"}
# 同一类问题的另一面：这两个版式从不调用 render_bottom_stack，写在它们上面的
# !ans: 会整段消失，而且因为答案本来就是"点一下才出现"，用户不会觉得少了东西。
NO_ANSWER_LAYOUTS = {"封面", "阐述"}

# [分步] 是本轮之前的版式名（同一过程拆成 N 张幻灯片）。现在渲染成单页流程，
# 保留别名让已经写好的 md 不必返工，同时在 validate 里提示改名。
LAYOUT_ALIAS = {"分步": "流程"}

# 两阶段自适应填充的参数。用户的要求是「可以适当调整字号，也可以通过多个换行
# 或者调整行间距来进行调整」，所以不做硬性居中，而是让文字块长到接近填满正文区。
#
# 字号阶梯上限取 30 而不是 32：页标题与强调块都是 32pt，正文若也到 32pt，
# 稀疏页上正文与标题同号，层级就只剩"加粗 + 颜色 + 位置"三种弱区分了。
SIZE_LADDER = (SIZE_BODY, 30)
FILL_TRIGGER = 0.58                # 占用率低于此值才启动填充
FILL_TARGET = 0.82                 # 填充目标：文字块高 / 正文区高
FILL_CEIL = 0.94                   # 硬上限：任何组合不得越过
SPARSE_WARN = 0.35                 # 拉满仍低于此值 → 告警"内容偏少"
LINE_SPACING = 1.30                # 基准行高倍数
SA_BASE = 10.0                     # 基准段后距 pt（对应 28pt 字号）
SA_MAX = 26.0                      # 段后距上限 pt
LS_MAX = 1.60                      # 行距上限
SUB_SPACE_RATIO = 0.40             # 二级要点段后距 = 一级 × 0.4

# 图片版式的分界：宽高比 < 1.5 的（竖幅/方形）并到文字右侧，>= 1.5 的横幅
# 上图下文占满版心。两种情况都水平居中。
IMAGE_AR_SPLIT = 1.5
COL_GAP = 0.35                     # 并排时文字列与图列的间隙
TEXT_COL_FRAC = (0.34, 0.56)       # 文字列宽占版心的夹取区间
IMG_TOP_FRACTION = 0.62            # 上图下文时图最多占正文区高度
IMG_TEXT_GAP = 0.28
MIN_IMG_H = 1.20                   # 图区低于此值告警
COL_STACK_GAP = 0.18               # [两栏] 同栏文字与图的间距
PLACEHOLDER_W, PLACEHOLDER_H = 3.20, 2.40

# [例题] 版式：题干贴顶，配图挂在题干下方偏右，**左下留白**给解答或老师的手写。
# 留白占比 0.60 是用户选定的（左六成）。这块地方是故意空着的，所以渲染器
# 在这里不跑 fit_block —— 那个函数的职责恰好是"把文字撑满可用高度"，方向相反。
EXAMPLE_LAYOUT = "例题"
EXAMPLE_SCRATCH_FRAC = 0.60        # 题干下方左侧留白占版心宽的比例
EXAMPLE_STMT_GAP = 0.30            # 题干与下方图文区的间距

# [流程] 版式：箭头宽与占位。图宽是按"着墨区等比"分出来的，箭头占得越宽留给图的
# 就越少，所以图排不开时逐档换更小的箭头。
FLOW_ARROW_LADDER = ((0.34, 0.12), (0.28, 0.08), (0.22, 0.05))
FLOW_ARROW_H = 0.30
FLOW_CAPTION_GAP = 0.12
FLOW_MAX_STEPS = 4
# 统一比例后图形的着墨高度低于此值，说明这组图的形状差异已经大到排不开了
FLOW_MIN_INK_H = 1.20
INK_WHITE_TOL = 12                 # 判定"白边"的灰度阈值（0–255）

# 收束类页面天然无需配图 —— 样本 PPT 里「实践探究」「课堂小结」「作业布置」
# 三页均为零图，这是常态而非疏漏。中学课件的这类页面用词相当固定，
# 所以用标题关键词识别它们，避免把正常版面误报成缺陷。
CONCLUSION_KEYWORDS = ("小结", "总结", "作业", "布置", "练习", "探究",
                       "回顾", "反思", "升华", "拓展", "板书")

BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

# 受高度模型约束的文本框都取这个名字，便于 check_spacing_written 只查它们。
# 标题、封面副标题不参与填充，也就没有这一约束。
BODY_BLOCK = "body-block"

# 答案块（!ans:）的固定形状名。build() 渲染完之后靠它找到"要挂点击动画"的那个
# 形状 —— 与 BODY_BLOCK 同一套路（见 check_spacing_written）。名字保持纯 ASCII：
# 验证用的 .ps1 是 ANSI 读入的，只能拿 ASCII 字面量去断言它。
ANSWER_BLOCK = "answer-block"

# 底部堆叠区另外两块。上面那句注释原先把驱动问题写成「单行元素，不参与填充」——
# **那是错的**，`question_height()` 明明按 QUESTION_LINE 逐行算它的高度，
# 强调块同理（`emph_height()`）。错在注释，后果是本文件的两套行距校验都把
# 这两块漏掉了：它们各自手搓形状、不走 layout_block，于是谁也不给它们写 spcPts，
# 渲染出来的行高由字体自然行高决定 —— 模型说这个块多高，实际是另一个高度。
# 产出层第一次真跑时就撞上了：折成两行的 `!!!` 必报「行距未显式指定」，
# 而作者从 课件.md 里**改不掉**，只能把句子压成一行（那是绕过内容，不是修好）。
EMPH_BLOCK = "emph-block"
QUESTION_BLOCK = "question-block"


def is_conclusion_page(page):
    return any(k in page.title for k in CONCLUSION_KEYWORDS)


# --------------------------------------------------------------------------
# 高度模型：估算与渲染必须用同一个公式
# --------------------------------------------------------------------------
#
# 这一节是本文件的"度量衡"。版面填充要靠"这段文字有多高"来做决定，所以估值
# 不能只是保守猜测 —— 它必须与真正写进 XML 的行距、段后距逐项对得上，否则
# 填出来的版面与预期不符，而且换底版后还会再变一次。
#
# 关键约束：p.line_spacing 必须传 Pt(...) 而不是浮点倍数。浮点会序列化成
# <a:spcPct val="130000"/>，那是"字体自然行高的 130%" —— 各字体的自然行高
# 不同，模型立刻失真。Pt() 写成 <a:spcPts val="3640"/>，是绝对值。

def line_h(size, line_spacing=LINE_SPACING):
    """一行文字的高度（英寸）。与写入 XML 的 spcPts 同源。"""
    return size * line_spacing / 72.0


def sub_size(size):
    """二级要点字号。

    下限不能直接取 SIZE_SUB_MIN —— 阐述页的正文是 16pt，min(20, 16) 会得到
    20pt，二级比一级还大。所以下限本身也要被 size - 2 夹住。
    """
    floor = min(SIZE_SUB_MIN, size - 2)
    return max(floor, int(round(size * SUB_RATIO)))


def default_space_after(size):
    return SA_BASE * size / SIZE_BODY


def _line_count(text, width_in, size):
    """折行数。按「每个字符都占一个全角宽」估，对西文偏保守，方向安全。"""
    plain = BOLD_RE.sub(r"\1", text or "")
    per_line = max(int(width_in * 72 / size), 1)
    return max(1, math.ceil(len(plain) / per_line))


def emph_height(text, width_in=CONTENT_W):
    return EMPH_PAD + _line_count(text, width_in, SIZE_EMPH) * EMPH_LINE


def question_height(text, width_in=CONTENT_W):
    return _line_count(text, width_in, SIZE_QUESTION) * QUESTION_LINE


def answer_in_stack(page):
    """答案块是否归底部堆叠区管。

    [例题] 的答案摆在题干下方的左下留白里 —— 那块留白正是这个版式存在的理由；
    其余版式没有留白区，答案就与强调块、驱动问题一起在页面底部往下排。
    """
    return page.layout != EXAMPLE_LAYOUT


def answer_height(texts, width_in=CONTENT_W):
    """答案块的高度（英寸）。按 sub_size(SIZE_BODY) 算 —— 它比题干小一号。

    走 text_height 而不是自己数行，是沿用本文件"估算与渲染必须同一个公式"的
    约定：add_answer 写进 XML 的 lnSpc/spcAft 就是这几个参数。
    """
    sz = sub_size(SIZE_BODY)
    return text_height([(0, t) for t in texts], width_in, size=sz,
                       space_after=default_space_after(sz))


def bottom_stack_height(page):
    h = 0.0
    if page.emph:
        h += emph_height(page.emph)
    if page.question:
        if page.emph:
            h += GAP_BLOCK
        h += question_height(page.question)
    # 答案排在最后，也就是视觉上的最下方：先看到结论，再看到问题，最后点出答案。
    if page.answers and answer_in_stack(page):
        if h:
            h += GAP_BLOCK
        h += answer_height(page.answers)
    return h


def body_zone(page):
    """任何版式的正文区都从这里取：(body_y, body_h, stack_top, warn)。

    正文盒底与堆叠区顶严格相等，所以只要正文实际渲染高度不超过 body_h 就
    不会重叠 —— 这一点由溢出告警兜底。
    """
    stack_h = bottom_stack_height(page)
    raw_h = BODY_BOTTOM - stack_h - BODY_Y
    warn = None
    if raw_h < MIN_BODY_H:
        warn = (f"底部强调块/驱动问题占 {stack_h:.1f}in，正文区仅剩 "
                f"{raw_h:.1f}in，建议移到下一页")
    return BODY_Y, max(raw_h, MIN_BODY_H), BODY_BOTTOM - stack_h, warn


def text_height(items, width_in, size=SIZE_BODY, sub=None,
                space_after=None, line_spacing=LINE_SPACING,
                include_trailing=True):
    """一组要点渲染后的高度（英寸）。

    与 layout_block 写入的 lnSpc/spcAft 一一对应，因此这不是"保守估计"而是
    "同一公式的复算"，差异只来自折行数。

    include_trailing：最后一段的段后距在 PowerPoint 里是否计入文本框所需高度，
    各家实现不一致。溢出检测用 True（保守）；填充求解用 False，否则单要点页
    会解出一个永远看不见的巨大段后距。
    """
    sub = sub if sub is not None else sub_size(size)
    sa = space_after if space_after is not None else default_space_after(size)
    total = 0.0
    for i, (level, text) in enumerate(items):
        sz = size if level == 0 else sub
        total += _line_count(text, width_in, sz) * line_h(sz, line_spacing)
        if include_trailing or i < len(items) - 1:
            total += (sa if level == 0 else sa * SUB_SPACE_RATIO) / 72.0
    return total


def fit_block(items, width_in, avail_h, base=SIZE_BODY, allow_fill=True,
              allow_resize=True):
    """两阶段自适应填充，返回 (size, sub, space_after, line_spacing, height)。

    阶段 1：在 SIZE_LADDER 里挑字号，占用率不超 FILL_CEIL 的前提下尽量大。
    阶段 2a：固定字号，反解段后距使块高达到目标。
    阶段 2b：段后距到顶仍不足，反解行距撑开每一行。

    先把高度拆成 height = H_lines + sa·A（A = 每 1pt 段后距贡献的英寸数），
    两个阶段都能精确反解，不必迭代逼近。

    allow_resize=False 用于字号由版式定死的页（[阐述] 的 16pt 细则）：那样
    调用方只取间距，若阶段 1 仍把 base 提到 28pt，反解出的间距就是按 28pt 算
    的，套回 16pt 上必然不对。

    为什么不加空行：空行是硬的，改一个要点就要重数；段后距是段落属性，
    增删要点后自动重新均摊。用户要的"多个换行"由此实现，效果等价但可维护。
    """
    if not items:
        return base, sub_size(base), default_space_after(base), LINE_SPACING, 0.0

    sub, sa, ls = sub_size(base), default_space_after(base), LINE_SPACING
    h = text_height(items, width_in, base, sub, sa, ls)
    best = (base, sub, sa, ls, h)

    # 已经够满、或者本来就溢出 → 绝不对溢出页二次加害
    if not allow_fill or avail_h <= 0 or h / avail_h >= FILL_TRIGGER:
        return best

    goal = avail_h * FILL_TARGET

    def split_terms(size, sub_, ls_):
        """(行高合计, 每 1pt 段后距贡献的英寸)——只统计段间空隙。"""
        h_lines, weight = 0.0, 0.0
        for i, (level, text) in enumerate(items):
            sz = size if level == 0 else sub_
            h_lines += _line_count(text, width_in, sz) * line_h(sz, ls_)
            if i < len(items) - 1:
                weight += 1.0 if level == 0 else SUB_SPACE_RATIO
        return h_lines, weight / 72.0

    # ---- 阶段 1：字号 ----
    for cand in (SIZE_LADDER if allow_resize else ()):
        if cand <= base:
            continue
        s2, sa2 = sub_size(cand), default_space_after(cand)
        h2 = text_height(items, width_in, cand, s2, sa2, LINE_SPACING)
        if h2 > avail_h * FILL_CEIL:      # text_height 对 size 单调，可以停
            break
        best = (cand, s2, sa2, LINE_SPACING, h2)
        if h2 >= goal:
            return best

    # ---- 阶段 2a：段后距（反解）----
    size, sub_, sa_, ls_, _ = best
    h_lines, A = split_terms(size, sub_, ls_)
    if A > 1e-9 and h_lines < goal:
        sa2 = max(min((goal - h_lines) / A, SA_MAX), sa_)
        best = (size, sub_, sa2, ls_, h_lines + sa2 * A)
        if best[4] >= goal:
            return best

    # ---- 阶段 2b：行距（反解）----
    size, sub_, sa_, ls_, _ = best
    B = sum(_line_count(t, width_in, size if lvl == 0 else sub_) *
            (size if lvl == 0 else sub_) / 72.0 for lvl, t in items)
    _, A = split_terms(size, sub_, ls_)
    if B > 1e-9:
        ls2 = min(max((goal - sa_ * A) / B, ls_), LS_MAX)
        if ls2 > ls_:
            best = (size, sub_, sa_, ls2, B * ls2 + sa_ * A)

    # ---- 硬护栏（防御性，理论上到不了）----
    if best[4] > avail_h * FILL_CEIL:
        best = (base, sub_size(base), default_space_after(base), LINE_SPACING,
                text_height(items, width_in, base))
    return best


# --------------------------------------------------------------------------
# 解析
# --------------------------------------------------------------------------

class Page:
    def __init__(self, layout, title):
        self.layout = layout
        self.title = title
        self.bullets = []      # [(level, text)]
        self.emph = None       # 强调块文字
        self.question = None   # 驱动问题
        self.answers = []      # 答案块的段落（放映时点击才出现）
        self.answer_blank = 0  # 写了 !ans: 但没写内容的行数
        self.images = []       # [(path, h, w)]
        self.steps = []        # [(path, caption)]
        self.left = []         # 两栏左侧 (level, text)
        self.right = []        # 两栏右侧
        self.left_img = None
        self.right_img = None
        self.exempt_no_image = False
        self.emph_extra = 0    # 被降级的重复强调块数（每页最多一个）
        self.raw_line = 0

    @property
    def has_image(self):
        return bool(self.images or self.steps or self.left_img or self.right_img)


def _split_frontmatter(text):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip("\"'")
    return meta, text[m.end():]


IMG_RE = re.compile(r"^!img:\s*(\S+)(.*)$")
ANSWER_RE = re.compile(r"^!ans:\s*(.*)$")
STEP_RE = re.compile(r"^\d+\.\s*!img:\s*(\S+)\s*(?:\|\s*(.*))?$")
HEAD_RE = re.compile(r"^#\s*(?:\[([^\]]+)\]\s*)?(.*)$")
BULLET_RE = re.compile(r"^(\s*)-\s+(.*)$")


def _parse_size_opts(rest):
    h = w = None
    for m in re.finditer(r"\b([hw])\s*=\s*([\d.]+)", rest or ""):
        if m.group(1) == "h":
            h = float(m.group(2))
        else:
            w = float(m.group(2))
    return h, w


def parse(text):
    meta, body = _split_frontmatter(text)
    pages = []
    cur = None
    section = None      # 'left' | 'right' | None

    for i, raw in enumerate(body.splitlines(), 1):
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            continue

        # 页级注释
        if stripped.startswith("<!--"):
            note = stripped.strip("<!->").strip()
            if "允许无图" in note and cur:
                cur.exempt_no_image = True
            continue

        m = HEAD_RE.match(stripped)
        if m and stripped.startswith("# ") and not stripped.startswith("## "):
            layout = (m.group(1) or "标题").strip() or "标题"
            cur = Page(layout, m.group(2).strip())
            cur.raw_line = i
            pages.append(cur)
            section = None
            continue

        if cur is None:
            continue

        # 两栏分节
        if stripped in ("## 左", "## 右", "## left", "## right"):
            section = "left" if "左" in stripped or "left" in stripped else "right"
            continue

        sm = STEP_RE.match(stripped)
        if sm:
            cur.steps.append((sm.group(1), (sm.group(2) or "").strip()))
            continue

        if stripped.startswith("!!!"):
            value = stripped[3:].strip()
            if cur.emph:      # 保留第一个，后面的降级为要点
                cur.emph_extra += 1
                cur.bullets.append((0, value))
            else:
                cur.emph = value
            continue

        if stripped.startswith(">"):
            cur.question = stripped[1:].strip()
            continue

        # 答案块。多行 !ans: 合成**一个**块（同一次点击一起出现），
        # 所以这里只是往同一个列表里追加段落，不新建元素。
        am = ANSWER_RE.match(stripped)
        if am:
            value = am.group(1).strip()
            if value:
                cur.answers.append(value)
            else:
                cur.answer_blank += 1      # 空的 !ans: 什么都不画，得报出来
            continue

        im = IMG_RE.match(stripped)
        if im:
            h, w = _parse_size_opts(im.group(2))
            if section == "left" and cur.left_img is None:
                cur.left_img = (im.group(1), h, w)
            elif section == "right" and cur.right_img is None:
                cur.right_img = (im.group(1), h, w)
            else:
                cur.images.append((im.group(1), h, w))
            continue

        bm = BULLET_RE.match(line)
        if bm:
            level = 1 if len(bm.group(1)) >= 2 else 0
            item = (level, bm.group(2).strip())
            if section == "left":
                cur.left.append(item)
            elif section == "right":
                cur.right.append(item)
            else:
                cur.bullets.append(item)
            continue

        # 其余裸文本按要点处理（封面副标题等）
        if section == "left":
            cur.left.append((0, stripped))
        elif section == "right":
            cur.right.append((0, stripped))
        else:
            cur.bullets.append((0, stripped))

    return meta, pages


# --------------------------------------------------------------------------
# 渲染工具
# --------------------------------------------------------------------------

def set_run_font(run, size, bold=False, color=None, face=None):
    """同时设置西文与中文字形。

    python-pptx 的 font.name 只写 a:latin，中文会退回主题默认字体。
    中文要落到 a:ea 上才会生效，否则「微软雅黑」的设定对汉字无效。
    """
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor.from_string(color)

    face = face or FONT_BODY
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = rPr.makeelement(qn(tag), {})
            rPr.append(el)
        el.set("typeface", face)


def add_rich(para, text, size, base_color, bold_all=False, face=None):
    """写入一段文字，解析 **加粗**。加粗部分用强调色，形成视觉落点。"""
    face = face or FONT_BODY
    pos = 0
    for m in BOLD_RE.finditer(text):
        if m.start() > pos:
            r = para.add_run()
            r.text = text[pos:m.start()]
            set_run_font(r, size, bold_all, base_color, face)
        r = para.add_run()
        r.text = m.group(1)
        set_run_font(r, size, True, COLOR["accent"], face)
        pos = m.end()
    if pos < len(text):
        r = para.add_run()
        r.text = text[pos:]
        set_run_font(r, size, bold_all, base_color, face)
    if not text:
        r = para.add_run()
        r.text = ""
        set_run_font(r, size, bold_all, base_color, face)


def textbox(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    # 底版可能带 <a:normAutofit>，那样 PowerPoint 会在显示时悄悄缩小文字，
    # 而高度模型毫不知情 —— 整个填充算法随即失效。显式关掉。
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    return tf


def image_aspect(path):
    """图的宽高比 w/h。缺图或坏图返回 1.0，调用方退化为默认版式。"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size[0] / im.size[1]
    except Exception:
        return 1.0


def measure_image(path, max_w, max_h, h=None, w=None):
    """把图缩放进 [max_w × max_h] 并保持长宽比。

    返回 (dw, dh, warn)。单独成函数是因为版式要先知道图占多大，才能决定
    文字该给多少宽 —— 判完再画，不能边画边判。
    """
    try:
        from PIL import Image
        with Image.open(path) as im:
            iw, ih = im.size
        ratio = ih / iw
        warn = None
    except Exception:
        # 坏图不许中断整份渲染，与"缺图插占位框"同一原则
        warn = f"读图失败 {path}"
        ratio = PLACEHOLDER_H / PLACEHOLDER_W

    if h and w:
        dw, dh = w, h
    elif h:
        dh, dw = h, h / ratio
    elif w:
        dw, dh = w, w * ratio
    else:
        dw, dh = max_w, max_w * ratio

    # 等比夹取。旧版对 dw、dh 各夹各的 —— 写了 h=4.2 而 4.2/aspect > max_w 时
    # 只有 dw 被削、dh 不变，图被横向压扁。
    scale = min(1.0, max_w / dw, max_h / dh)
    return dw * scale, dh * scale, warn


def _place(x, y, dw, dh, max_w, max_h, center_h, center_v):
    px = x + (max_w - dw) / 2.0 if center_h else x
    py = y + (max_h - dh) / 2.0 if center_v else y
    return px, py


def add_image(slide, path, x, y, max_w, max_h, h=None, w=None,
              center_h=True, center_v=False, crop=None):
    """插图。缺图时插占位框而非中断 —— 先看到整体结构比渲染失败有用。

    居中范围是 [x, x+max_w] 这个"容器"，不是整页。容器的 max_w 天然就是各处
    调用想要的范围（并排时的图栏、两栏时的本栏、纯图时的版心、流程时的单格），
    所以一处偏移就覆盖了全部版式 —— 上一版图一律左贴，空白全堆在右侧。

    center_v 默认关闭：并排与上图下文里的图是跟着文字走的，垂直居中会把图
    推离文字。只有 [纯图]、[流程] 这类图独立占区的版式才打开。

    crop：可选 (l, t, r, b)，各为相对源图的裁切比例，用来先裁掉四周白边再摆。
    裁切是"源图裁掉多少"，显示尺寸仍由 dw×dh 决定 —— 所以传 crop 时必须同时
    给出 w 和 h，否则量的还是整张画布的宽高比，白边一裁就变形。
    """
    dw, dh, warn = measure_image(path, max_w, max_h, h, w)
    px, py = _place(x, y, dw, dh, max_w, max_h, center_h, center_v)

    if warn:
        # 占位框走同一套定位（且尺寸取一张"假图"，不占满整栏）—— 否则缺图处
        # 会突然出现一个不居中的大灰块，比缺图本身更刺眼。
        box = slide.shapes.add_shape(1, Inches(px), Inches(py),
                                     Inches(dw), Inches(dh))
        box.fill.solid()
        box.fill.fore_color.rgb = RGBColor.from_string("EDF2F7")
        box.line.color.rgb = RGBColor.from_string("A0AEC0")
        box.shadow.inherit = False
        tf = box.text_frame
        tf.text = f"缺图: {os.path.basename(path)}"
        tf.paragraphs[0].runs[0].font.size = Pt(14)
        tf.paragraphs[0].runs[0].font.color.rgb = RGBColor.from_string("718096")
        return None, warn

    pic = slide.shapes.add_picture(path, Inches(px), Inches(py),
                                   Inches(dw), Inches(dh))
    if crop:
        l, t, r, b = crop
        # 夹到 [0, 1)：源图裁没了 PowerPoint 会直接报文件损坏
        pic.crop_left, pic.crop_top = max(0.0, min(l, 0.98)), max(0.0, min(t, 0.98))
        pic.crop_right, pic.crop_bottom = max(0.0, min(r, 0.98)), max(0.0, min(b, 0.98))
    return pic, None


def add_title(slide, text, size=SIZE_TITLE):
    tf = textbox(slide, MARGIN_X, TITLE_Y, CONTENT_W, TITLE_H,
                 anchor=MSO_ANCHOR.MIDDLE)
    add_rich(tf.paragraphs[0], text, size, COLOR["title"], bold_all=True,
             face=FONT_TITLE)


def layout_block(slide, items, x, y, w, h, size=SIZE_BODY, sub=None,
                 space_after=None, line_spacing=LINE_SPACING, center=True,
                 name=BODY_BLOCK):
    """在 [y, y+h] 里放一个要点块。返回 (tf, need, bottom)。

    center=True 时按着墨高度反算 top（内容不足则垂直居中）；装不下时贴顶、向下
    溢出，交给告警处理。返回值里的 need 含最后一段的段后距，[两栏] 靠它定位同栏
    图片 —— 图片本来就该从文字块的"框底"往下排，用着墨高度反而会挤上来。
    """
    sub = sub if sub is not None else sub_size(size)
    sa = space_after if space_after is not None else default_space_after(size)
    need = text_height(items, w, size, sub=sub, space_after=sa,
                       line_spacing=line_spacing, include_trailing=True)

    box_h = need * 1.04 + 0.06          # 留 4% 余量，免得 PowerPoint 裁掉半行

    # 居中要按**着墨高度**算，不能按 need 或 box_h。两者都含最后一段的段后距与
    # 底部余量，而那是纯空白 —— 按它们居中会把整块文字凭空抬高
    # (段后距 + 余量)/2，实测每页偏上 0.15~0.19in。填充算法把段后距拉到 26pt 时
    # 偏差最大，恰好是留白最刺眼的那几页。
    last_level = items[-1][0] if items else 0
    trailing = (sa if last_level == 0 else sa * SUB_SPACE_RATIO) / 72.0
    ink = max(need - trailing, 0.0)
    top = y + max(0.0, (h - ink) / 2.0) if center else y

    box = slide.shapes.add_textbox(Inches(x), Inches(top), Inches(w),
                                   Inches(box_h))
    # name 供 check_spacing_written 识别"受高度模型约束"的块；答案块取
    # ANSWER_BLOCK，好让 build() 渲染完之后认得出该给谁挂点击动画。
    box.name = name
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0

    for i, (level, text) in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        sz = size if level == 0 else sub
        # 必须用 Pt()：浮点会写成 spcPct（字体自然行高的百分比），各字体不等，
        # 而高度模型算的是绝对值。见本文件"高度模型"一节的说明。
        p.line_spacing = Pt(line_h(sz, line_spacing) * 72)
        p.space_after = Pt(sa if level == 0 else sa * SUB_SPACE_RATIO)
        if level > 0:
            r = p.add_run()
            r.text = "· "
            set_run_font(r, sz, False, COLOR["aux"])
        add_rich(p, text, sz, COLOR["body"])

    return tf, need, top + box_h


def add_emph(slide, text, y, height=None):
    height = height or emph_height(text)
    box = slide.shapes.add_shape(1, Inches(MARGIN_X), Inches(y),
                                 Inches(CONTENT_W), Inches(height))
    box.fill.solid()
    box.fill.fore_color.rgb = RGBColor.from_string(COLOR["emph_bg"])
    box.line.fill.background()
    box.shadow.inherit = False
    box.name = EMPH_BLOCK
    tf = box.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    add_rich(tf.paragraphs[0], text, SIZE_EMPH, COLOR["emph"], bold_all=True)
    # 行距必须显式写死，且**就用 emph_height() 算高度时用的那个常量**。
    # 框高是按 EMPH_LINE 算的，行距若交给字体的自然行高，两者就对不上：
    # 框比内容矮就压字，比内容高就白留一截。中间对齐只是把误差藏起来，
    # 不是消掉它。
    tf.paragraphs[0].line_spacing = Pt(EMPH_LINE * 72)
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    return box


def add_question(slide, text, y, height=None):
    height = height or question_height(text)
    tf = textbox(slide, MARGIN_X, y, CONTENT_W, height,
                 anchor=MSO_ANCHOR.MIDDLE)
    # 与 add_emph 同一条理由：高度按 QUESTION_LINE 算的，行距就得写同一个数。
    tf._parent.name = QUESTION_BLOCK
    add_rich(tf.paragraphs[0], text, SIZE_QUESTION, COLOR["question"])
    tf.paragraphs[0].line_spacing = Pt(QUESTION_LINE * 72)
    return tf


def add_answer(slide, texts, x, y, w, h):
    """答案块。段落连成一个文本框 —— 放映时由**一次**点击整体显现。

    刻意不上任何颜色，正文色即可，有两层理由：

    - [例题] 里它落在左下留白区，那里本来就该看着像"写上去的"，不像贴上去的；
    - 其它版式里它与强调块可能同页。若也取强调块的橙，一页就有两处橙，
      强调块作为"本页要得出的那句话"的分量就被摊薄了。

    驱动问题是蓝、强调块是橙、答案是正文色 —— 三者分量依次递减，正是它们
    在这页上的从属关系。答案的"出现"本身就是醒目事件（一次点击），不需要
    再靠颜色重复强调一次。

    字号用 allow_resize=False 钉在"比题干小一号"（24pt）：允许它涨到 30pt
    会把层级搞反，解答不该比题干还大声。

    center=False（贴顶）是刻意的：解答该紧接着题干往下读。若在留白区里垂直居中，
    题干与解答之间会空出一截，看着像两件不相干的东西；贴顶则读成"题目下面就是解"，
    余下的空白自然成了"还可以往下写"的地方。

    每段一个段落、共用一个文本框，是为了动画 —— 见 apply_click_animations：
    它按形状名找到这个块，挂**一个**单击效果，整块一次显现。
    """
    items = [(0, t) for t in texts]
    base = sub_size(SIZE_BODY)
    blk = fit_block(items, w, h, base=base, allow_resize=False)
    return layout_block(slide, items, x, y, w, h, size=blk[0], sub=blk[1],
                        space_after=blk[2], line_spacing=blk[3], center=False,
                        name=ANSWER_BLOCK)


def render_bottom_stack(slide, page):
    """在正文元素之后调用。所有版式共用这一处，正文区高度与元素高度才对得上。

    自下而上的高度来自 bottom_stack_height，这里的 y 递推必须与它逐项对齐 ——
    所以每个 y += 后面的条件都写成"后面还有没有块"，而不是照抄某个固定顺序。
    """
    y = BODY_BOTTOM - bottom_stack_height(page)
    has_answer = bool(page.answers) and answer_in_stack(page)
    if page.emph:
        h = emph_height(page.emph)
        add_emph(slide, page.emph, y, h)
        y += h + (GAP_BLOCK if (page.question or has_answer) else 0)
    if page.question:
        h = question_height(page.question)
        add_question(slide, page.question, y, h)
        y += h + (GAP_BLOCK if has_answer else 0)
    if has_answer:
        add_answer(slide, page.answers, MARGIN_X, y, CONTENT_W,
                   answer_height(page.answers))
    return y


# --------------------------------------------------------------------------
# 版式渲染
# --------------------------------------------------------------------------

def render_cover(slide, page, meta):
    n = len(page.title)
    if n <= COVER_SHORT_CHARS:
        size = SIZE_COVER
    elif n <= COVER_LONG_CHARS:
        size = SIZE_COVER_LONG
    else:
        size = SIZE_COVER_XLONG
    tf = textbox(slide, MARGIN_X, COVER_TITLE_Y, CONTENT_W, COVER_TITLE_H,
                 anchor=MSO_ANCHOR.MIDDLE)
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    add_rich(tf.paragraphs[0], page.title, size, COLOR["title"], bold_all=True,
             face=FONT_TITLE)

    # 封面正文优先。只有封面自身没写副标题行时才用 frontmatter 的 subtitle，
    # 否则两处都写「讲师：XXX」时会在封面上重复出现。
    lines = [t for _, t in page.bullets]
    sub = meta.get("subtitle") or ""
    if sub and sub not in lines:
        lines.insert(0, sub)
    if lines:
        tf2 = textbox(slide, MARGIN_X, COVER_SUB_Y, CONTENT_W, 1.3)
        for i, t in enumerate(lines):
            p = tf2.paragraphs[0] if i == 0 else tf2.add_paragraph()
            p.alignment = PP_ALIGN.CENTER
            add_rich(p, t, SIZE_SUB, COLOR["aux"])


def _fill_hint(blk, avail):
    """填充结果的一句话摘要，附在告警里，便于判断是字号还是间距撑爆的。"""
    return (f"字号 {blk[0]}pt / 段距 {blk[2]:.0f}pt / 行距 {blk[3]:.2f}"
            f"〔占正文区 {blk[4] / avail * 100:.0f}%〕")


def _overflow_warn(blk, avail, where=""):
    return (f"{where}文字估算 {blk[4]:.1f}in > 可用 {avail:.1f}in"
            f"（{_fill_hint(blk, avail)}），可能溢出 ——\n"
            f"      正确反应是拆页，不是调小字号")


def render_generic(slide, page, meta):
    """[标题] 版式。按图的宽高比分派：竖幅并排，横幅上图下文。"""
    add_title(slide, page.title)
    body_y, body_h, _, warn = body_zone(page)
    warns = [warn] if warn else []

    if len(page.images) > 1:
        warns.append(f"本页 {len(page.images)} 张图，仅渲染第 1 张；"
                     f"多图请用 [流程] 或 [两栏]")

    img = page.images[0] if page.images else None
    ar = image_aspect(img[0]) if img else 0

    if img and ar >= IMAGE_AR_SPLIT:
        # 横幅：上图下文，图占满版心
        path, h, w = img
        dw, dh, mw = measure_image(path, CONTENT_W, body_h * IMG_TOP_FRACTION, h, w)
        if mw:
            warns.append(mw)
        text_avail = body_h - dh - IMG_TEXT_GAP
        blk = fit_block(page.bullets, CONTENT_W, max(text_avail, 0),
                        allow_fill=text_avail >= 1.4)
        if blk[4] > max(text_avail, 0):
            warns.append(_overflow_warn(blk, max(text_avail, 0)))
        add_image(slide, path, MARGIN_X, body_y, CONTENT_W,
                  body_h * IMG_TOP_FRACTION, h, w)
        layout_block(slide, page.bullets, MARGIN_X, body_y + dh + IMG_TEXT_GAP,
                     CONTENT_W, max(text_avail, 0.4), size=blk[0], sub=blk[1],
                     space_after=blk[2], line_spacing=blk[3])

    elif img:
        # 竖幅/方形：左文右图。文字列宽由图的长宽比反推并夹取，
        # 免得极瘦的图占满整栏、文字被挤成一条。
        frac = min(max(1.0 - ar / 1.6, TEXT_COL_FRAC[0]), TEXT_COL_FRAC[1])
        text_w = CONTENT_W * frac
        img_x = MARGIN_X + text_w + COL_GAP
        img_w = CONTENT_W - text_w - COL_GAP

        blk = fit_block(page.bullets, text_w, body_h)
        if blk[4] > body_h:
            warns.append(_overflow_warn(blk, body_h))
        layout_block(slide, page.bullets, MARGIN_X, body_y, text_w, body_h,
                     size=blk[0], sub=blk[1], space_after=blk[2],
                     line_spacing=blk[3])
        path, h, w = img
        _, mw = add_image(slide, path, img_x, body_y, img_w, body_h, h, w,
                          center_v=True)
        if mw:
            warns.append(mw)

    else:
        blk = fit_block(page.bullets, CONTENT_W, body_h)
        if blk[4] > body_h:
            warns.append(_overflow_warn(blk, body_h))
        elif blk[4] / body_h < SPARSE_WARN and not (page.question or page.emph):
            # 带驱动问题/结论句的页不算稀疏：那类页面的留白是"给学生想的
            # 地方"，把要点撑满反而把问题挤没了。
            warns.append(f"本页仅占正文区 {blk[4] / body_h * 100:.0f}%，"
                         f"建议补充内容或改用 [重点]")
        layout_block(slide, page.bullets, MARGIN_X, body_y, CONTENT_W, body_h,
                     size=blk[0], sub=blk[1], space_after=blk[2],
                     line_spacing=blk[3])

    render_bottom_stack(slide, page)
    return "；".join(warns) if warns else None


def render_two_col(slide, page, meta):
    add_title(slide, page.title)
    body_y, body_h, _, warn = body_zone(page)
    warns = [warn] if warn else []

    if not any((page.left, page.right, page.left_img, page.right_img)):
        blk = fit_block(page.bullets, CONTENT_W, body_h)
        if blk[4] > body_h:
            warns.append(_overflow_warn(blk, body_h))
        layout_block(slide, page.bullets, MARGIN_X, body_y, CONTENT_W, body_h,
                     size=blk[0], sub=blk[1], space_after=blk[2],
                     line_spacing=blk[3])
        render_bottom_stack(slide, page)
        return "；".join(warns) if warns else None

    col_w = (CONTENT_W - 0.5) / 2
    cols = (("左", page.left, page.left_img, MARGIN_X),
            ("右", page.right, page.right_img, MARGIN_X + col_w + 0.5))

    # 两栏必须同字号同间距，否则学生会以为字号差异有含义；可用高度也要按
    # "有图的那栏"取，否则一栏放得下一栏放不下。
    def avail_for(items, img):
        return body_h * 0.5 if img else body_h

    blocks = []
    for _, items, img, _x in cols:
        blocks.append(fit_block(items, col_w, avail_for(items, img))
                      if items else None)
    live = [b for b in blocks if b]
    if live:
        size = min(b[0] for b in live)
        sub = min(b[1] for b in live)
        sa = min(b[2] for b in live)
        ls = min(b[3] for b in live)
    else:
        size, sub, sa, ls = SIZE_BODY, sub_size(SIZE_BODY), SA_BASE, LINE_SPACING

    # 两栏文字共用顶端：各自居中会让首行不齐，对照表读起来就是错的。
    needs = [text_height(items, col_w, size, sub, sa, ls) if items else 0.0
             for _, items, _img, _x in cols]
    need_max = max(needs)
    text_top = body_y + max(0.0, (body_h - need_max) / 2.0)

    for (label, items, img, x), need in zip(cols, needs):
        if items:
            layout_block(slide, items, x, text_top, col_w,
                         body_h - (text_top - body_y), size=size, sub=sub,
                         space_after=sa, line_spacing=ls, center=False)
            if need > body_h:
                warns.append(f"{label}栏文字 {need:.1f}in > 可用 {body_h:.1f}in")
        if img:
            path, h, w = img
            if items:
                # 文字与图作为一组往下顺；空间不够就先放弃居中，再放弃填充
                img_top = text_top + need + COL_STACK_GAP
                img_avail = BODY_BOTTOM - bottom_stack_height(page) - img_top
                if img_avail < MIN_IMG_H:
                    img_top = body_y + need + COL_STACK_GAP
                    img_avail = BODY_BOTTOM - bottom_stack_height(page) - img_top
                if img_avail < MIN_IMG_H:
                    warns.append(f"{label}栏文字+图超出可用高度")
                    img_avail = MIN_IMG_H
                _, mw = add_image(slide, path, x, img_top, col_w, img_avail,
                                  h, w, center_v=False)
            else:
                _, mw = add_image(slide, path, x, body_y, col_w, body_h,
                                  h, w, center_v=True)
            if mw:
                warns.append(mw)

    render_bottom_stack(slide, page)
    return "；".join(warns) if warns else None


def render_emph_page(slide, page, meta):
    """[重点] 版式：大字号居中，用于核心术语与必须记住的结论。

    不做自动填充 —— 重点页靠"居中 + 大字号"取胜，放大段后距会让三行文字
    散成三个孤岛，版面立刻垮。

    结论句（`!!!`）只由 render_bottom_stack 渲染成底部强调条，这里不再另画一遍。
    早先这里也把它当正文最大一行画过，同一页同一句话会以两个字号各出现一次。
    """
    add_title(slide, page.title)
    body_y, body_h, _, warn = body_zone(page)
    warns = [warn] if warn else []

    top = body_y + 0.3
    avail = (BODY_BOTTOM - bottom_stack_height(page)) - top
    tf = textbox(slide, MARGIN_X + 0.6, top, CONTENT_W - 1.2, avail,
                 anchor=MSO_ANCHOR.MIDDLE)
    for i, (level, text) in enumerate(page.bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        p.line_spacing = Pt(line_h(SIZE_EMPH) * 72)
        p.space_after = Pt(16)
        add_rich(p, text, SIZE_EMPH, COLOR["body"])

    render_bottom_stack(slide, page)
    return "；".join(warns) if warns else None


def render_full_image(slide, page, meta):
    add_title(slide, page.title)
    body_y, body_h, _, warn = body_zone(page)
    warns = [warn] if warn else []
    if page.images:
        path, h, w = page.images[0]
        _, mw = add_image(slide, path, MARGIN_X, body_y, CONTENT_W, body_h,
                          h, w, center_v=True)
        if mw:
            warns.append(mw)
    render_bottom_stack(slide, page)
    return "；".join(warns) if warns else None


def render_detail(slide, page, meta):
    """[阐述] 版式：16pt 细则，仅比赛版追加。

    不做字号填充（密集小字是给评委读的），但要做间距填充 —— 细则页常常
    只有三四条，不撑开会显得整页空荡。
    """
    add_title(slide, page.title)
    body_y, body_h, _, warn = body_zone(page)
    warns = [warn] if warn else []
    blk = fit_block(page.bullets, CONTENT_W, body_h, base=SIZE_DETAIL,
                    allow_resize=False)
    size = SIZE_DETAIL                        # 字号固定，只放开间距
    sub = sub_size(size)
    if blk[4] > body_h:
        warns.append(_overflow_warn(blk, body_h))
    layout_block(slide, page.bullets, MARGIN_X, body_y, CONTENT_W, body_h,
                 size=size, sub=sub, space_after=blk[2], line_spacing=blk[3])
    return "；".join(warns) if warns else None


def ink_box(path):
    """着墨区（四周纯白边之内真正有图形的那块）占整张画布的比例与中心。

    返回 (w_ratio, h_ratio, cx_ratio, cy_ratio)。取不到（没装 Pillow、坏图、
    整张纯白、着墨区小到不成形）返回 None —— 调用方退化为"整张画布即图形"。
    """
    try:
        from PIL import Image, ImageChops
        with Image.open(path) as im:
            if getattr(im, "is_animated", False):
                im.seek(0)
            rgba = im.convert("RGBA")
            W, H = rgba.size
            if W < 4 or H < 4:
                return None
            flat = Image.alpha_composite(
                Image.new("RGBA", rgba.size, (255, 255, 255, 255)), rgba
            ).convert("RGB")
            # 透明像素按白处理：出图脚本给的透明背景等同于白背景
            mask = ImageChops.difference(
                flat, Image.new("RGB", flat.size, (255, 255, 255))
            ).convert("L").point(lambda v: 255 if v > INK_WHITE_TOL else 0)
            box = mask.getbbox()
    except Exception:
        return None
    if box is None:
        return None                    # 整张纯白，没有可用的着墨区
    l, t, r, b = box
    iw, ih = (r - l) / W, (b - t) / H
    # 细到不足 2% 的着墨区多半是扫描噪点或一条边框线。照它裁会得到 l+r≈1 的
    # 退化裁切，PowerPoint 那边直接报文件损坏 —— 宁可退回不裁。
    if iw < 0.02 or ih < 0.02:
        return None
    return iw, ih, (l + r) / 2.0 / W, (t + b) / 2.0 / H


def flow_plan(paths, max_zone_h):
    """[流程] 按"同组图着墨区等高"定出每张图裁多少、摆多大。

    返回 (plan, arrow_w, arrow_gap, warns)。plan 是 [{path, crop, ar, w, h}]，
    w/h 为英寸（按 max_zone_h 估出，调用方可以再用实际图区高度等比缩小），
    crop 为 None 或 (l, t, r, b) 的裁切比例。

    为什么量着墨区而不是量文件画布：出图脚本常给一组图统一加 `"aspect": 1.0`
    把画布补成正方形，好让它们"看着一致"。但白边补在侧面还是补在上下并不统一，
    于是三个同样 370×370 的文件，着墨区可以是 0.60 / 0.60 / 1.89 —— contain 到
    同样大的格子里，真正看得见的图形高度差近一倍（实测棱柱分割那组，第三步只有
    前两步的 53%，宽扁地摊在格子里）。**补白把差异藏进了白边里**，所以按画布排
    就会排歪，旧版那条"文件长宽比差 3 倍就告警"也就永远不响（三个文件都是 1.00）。
    """
    warns = []
    plan = []
    for p in paths:
        W = H = None
        try:
            from PIL import Image
            with Image.open(p) as im:
                if getattr(im, "is_animated", False):
                    im.seek(0)
                W, H = im.size
        except Exception:
            pass                       # 坏图/缺图：交给 add_image 出占位框

        box = ink_box(p) if W else None
        if box is None or not W or not H:
            # 量不到就整张画布当图形。排出来仍是等比例的，只是没去掉白边。
            plan.append({"path": p, "crop": None,
                         "ar": (W / H) if (W and H) else 1.0})
            continue

        iw, ih, cx, cy = box
        plan.append({
            "path": p,
            "ar": (W * iw) / (H * ih),
            # 裁切是相对源图的比例，不是绝对像素
            "crop": (cx - iw / 2.0, cy - ih / 2.0,
                     1.0 - (cx + iw / 2.0), 1.0 - (cy + ih / 2.0)),
        })

    n = len(plan)
    sum_ar = sum(it["ar"] for it in plan) or 1.0

    # 先挑箭头：箭头占得越宽，留给图的横向预算就越少。取最宽的、又能让图形
    # 保持在可读高度上的那一档。
    arrow_w, arrow_gap, ink_h = FLOW_ARROW_LADDER[-1][0], FLOW_ARROW_LADDER[-1][1], 0.0
    for cand_w, cand_gap in FLOW_ARROW_LADDER:
        budget = CONTENT_W - (n - 1) * (cand_w + 2 * cand_gap)
        cand_h = min(max_zone_h, budget / sum_ar)
        arrow_w, arrow_gap, ink_h = cand_w, cand_gap, cand_h
        if cand_h >= FLOW_MIN_INK_H:
            break

    ars = [it["ar"] for it in plan]
    if ink_h < FLOW_MIN_INK_H and min(ars) > 0:
        # 这里告警而不是硬排：等比例这一条不能破（破了就是本函数要修的那个毛病），
        # 而硬排出来的图小到看不清，不如直说这组图得重出。
        warns.append(f"流程页统一比例后图形仅 {ink_h:.2f}in 高 —— 这组图着墨区的"
                     f"形状差得太多（宽高比 {min(ars):.2f}~{max(ars):.2f}），"
                     f"建议重出图让各步形状接近，或拆页")

    for it in plan:
        it["h"] = ink_h
        it["w"] = ink_h * it["ar"]
    return plan, arrow_w, arrow_gap, warns


def render_flow(slide, page, meta):
    """[流程] 版式：一页内并排 N 张图，图间用箭头连接，图下统一基线写说明。

    这一页的价值在于"上一步"和"这一步"同时在场，能被对照着看 —— 所以各图必须
    是**同一个尺度**，否则学生看不出第三步是第一、二步那个东西变来的，只看到三张
    大小不一的插画。因此不是"每张图各自缩放到格子里"，而是先定一个共用的着墨
    高度，再按各自的形状分宽（见 flow_plan）。箭头画在每段间隔的中线上，各图的
    垂直中心都落在这条线上，读起来是"从这张图指向下一张图"。
    """
    add_title(slide, page.title)
    steps, n = page.steps, len(page.steps)
    if n == 0:
        return render_generic(slide, page, meta)

    body_y, body_h, _, warn = body_zone(page)
    warns = [warn] if warn else []
    if n == 1:
        warns.append("流程页只有 1 步，没有可连接的箭头，建议改用 [纯图]")
    if n > FLOW_MAX_STEPS:
        warns.append(f"流程页 {n} 步，人得凑近看，建议拆页")

    # 先用"一整行说明 + 一个间隔"之外的满高估一轮，只为拿到各图的比例和箭头档位。
    # 说明行占多高、图区剩多高，此时还不知道 —— 图区只会更矮，所以这一轮算出的
    # 图宽是上限。**但这个上限不能反过来当说明折行的估算依据**，见下。
    est_zone_h = max(body_h - line_h(SIZE_CAPTION) - FLOW_CAPTION_GAP, 1.0)
    plan, arrow_w, arrow_gap, plan_warns = flow_plan(
        [p for p, _ in steps], est_zone_h)
    warns += plan_warns

    gutter = arrow_w + 2 * arrow_gap if n > 1 else 0.0

    def caption_cols(ink_h):
        """按图高 ink_h 排一次版，返回 (各格起点 x, 各说明框 (cap_x, cap_w))。

        说明可以借用到两侧的间隔里（相邻两条各借一半，正好接上而不重叠）——
        所以每格说明的可用宽度是"本图宽 + 一个间隔"，比图本身宽。定位与折行
        估算共用这一处，避免两处各算一遍、算岔了还没人发现。
        """
        row = sum(ink_h * it["ar"] for it in plan) + (n - 1) * gutter
        x = MARGIN_X + max(0.0, (CONTENT_W - row) / 2.0)
        xs, cols = [], []
        for it in plan:
            w = ink_h * it["ar"]
            cap_x = max(MARGIN_X, x - gutter / 2.0)
            cap_w = min(MARGIN_X + CONTENT_W, x + w + gutter / 2.0) - cap_x
            xs.append(x)
            cols.append((cap_x, max(cap_w, 0.5)))
            x += w + gutter
        return xs, cols

    def caption_rows(ink_h):
        _, cols = caption_cols(ink_h)
        rows = [_line_count(c, w, SIZE_CAPTION)
                for (_, c), (_, w) in zip(steps, cols) if c]
        return (max(rows) if rows else 1), (min(w for _, w in cols) if cols
                                            else CONTENT_W)

    # 说明行高与图高互相制约：说明折行越多图区越矮；图一矮，每格的列也窄，说明
    # 又更容易折行。所以迭代到不动点，而不是只估一次。
    #
    # 为什么不能按"最宽那一格"估一次：说明列是**每格自己的**图宽 + 一个间隔，
    # 窄图的说明列也窄。实测三步流程（各图宽 2.07 / 2.07 / 6.52in），按最宽的
    # 7.10in 估出"三格都是 1 行"，而第 1 格实际列宽只有 2.36in、要 2 行 ——
    # 多出的那一行压进了底部驱动问题里，且不产生任何告警。旧版没暴露是因为
    # 那时流程页不带驱动问题，说明行正好停在页面底边上；一旦这页有了底部堆叠区，
    # 这个"按最宽格估"就再也兜不住了。
    ink_h = (min(min(it["h"] for it in plan), body_h - FLOW_CAPTION_GAP)
             if plan else body_h)
    for _ in range(8):
        rows, _narrow = caption_rows(ink_h)
        fit_h = (min(min(it["h"] for it in plan),
                     body_h - rows * line_h(SIZE_CAPTION) - FLOW_CAPTION_GAP)
                 if plan else body_h)
        if fit_h >= ink_h - 1e-9:      # 收不动了 —— 已经是不动点
            break
        if fit_h < MIN_IMG_H:          # 再收就要把图压没了，停手并如实报告
            ink_h = MIN_IMG_H
            break
        ink_h = fit_h

    cap_lines, narrow_w = caption_rows(ink_h)
    cap_h = cap_lines * line_h(SIZE_CAPTION)
    if cap_lines > 3:
        warns.append(f"说明文字在 {narrow_w:.1f}in 的窄列里折了 {cap_lines} 行，"
                     f"建议精简")

    # 图形高度要等说明行占多少定下来才能最终确定：说明折行越多，图区越矮。
    img_zone_h = max(body_h - cap_h - FLOW_CAPTION_GAP, 0.0)
    if img_zone_h < 1.80:
        warns.append(f"流程页图区仅 {img_zone_h:.1f}in，"
                     f"建议不要与强调块/驱动问题同页")

    # 按最终图区高度收回一次。收的是高度，比例不变，所以"各图同尺度"仍然成立。
    for it in plan:
        it["h"] = ink_h
        it["w"] = ink_h * it["ar"]

    # 图宽之和由比例定死，行宽不够时靠缩箭头腾地方（flow_plan 里已经这么挑过档），
    # 还有富余就把整行居中 —— 而不是把间隔拉大，否则箭头会飘到离图很远的地方。
    row_w = sum(it["w"] for it in plan) + (n - 1) * gutter
    xs, cap_cols = caption_cols(ink_h)

    cy = body_y + img_zone_h / 2.0          # 图区的垂直中心 = 箭头的水平线
    cap_y = body_y + img_zone_h + FLOW_CAPTION_GAP

    # 兜底：迭代到 MIN_IMG_H 仍装不下时，说明行会越到底部堆叠区里去。这条必须报 ——
    # 文字压在文字上是最难在成品里发现的一类问题。
    over = cap_y + cap_h - (BODY_BOTTOM - bottom_stack_height(page))
    if over > 0.02:
        warns.append(f"说明行越过底部堆叠区 {over:.2f}in —— "
                     f"精简说明，或把本页的驱动问题移到下一页")

    for i, (path, caption) in enumerate(steps):
        it = plan[i]
        x = xs[i] if i < len(xs) else MARGIN_X
        _, mw = add_image(slide, path, x, cy - it["h"] / 2.0,
                          it["w"], it["h"], w=it["w"], h=it["h"],
                          center_h=False, center_v=False, crop=it["crop"])
        if mw:
            warns.append(f"流程第 {i + 1} 步 {mw}")

        if caption:
            cap_x, cap_w = cap_cols[i]
            # 给一点点余量：cap_h 是按模型算的整数值，实际渲染略高就会被裁掉
            # 最后半行 —— 说明文字被裁比留一点白难看得多。
            tf = textbox(slide, cap_x, cap_y, cap_w, cap_h + 0.08)
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            p.line_spacing = Pt(line_h(SIZE_CAPTION) * 72)
            p.space_after = Pt(0)
            add_rich(p, caption, SIZE_CAPTION, COLOR["body"])

        if i < n - 1:
            x += it["w"]
            arrow = slide.shapes.add_shape(
                MSO_SHAPE.RIGHT_ARROW,
                Inches(x + arrow_gap), Inches(cy - FLOW_ARROW_H / 2.0),
                Inches(arrow_w), Inches(FLOW_ARROW_H))
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = RGBColor.from_string(COLOR["arrow"])
            arrow.line.fill.background()
            arrow.shadow.inherit = False
            x += gutter

    render_bottom_stack(slide, page)
    return "；".join(warns) if warns else None


def render_example(slide, page, meta):
    """[例题] 版式：题干贴顶，配图挂在题干下方偏右，**左下留白**。

    那块留白是这个版式存在的理由 —— 它是老师写解答、推导或让学生上来写的地方。
    所以下半区左侧 EXAMPLE_SCRATCH_FRAC 里不摆任何东西；解答块（若有）落在留白里。

    题干固定 28pt 贴顶，**不跑 fit_block**：那个函数的职责是把文字撑满可用高度，
    与"故意留白"方向正好相反。题干过长要改的是题干本身，不是让它去占满下半页。
    """
    add_title(slide, page.title)
    body_y, body_h, stack_top, warn = body_zone(page)
    warns = [warn] if warn else []

    if len(page.images) > 1:
        warns.append(f"本页 {len(page.images)} 张图，仅渲染第 1 张"
                     f"（多图请用 [流程] 或 [两栏]）")

    stmt_h = 0.0
    if page.bullets:
        sa = default_space_after(SIZE_BODY)
        stmt_h = text_height(page.bullets, CONTENT_W, space_after=sa,
                             include_trailing=False)
        layout_block(slide, page.bullets, MARGIN_X, body_y, CONTENT_W,
                     max(stmt_h, 0.4), size=SIZE_BODY, space_after=sa,
                     center=False)
        if stmt_h > body_h:
            warns.append(f"题干估算 {stmt_h:.1f}in > 正文区 {body_h:.1f}in，"
                         f"会压到下方留白 —— 该改的是缩短题干，不是调小字号")

    lower_y = body_y + stmt_h + EXAMPLE_STMT_GAP
    lower_h = stack_top - lower_y
    scratch_w = CONTENT_W * EXAMPLE_SCRATCH_FRAC

    img = page.images[0] if page.images else None
    if img:
        img_x = MARGIN_X + scratch_w + COL_GAP
        img_w = CONTENT_W - scratch_w - COL_GAP
        path, h, w = img
        _, mw = add_image(slide, path, img_x, lower_y, img_w,
                          max(lower_h, 0.4), h, w,
                          center_h=True, center_v=True)
        if mw:
            warns.append(mw)
    else:
        # 没有配图时整片下半区都是留白，解答可以放宽到满版心
        scratch_w = CONTENT_W

    if page.answers:
        # 拿解答的"自然高度"（默认段距、不再压缩）跟留白区比，而不是比一个固定
        # 下限 —— 只有自然高度装不下时才说明这个版式真的挤，那时 fit_block 会
        # 去压段距行距，压出来的版面读着就紧了，得让写的人知道。
        need = answer_height(page.answers, scratch_w)
        if need > lower_h:
            warns.append(f"解答自然高度 {need:.1f}in > 留白区 {lower_h:.1f}in，"
                         f"会被压缩行距 —— 建议缩短题干或分两页")
        add_answer(slide, page.answers, MARGIN_X, lower_y, scratch_w,
                   max(lower_h, 0.4))

    render_bottom_stack(slide, page)
    return "；".join(warns) if warns else None


RENDERERS = {
    "封面": render_cover,
    "标题": render_generic,
    "两栏": render_two_col,
    "重点": render_emph_page,
    "纯图": render_full_image,
    "流程": render_flow,
    "阐述": render_detail,
    "例题": render_example,
}


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# 文字规范性检查（规则 9）
# --------------------------------------------------------------------------
# 本技能对"写多少"一直管得很严（标题 ≤12 字、一级要点 ≤6 行、每页 ≤1 个 !!!），
# 对"怎么写"却一个字都没管 —— 于是「体积谁都会算」「斜着推一下」这类口水话
# 能一路零告警地通过构建。这一节补的就是那个缺口。
#
# 只告警，不拦截（沿用本文件「告警是提示不是错误」的取向）：语体是判断题，
# 有些页面确实需要破例，把判断权留给人比强行拦截有用。

# 口语痕迹词典。命中即报，高置信 —— 这些词在数学课件的要点行里没有正当用法。
_SPOKEN_WORDS = ("我们", "咱们", "一下", "谁都会", "都知道", "很明显",
                 "还行吗", "凭什么")
# 「它」单独看，因为它以「其它」的形式合法出现在数学表述里
_PRONOUN_RE = re.compile(r"(?<!其)它")

# 散文断句的判据（启发式，低置信）。阈值是拿两份实际产出校准的：
#
#   命中（都是真该改的）：
#     一叠整齐的书，形状是长方体，体积是 V = Sh     ← 三个信息串在一行
#     书没有增减，只是错位 ——                       ← 句子断在破折号上，下一条接着写
#     圆锥底面半径 r，高 h，求体积                    ← 三个信息串在一行
#   不命中（都是合法的）：
#     若截得的两个截面面积总相等，则两个几何体的体积相等   ← 「若…则…」本就只有一个逗号
#     等高处截面面积相等，则体积相等
#     两个公式：柱体 V = Sh、锥体 V = 1/3 Sh          ← 用顿号并列，不是散文
#     反例：等高同底的圆锥与圆柱，中间截面不等
#
# 所以判据是「逗号 ≥2」（多个小句）而不是「字数 ≥N」，后者会在 25 字的
# 「若…则…」上误报。阈值定得偏严是有意的：误报会训练人忽略告警。
_PROSE_COMMA_MIN = 2
_PROSE_LONG_COMMA_MIN = 1
_PROSE_LONG_CHARS = 30
# 结尾悬空 == 这一条是半句话，下一条接着写。这是「把一句话拆成两条要点」的
# 直接症状，比任何长度阈值都准。「：」不算 —— 那是标签，下面接子要点是合法的。
_PROSE_DANGLING_RE = re.compile(r"[，、——]$")

# 驱动问题（>）不看语体：它本来就该是一句问话，正当使用「吗/呢/凭什么」。
# 没有这条豁免，「体积凭什么不变？」这类合格的驱动问题会被逼着改成不自然的问句。
# 阐述页只看词典、不看断句启发式：那是给评委看的 16pt 论述条目，成句是它的本分。
_WORDING_SKIP_LAYOUTS = {"封面"}


def check_wording(pages):
    """按规则 9 检查要点行的语体。返回告警列表（只提示，不阻断渲染）。"""
    warns = []
    for idx, p in enumerate(pages, 1):
        if p.layout in _WORDING_SKIP_LAYOUTS:
            continue
        tag = f"P{idx}[{p.layout}] {p.title or '(无标题)'}"

        # (文本, 是否适用断句启发式) —— 强调块与答案块是**句子**，成句是它们的
        # 本分，所以只过词典、不过断句检查。
        # 两栏页的正文在 left/right 里，不在 bullets 里 —— 漏掉它就等于漏掉
        # 一整个版式（实测：「书没有增减，只是错位 ——」正是一条两栏要点）。
        items = [(t, True) for _, t in p.bullets]
        items += [(t, True) for _, t in p.left]
        items += [(t, True) for _, t in p.right]
        items += [(c, True) for _, c in p.steps if c]
        if p.emph:
            items.append((p.emph, False))
        items += [(t, False) for t in p.answers]
        if p.layout == "阐述":
            items = [(t, False) for t, _ in items]

        for text, prose_check in items:
            plain = text.replace("**", "")
            hits = [w for w in _SPOKEN_WORDS if w in plain]
            if _PRONOUN_RE.search(plain):
                hits.append("它")
            if hits:
                warns.append(f"{tag}: 要点行有口语痕迹 {'、'.join(repr(h) for h in hits)}"
                             f" —— 「{_ellipsis(plain)}」按规则 9 改写成书面短语")
            if not prose_check:
                continue
            n = plain.count("，")
            why = None
            if n >= _PROSE_COMMA_MIN:
                why = f"{n} 个逗号串了多个小句"
            elif n >= _PROSE_LONG_COMMA_MIN and len(plain) >= _PROSE_LONG_CHARS:
                why = f"{len(plain)} 字、{n} 个逗号"
            elif _PROSE_DANGLING_RE.search(plain):
                why = "结尾悬空，这半句要并进上一条或补全"
            if why:
                warns.append(f"{tag}: 「{_ellipsis(plain)}」{why}"
                             f" —— 可能是一整句话被塞进一条要点（规则 9 判据 4；"
                             f"启发式判断，若这一条本来就是一整句可忽略）")
    return warns


def _ellipsis(text, n=22):
    return text if len(text) <= n else text[:n] + "…"


def validate(pages, meta):
    warns = []
    for idx, p in enumerate(pages, 1):
        tag = f"P{idx}[{p.layout}] {p.title or '(无标题)'}"

        if p.layout not in LAYOUTS:
            warns.append(f"{tag}: 未知版式（可选 {sorted(LAYOUTS)}）")
        # 判 layout_origin，不判 p.layout —— 到这儿 p.layout 已经是改完的
        # [流程] 了（构建循环里改的），判它恒为假。getattr 兜底 None，
        # 让没走过 build() 的调用方（测试直接构造 pages）也不炸。
        origin = getattr(p, "layout_origin", None)
        if origin:
            warns.append(f"{tag}: [{origin}] 已更名为 [流程]"
                         f"（现渲染为单页流程），建议改 md")
        if p.layout != "封面" and len(p.title) > 12:
            warns.append(f"{tag}: 标题 {len(p.title)} 字，超过 12 字"
                         f"（规则 3：标题要短）")
        n_main = sum(1 for lvl, _ in p.bullets if lvl == 0)
        if n_main > 6:
            warns.append(f"{tag}: 一级要点 {n_main} 行，超过 6 行"
                         f"（规则 7：该拆页，不是调小字号）")
        if p.emph_extra:
            warns.append(f"{tag}: 第 {p.emph_extra + 1} 个强调块已降级为普通要点"
                         f"（每页最多一个 !!!）")
        if p.layout in NO_IMAGE_LAYOUTS and p.images:
            warns.append(f"{tag}: [{p.layout}] 版式不渲染插图，"
                         f"{len(p.images)} 张图会被整张丢弃"
                         f"（要配图请改用 [标题] / [两栏] / [纯图]）")
        elif len(p.images) > 1:
            warns.append(f"{tag}: {len(p.images)} 张图但只渲染第 1 张"
                         f"（多图请用 [流程] 或 [两栏]）")
        if p.layout in CONSTRUCT_LAYOUTS and not p.has_image \
                and not p.exempt_no_image and not is_conclusion_page(p):
            warns.append(f"{tag}: 建构段无配图"
                         f"（规则 5；确实不需要时加 <!-- 允许无图 -->）")
        if p.layout in ("纯图", "两栏", "标题") and p.exempt_no_image \
                and p.has_image:
            warns.append(f"{tag}: 标了豁免却仍有图，豁免标记可删")
        if p.layout == EXAMPLE_LAYOUT and not p.bullets:
            # [例题] 的题干撑起上半页，配图与留白都挂在它下面。没有题干时
            # 下半区从正文区顶边就开始，整页只剩一张图和一个悬空的解答。
            warns.append(f"{tag}: [例题] 页没有题干 —— 这个版式靠题干压顶、"
                         f"配图和留白都排在它下方，请把题面写成要点行")
        if p.layout in NO_ANSWER_LAYOUTS and p.answers:
            warns.append(f"{tag}: [{p.layout}] 版式不渲染底部块，"
                         f"{len(p.answers)} 行解答会被整段丢弃"
                         f"（要放解答请改用 [例题] / [标题] / [重点]）")
        if p.answer_blank:
            warns.append(f"{tag}: 有 {p.answer_blank} 行 !ans: 后面是空的，"
                         f"不会有任何内容出现（要么补上解答，要么删掉这行）")

    if meta.get("footer"):
        warns.append("frontmatter 的 footer 已不再使用（页脚已取消），可删除")
    if meta.get("version") == "contest":
        if not any(p.layout == "阐述" for p in pages):
            warns.append("version=contest 但没有阐述页"
                         "（比赛版应含「教学设计阐述」「教学重难点及解决」）")
    return warns


# --------------------------------------------------------------------------
# 单击显现动画
# --------------------------------------------------------------------------
# 解答块（!ans:）在放映时**点击一次才出现** —— 教案里写着"引导学生思考讨论"的地方，
# 一上屏就摊开答案，讨论就没了。做法是给那个形状挂一个 PowerPoint 最老的进入效果
# （Appear，presetID=1），它从 PowerPoint 2000 起就没变过。
#
# ⚠ 这段 XML 是**唯一**一处会写坏产出的地方，所以有三条硬约定：
#
# 1. **不许写 hidden="1"。** 一个形状显不显示完全由下面这段 timing 决定（作者那份
#    参赛 PPT 里 hidden 出现 0 次，18 个单击效果全靠 timing）。所以"不注入 timing"
#    天然等于"答案直接显示" —— 版面分毫不差，只是少了一次点击，这是**正确**的退化。
#    可要是写了 hidden="1" 再退化，答案就成了永远不出现：版面看着完全正常，
#    只是那块东西没了。那才是真正的损坏，且没有迹象。
# 2. **只用主序列（mainSeq）+ 单击触发。** 不碰 p:bldLst（逐段/逐行揭示要文本构建
#    XML，风险面大得多），不做自动播放（delay 一律 indefinite），不做退出与强调。
# 3. **一页一个效果。** 页面上至多一个答案块（多行 !ans: 合成一块），所以每页的
#    主序列里最多一个单击组。
#
# 结构取自一份参赛课件的 ppt/slides/slide5.xml ——
# 那是该文件里最简的一处（timing=1、clickEffect=1、bldLst=0、hidden=0，1215 字节），
# 正好是一个"点一下出一块"的最小样例。层级逐字照抄，只换 id 与 spid：
#
#   p:timing / p:tnLst / p:par / p:cTn(nodeType=tmRoot)
#     p:childTnLst              ← python-pptx 的空骨架只有这一层，seq 要自己补
#       p:seq(nextAc=seek) / p:cTn(nodeType=mainSeq)
#         p:childTnLst
#           p:par / p:cTn(fill=hold, cond delay=indefinite)   ← "等一次点击"
#             p:par / p:cTn(fill=hold, cond delay=0)
#               p:par / p:cTn(presetClass=entr, presetID=1, nodeType=clickEffect)
#                 p:set / p:cBhvr / p:tgtEl / p:spTgt spid=N
#                              / p:attrNameLst / style.visibility
#                       / p:to / p:strVal visible
#         p:prevCondLst、p:nextCondLst                           ← 前后翻页要能跳过它
#
# 用 python-pptx 的 get_or_add_timing() + get_or_add_childTnLst() 建骨架，**不要用**
# CT_TimeNodeList._add_childTnLst：它内部先 remove 掉已有 timing 再重建，会连视频
# 那类已经写好的时序一起抹掉。
CLICK_REVEAL = True

_ANIM_HTML = """<p:seq {ns} concurrent="1" nextAc="seek">
  <p:cTn id="{main}" dur="indefinite" nodeType="mainSeq">
    <p:childTnLst>
      <p:par><p:cTn id="{grp}" fill="hold">
        <p:stCondLst><p:cond delay="indefinite"/></p:stCondLst>
        <p:childTnLst>
          <p:par><p:cTn id="{sub}" fill="hold">
            <p:stCondLst><p:cond delay="0"/></p:stCondLst>
            <p:childTnLst>
              <p:par><p:cTn id="{eff}" presetID="1" presetClass="entr"
                            presetSubtype="0" fill="hold" nodeType="clickEffect">
                <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                <p:childTnLst>
                  <p:set>
                    <p:cBhvr>
                      <p:cTn id="{set}" dur="1" fill="hold">
                        <p:stCondLst><p:cond delay="0"/></p:stCondLst>
                      </p:cTn>
                      <p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>
                      <p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst>
                    </p:cBhvr>
                    <p:to><p:strVal val="visible"/></p:to>
                  </p:set>
                </p:childTnLst>
              </p:cTn></p:par>
            </p:childTnLst>
          </p:cTn></p:par>
        </p:childTnLst>
      </p:cTn></p:par>
    </p:childTnLst>
  </p:cTn>
  <p:prevCondLst><p:cond evt="onPrev" delay="0">
    <p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>
  <p:nextCondLst><p:cond evt="onNext" delay="0">
    <p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>
</p:seq>"""


def apply_click_animations(prs):
    """给每个解答块挂一个"单击显现"。返回 (挂上的页数, 说明列表)。

    必须在所有幻灯片都渲染完之后、prs.save() 之前调用 —— 它按形状名找目标，
    而名字是渲染阶段写上的。
    """
    n = 0
    notes = []
    for i, slide in enumerate(prs.slides, 1):
        targets = [sh for sh in slide.shapes
                   if sh.has_text_frame and sh.name.startswith(ANSWER_BLOCK)]
        if not targets:
            continue
        if len(targets) > 1:
            notes.append(f"P{i}: {len(targets)} 个解答块，只给第一个挂动画")
        sh = targets[0]
        if _add_appear_on_click(slide, sh.shape_id):
            n += 1
        else:
            notes.append(f"P{i}: 该页已有主序列，动画未挂（保持直接显示）")
    return n, notes


def _add_appear_on_click(slide, shape_id):
    """往该页的 timing 里加一个单击显现效果。已有主序列时返回 False 不覆盖。

    为什么"已有就不动"：一页只该有一个 mainSeq，硬塞第二个会得到一段 PowerPoint
    读不懂的时序 —— 那正是"修复提示"的来源。真出现这种情况说明别的代码也往这页
    写了动画，此时保留原样（答案是直接显示的，不丢内容）比冒险合并安全。
    """
    el = slide._element
    child = el.get_or_add_childTnLst()
    if child.find(qn("p:seq")) is not None:
        return False
    # p:cTn 的 id 只要在**本页**内唯一即可（python-pptx 的 add_video 也是这么取的：
    # 全页最大 id + 1）。自己算而不是调 CT_TimeNodeList._next_cTn_id —— 那是个私有
    # 属性，逻辑就这一行，抄过来比押注它不被改名稳。
    ids = [int(v) for v in el.xpath("/p:sld/p:timing//p:cTn/@id")]
    base = (max(ids) + 1) if ids else 1
    seq = parse_xml(_ANIM_HTML.format(
        ns=nsdecls("p"), main=base, grp=base + 1, sub=base + 2,
        eff=base + 3, set=base + 4, spid=shape_id))
    child.append(seq)
    return True


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------

def blank_layout(prs):
    for layout in prs.slide_layouts:
        if layout.name in ("Blank", "空白"):
            return layout
    return prs.slide_layouts[-1]


def drop_all_slides(prs):
    """清空演示文稿的幻灯片，保留母版/版式/主题 —— 这是 "--template" 的核心。"""
    xml_slides = prs.slides._sldIdLst
    for sld in list(xml_slides):
        prs.part.drop_rel(sld.rId)
        xml_slides.remove(sld)


def build(md_path, out_path, template=None, font_title=None, font_body=None):
    global FONT_TITLE, FONT_BODY
    if font_title:
        FONT_TITLE = font_title
    if font_body:
        FONT_BODY = font_body

    with open(md_path, encoding="utf-8") as fh:
        meta, pages = parse(fh.read())

    if template:
        if not os.path.exists(template):
            sys.exit(f"模板不存在: {template}")
        prs = Presentation(template)
        drop_all_slides(prs)
        # python-pptx 自带的默认模板是 10 × 7.5。底版若不是 16:9，下面所有
        # 按 13.333 × 7.5 写死的几何量会全面错位 —— 与其产出一份歪的课件，
        # 不如直接说清楚。
        if abs(prs.slide_width - Inches(SLIDE_W)) > 9144:      # 0.01 in
            sys.exit(f"底版尺寸 {prs.slide_width / 914400:.2f} × "
                     f"{prs.slide_height / 914400:.2f} in，"
                     f"不是 16:9（{SLIDE_W} × {SLIDE_H}）")
    else:
        prs = Presentation()
        prs.slide_width = Inches(SLIDE_W)
        prs.slide_height = Inches(SLIDE_H)

    prs.core_properties.title = meta.get("title", "") or ""

    blank = blank_layout(prs)
    base = os.path.dirname(os.path.abspath(md_path))
    warn_imgs = []

    for idx, page in enumerate(pages, 1):
        # 解析该页的图片路径为相对 md 的绝对路径
        for container in (page.images, page.steps):
            for i, (path, *rest) in enumerate(container):
                container[i] = (os.path.join(base, path), *rest)
        for attr in ("left_img", "right_img"):
            v = getattr(page, attr)
            if v:
                setattr(page, attr, (os.path.join(base, v[0]),) + tuple(v[1:]))

        # 先把「原来叫什么」记下来，再改名。
        # validate() 是在循环之后才跑的（`warns = validate(...)` 那行），
        # 而它是拿同一个 pages 列表判的 —— 不记这一笔，它看到的永远是改完的
        # [流程]，validate 里那条 `p.layout in LAYOUT_ALIAS` 就恒为假，
        # 告警成了死代码。SKILL.md 却写着「会被改名并提示」，用户等不到。
        page.layout_origin = page.layout if page.layout in LAYOUT_ALIAS else None
        page.layout = LAYOUT_ALIAS.get(page.layout, page.layout)
        renderer = RENDERERS.get(page.layout, render_generic)
        slide = prs.slides.add_slide(blank)
        w = renderer(slide, page, meta)
        if w:
            warn_imgs.append(f"P{idx}[{page.layout}] {w}")

    warns = validate(pages, meta) + check_wording(pages) + warn_imgs
    warns += check_spacing_written(prs)
    glyph_warns, n_faces = check_glyphs(prs)
    warns += glyph_warns
    if n_faces == 0:
        # 「没查到」必须显式说出来。静默跳过会被读成「字形全都有」，
        # 而这条检查挡的恰恰是那种渲染成功但字形是方框的静默失败。
        warns.append("字形覆盖未检查（没装 fontTools 或找不到字体文件）—— "
                     "本次不保证成品里没有字体缺字的字符")

    # 动画必须在保存前注入，且必须在所有页都渲染完之后 —— 它按形状名找目标，
    # 名字是渲染阶段写上的。见「单击显现动画」一节。
    n_anim = 0
    if CLICK_REVEAL:
        n_anim, anim_notes = apply_click_animations(prs)
        warns.extend(anim_notes)
    elif any(p.answers for p in pages):
        # 关掉开关时不能静默：写了 !ans: 的人以为答案会藏着，而它其实是直接显示的。
        warns.append("单击显现动画已关闭（CLICK_REVEAL=False）—— "
                     "所有 !ans: 解答会直接显示在页面上，不再点击显现")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    prs.save(out_path)

    return len(pages), len(prs.slides._sldIdLst), n_anim, warns


def check_spacing_written(prs):
    """确保每个要点块的段落都显式写了 spcPts 行距。

    这一条不是在挑格式毛病：高度模型算的是绝对行高，而 spcPct 是"字体自然
    行高的百分比"，两者一旦混用，填充算法就会按错的数做决定 —— 而且换底版
    换个字体后结果还会再变一次。这个检查专门抓这种静默脱钩。

    只查 BODY_BLOCK 与 ANSWER_BLOCK：单行元素（标题、封面副标题、驱动问题）
    不参与填充，给它们写死行距既没用也碍事。答案块要查，因为它在 [例题] 里
    同样受留白区高度约束、同样走 fit_block —— 漏掉它就等于漏掉一整个版式。
    """
    bad = []
    for i, s in enumerate(prs.slides, 1):
        for sh in s.shapes:
            if not sh.has_text_frame or not sh.name.startswith(
                    (BODY_BLOCK, ANSWER_BLOCK, EMPH_BLOCK, QUESTION_BLOCK)):
                continue
            for p in sh.text_frame.paragraphs:
                if not p.runs:
                    continue
                pPr = p._p.find(qn("a:pPr"))
                ln = pPr.find(qn("a:lnSpc")) if pPr is not None else None
                if ln is None or ln.find(qn("a:spcPts")) is None:
                    bad.append(f"P{i} 要点块有段落未写 spcPts 行距"
                               f"（估算会与渲染脱钩）")
                    break
    return bad


# --------------------------------------------------------------------------
# 字形覆盖检查
# --------------------------------------------------------------------------
# 字体里没有某个字形时 Python 不报错、python-pptx 不报错、PowerPoint 打开也不报错 ——
# 它只是把那个字画成一个方框。缩略图里方框看着就像一坨正常的字，只有逐字读才发现。
# 这是全套校验里唯一"渲染成功但内容是错的"的失败模式，所以只能自己去查 cmap。
#
# 实测（Windows 11 自带字体，fontTools 读 cmap）：
#     微软雅黑 msyh.ttc 与 华文中宋 STZHONGS.TTF **都缺**
#         ₁ ₂ ⟹ ⅓ ⟷ ⇒ ∅
# 数学课件偏偏爱用下标和箭头，这批字符正是高危区。缺字形时 PowerPoint 有时会回退到
# 别的字体顶上 —— 于是同一个符号在相邻两页长得不一样，观感不可控；WPS 与老版本
# PowerPoint 则直接画方框。两种结局都不该靠运气，所以报出来让人换字符。

_FONT_FILES = {
    "微软雅黑": ("msyh.ttc", "msyh.ttf", "msyhbd.ttc"),
    "华文中宋": ("STZHONGS.TTF", "STZHONGS.ttf"),
    "等线": ("Deng.ttf", "Dengb.ttf"),
    "宋体": ("simsun.ttc",),
    "黑体": ("simhei.ttf",),
    "楷体": ("simkai.ttf",),
}

# 变体选择符、零宽字符之类不需要字形，查了只会误报
_GLYPH_EXEMPT = {0x200B, 0x200C, 0x200D, 0xFE0E, 0xFE0F}

_cmap_cache = {}


def _cmap_for(face):
    """该字族能渲染的码点集合；取不到（没装 fontTools / 找不到字体文件）返回 None。

    None 的语义是"没查到"，不是"没问题" —— 两者绝不能混，否则这条检查会输出
    虚假的安全感。
    """
    if face in _cmap_cache:
        return _cmap_cache[face]
    cps = None
    try:
        from fontTools.ttLib import TTFont
        fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        for cand in _FONT_FILES.get(face, (face, face + ".ttf", face + ".ttc")):
            path = os.path.join(fonts_dir, cand)
            if not os.path.isfile(path):
                continue
            ttf = TTFont(path, fontNumber=0, lazy=True)
            cps = set()
            for table in ttf["cmap"].tables:
                cps |= set(table.cmap.keys())
            break
    except Exception:
        cps = None
    _cmap_cache[face] = cps
    return cps


def _faces_of(run):
    """run 上显式写死的字族（latin 与 ea 各可能不同）。"""
    rPr = run._r.find(qn("a:rPr"))
    if rPr is None:
        return []
    out = []
    for tag in ("a:latin", "a:ea"):
        el = rPr.find(qn(tag))
        v = el.get("typeface") if el is not None else None
        if v and v not in out:
            out.append(v)
    return out


def check_glyphs(prs):
    """扫全部文字，报出目标字族渲染不了的字符。

    返回 (告警, 实际查过字形的字族数)。第二个数用来区分「查过没问题」和
    「压根没查成」—— 为 0 时调用方应当明说这次没验成，而不是默认通过。
    """
    missing = {}          # face -> {char: {页码}}
    live_faces = set()

    for idx, slide in enumerate(prs.slides, 1):
        for sh in slide.shapes:
            if not sh.has_text_frame:
                continue
            for para in sh.text_frame.paragraphs:
                for run in para.runs:
                    text = run.text
                    if not text or not any(ord(c) > 127 for c in text):
                        continue
                    faces = _faces_of(run)
                    if not faces:
                        continue          # 没显式指定 = 继承主题，无法判定
                    cmaps = [_cmap_for(f) for f in faces]
                    known = [c for c in cmaps if c is not None]
                    if not known:
                        continue          # 字族不认识，跳过而不是判它错
                    live_faces.update(f for f, c in zip(faces, cmaps) if c is not None)
                    for ch in text:
                        cp = ord(ch)
                        # 只查 >127：ASCII 在所有中文字体里都有，查了纯属浪费时间
                        if cp <= 127 or cp in _GLYPH_EXEMPT:
                            continue
                        if any(cp in c for c in known):
                            continue
                        missing.setdefault("/".join(faces), {}) \
                               .setdefault(ch, set()).add(idx)

    warns = []
    for face, chars in sorted(missing.items()):
        # 按首次出现页码排，读告警的人正好按翻页顺序核对
        for ch, pages in sorted(chars.items(), key=lambda kv: (min(kv[1]), kv[0])):
            where = "、".join(f"P{p}" for p in sorted(pages)[:6])
            if len(pages) > 6:
                where += f" 等 {len(pages)} 页"
            warns.append(f"「{face}」没有 {ch!r}（U+{ord(ch):04X}）的字形，"
                         f"{where} —— 可能被画成方框或被回退字体顶替，"
                         f"建议换成同类可显示字符")
    return warns, len(live_faces)


def main():
    ap = argparse.ArgumentParser(description="课件.md → .pptx")
    ap.add_argument("src", help="课件.md")
    ap.add_argument("-o", "--out", required=True, help="输出 .pptx")
    ap.add_argument("--template", help="底版 .pptx（继承其母版与主题）")
    ap.add_argument("--font-title", help=f"标题字族（默认 {FONT_TITLE}）")
    ap.add_argument("--font-body", help=f"正文字族（默认 {FONT_BODY}）")
    ap.add_argument("--strict", action="store_true",
                    help="有告警时以非零码退出（默认仅提示）")
    args = ap.parse_args()

    n_pages, n_slides, n_anim, warns = build(args.src, args.out, args.template,
                                             args.font_title, args.font_body)

    print(f"✓ {args.out}")
    print(f"  {n_pages} 个页面块 → {n_slides} 张幻灯片")
    if n_anim:
        # 这个数要报出来：它是 COM 复核的期望值，见 scripts/verify_anim.ps1。
        print(f"  单击显现 {n_anim} 页（解答块）")

    if warns:
        print(f"\n告警 {len(warns)} 条（不影响渲染完成）:")
        for w in warns:
            print(f"  · {w}")
        if args.strict:
            return 1
    else:
        print("  结构校验通过，无告警")
    return 0


if __name__ == "__main__":
    sys.exit(main())
