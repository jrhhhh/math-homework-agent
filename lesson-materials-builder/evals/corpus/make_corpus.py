#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 evals/corpus/src/*.md 生成 .docx 与 .pdf，作为产出层的输入语料。

    python evals/corpus/make_corpus.py            # 生成全部
    python evals/corpus/make_corpus.py --only mini-1

为什么手写 OOXML 而不用 python-docx：**技能不依赖 python-docx**。
SKILL.md 里读 .docx 走的是 `zipfile` 读 word/document.xml 再剥标签，这里生成也用
同一套 stdlib，免得为了造测试数据反过来给技能引入一条新依赖。

生成的 docx 是**普通 Word 文档**（[Content_Types].xml + _rels/.rels + word/document.xml），
不引用 styles.xml —— 因此所有格式都是直接写在 run 上的。改完务必按 evals/README.md
里的「语料自检」跑一遍，确认技能真能读出正文。
"""

import argparse
import html
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# 半磅为单位：h1=18pt, h2=14pt, h3=12pt, 正文=10.5pt
SZ = {"h1": 36, "h2": 28, "h3": 24, "p": 21, "li": 21, "cell": 21}


# --------------------------------------------------------------------------
# Markdown 子集解析
# --------------------------------------------------------------------------

def parse(md):
    """→ [(kind, payload)]，kind ∈ h1|h2|h3|p|li|table"""
    lines = md.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s or s == "---":
            i += 1
            continue

        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(set(c) <= set("-: ") for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                blocks.append(("table", rows))
            continue

        m = re.match(r"^(#{1,3})\s+(.*)$", s)
        if m:
            blocks.append(("h%d" % len(m.group(1)), m.group(2).strip()))
            i += 1
            continue

        m = re.match(r"^(\d+\.|[-*])\s+(.*)$", s)
        if m:
            blocks.append(("li", s))
            i += 1
            continue

        blocks.append(("p", s))
        i += 1
    return blocks


# --------------------------------------------------------------------------
# .docx
# --------------------------------------------------------------------------

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def runs(text, bold_all=False, size=None):
    """`**粗**` 拆成交替的 run。返回的 XML 里 `</w:p>` 由调用方补 —— 技能读 docx
    就是靠把 `</w:p>` 换成换行再剥标签，所以段落边界必须是良构的 w:p。"""
    parts = text.split("**")
    out = []
    for i, p in enumerate(parts):
        if not p:
            continue
        rpr = ""
        b = "<w:b/>" if (bold_all or i % 2 == 1) else ""
        sz = '<w:sz w:val="%d"/>' % size if size else ""
        if b or sz:
            rpr = "<w:rPr>%s%s</w:rPr>" % (b, sz)
        out.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, esc(p)))
    return "".join(out) or '<w:r><w:t xml:space="preserve"></w:t></w:r>'


def para(text, kind):
    size = SZ.get(kind, SZ["p"])
    align = '<w:jc w:val="center"/>' if kind == "h1" else ""
    ppr = "<w:pPr>%s</w:pPr>" % align if align else ""
    return "<w:p>%s%s</w:p>" % (ppr, runs(text, bold_all=(kind in ("h1", "h2", "h3")), size=size))


def docx_table(rows):
    ncol = max(len(r) for r in rows)
    w = int(8640 / ncol)
    x = ['<w:tbl><w:tblPr><w:tblW w:w="8640" w:type="dxa"/><w:tblBorders>']
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        x.append('<w:%s w:val="single" w:sz="4" w:space="0" w:color="808080"/>' % side)
    x.append("</w:tblBorders></w:tblPr>")
    for ri, row in enumerate(rows):
        x.append("<w:tr>")
        for ci in range(ncol):
            cell = row[ci] if ci < len(row) else ""
            x.append('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/></w:tcPr>' % w)
            x.append("<w:p>%s</w:p>" % runs(cell, bold_all=(ri == 0), size=SZ["cell"]))
            x.append("</w:tc>")
        x.append("</w:tr>")
    x.append("</w:tbl>")
    # Word 要求两张相邻表格之间必须有段落，否则会被并成一张。统一补一个空段。
    x.append("<w:p/>")
    return "".join(x)


CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    "</Types>"
)

RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    "</Relationships>"
)


def write_docx(blocks, path):
    body = []
    for kind, payload in blocks:
        if kind == "table":
            body.append(docx_table(payload))
        else:
            body.append(para(payload, kind))
    doc = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="%s"><w:body>%s'
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/></w:sectPr>'
        "</w:body></w:document>" % (W, "".join(body))
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/document.xml", doc)


# --------------------------------------------------------------------------
# .pdf  （matplotlib，只嵌 TrueType 子集；用 .ttc 容易出问题，所以挑纯 .ttf）
# --------------------------------------------------------------------------

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\STZHONGS.TTF",   # 华文中宋 —— 与技能正文默认字体一致
    r"C:\Windows\Fonts\simhei.ttf",
]


def find_font():
    for f in FONT_CANDIDATES:
        if os.path.exists(f):
            return f
    return None


def pdf_blocks(blocks):
    """→ [(text, kind)]，表格压成「a ｜ b ｜ c」的行"""
    out = []
    for kind, payload in blocks:
        if kind == "table":
            for ri, row in enumerate(payload):
                out.append((" ｜ ".join(row), "cell"))
                if ri == 0:
                    out.append(("-" * 46, "cell"))
        else:
            out.append((payload.replace("**", ""), kind))
    return out


def wrap(text, n):
    """按字数折行。全角字符按 1 计，ASCII 按 0.5 计 —— 够用即可。"""
    lines, cur, w = [], "", 0.0
    for ch in text:
        cw = 1.0 if ord(ch) > 0x2000 else 0.5
        if w + cw > n and cur:
            lines.append(cur)
            cur, w = "", 0.0
        cur += ch
        w += cw
    if cur:
        lines.append(cur)
    return lines or [""]


def write_pdf(blocks, path):
    import matplotlib
    matplotlib.use("Agg")
    # 关键：matplotlib 默认 pdf.fonttype=3（Type 3 字体），生成的中文 PDF
    # **提取不出来** —— pypdf 拿回的是 `/uni00000003` 这样的字形编号，汉字数为 0，
    # 而文件看着完全正常。设成 42 才会嵌入 TrueType 子集并带 ToUnicode 映射。
    # 实测：默认设置下三份语料 extract_text() 全是 0 汉字，改成 42 后逐字正确。
    matplotlib.rcParams["pdf.fonttype"] = 42
    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    fp = find_font()
    if not fp:
        raise RuntimeError("找不到可用的中文字体（STZHONGS.TTF / simhei.ttf）")
    font = font_manager.FontProperties(fname=fp)

    # A4，四边 0.9in 页边距
    PW, PH, M = 8.27, 11.69, 0.9
    usable = PW - 2 * M                      # 英寸
    sizes = {"h1": 16, "h2": 13, "h3": 11.5, "p": 10.5, "li": 10.5, "cell": 9.5}

    pages = []
    cur = []
    y = PH - M
    for text, kind in pdf_blocks(blocks):
        fs = sizes.get(kind, 10.5)
        cpl = max(10, int(usable / (fs / 72.0)))       # 每行字数
        lh = fs * 1.9 / 72.0                            # 行高（英寸）
        if kind == "h1":
            y -= 0.25
        for ln in wrap(text, cpl):
            if y - lh < M:
                pages.append(cur)
                cur, y = [], PH - M
            cur.append((M, y, ln, fs, kind))
            y -= lh
        gap = 0.16 if kind in ("p", "li", "cell") else 0.08
        y -= gap

    if cur:
        pages.append(cur)

    with PdfPages(path) as pdf:
        for page in pages:
            fig = plt.figure(figsize=(PW, PH))
            for x, yy, ln, fs, kind in page:
                bold = kind in ("h1", "h2", "h3")
                fig.text(x / PW, yy / PH, ln, fontproperties=font,
                         fontsize=fs, va="top", ha="left",
                         fontweight="bold" if bold else "normal")
            pdf.savefig(fig)
            plt.close(fig)
    return len(pages)


# --------------------------------------------------------------------------

def count_docx(path):
    """按 SKILL.md 第 1 步读 docx 的同一套办法数汉字 —— 生成和读取用同一路径，
    这条自检才代表技能真的读得到。"""
    x = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    x = x.replace("</w:p>", "\n")
    return len(re.findall(r"[一-鿿]", html.unescape(re.sub(r"<[^>]+>", "", x))))


def count_pdf(path):
    from pypdf import PdfReader
    return len(re.findall(r"[一-鿿]",
                          "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="只生成指定前缀，如 mini-1")
    a = ap.parse_args()

    if not os.path.isdir(SRC):
        print("找不到源目录: %s" % SRC)
        return 1

    todo = []
    for name in sorted(os.listdir(SRC)):
        if not name.endswith(".md"):
            continue
        stem = os.path.splitext(name)[0]
        if a.only and not stem.startswith(a.only):
            continue
        todo.append((stem, os.path.join(SRC, name)))

    if not todo:
        print("没有匹配的源文件")
        return 1

    made = []
    for stem, src in todo:
        with open(src, encoding="utf-8") as f:
            md = f.read()
        blocks = parse(md)
        nch = len(re.findall(r"[\u4e00-\u9fff]", open(src, encoding="utf-8").read()))

        # 两种格式都出。哪一份进产出层由 corpus.json 决定 —— 免得把「哪个是
        # 指定格式」这条信息藏在生成器里，改起来还得动代码。
        d = os.path.join(HERE, stem + ".docx")
        write_docx(blocks, d)
        p = os.path.join(HERE, stem + ".pdf")
        npg = write_pdf(blocks, p)

        print("%-20s 源 %4d 字  docx %6d B   pdf %d 页 %6d B"
              % (stem, nch, os.path.getsize(d), npg, os.path.getsize(p)))
        made.append((nch, d, "docx"))
        made.append((nch, p, "pdf"))

    # 生成完立刻自证：生成器产出的东西必须真的能被技能读出来，否则产出层是在读
    # 空文档，而报告会把这件事显示成「技能做得不好」。容许 5% 误差（标点与空白
    # 的口径差异）。
    print("\n读回自检（走技能自己的读取路径）")
    bad = 0
    for want, path, kind in made:
        got = count_docx(path) if kind == "docx" else count_pdf(path)
        ok = got >= want * 0.95
        if not ok:
            bad += 1
        print("  %s %-24s 源 %4d / 读回 %4d  %s"
              % ("ok  " if ok else "FAIL", os.path.basename(path), want, got,
                 "一致" if ok else "**读不出来，别拿它当语料**"))

    if bad:
        print("\n有 %d 份读不回来 —— 先修生成器，别往下做产出层。" % bad)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
