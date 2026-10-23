# -*- coding: utf-8 -*-
"""lesson-materials-builder 产出物的独立复核。

刻意不 import build_pptx —— 复核必须独立于被检代码。只读 .pptx 成品，
几何量自己从 EMU 算，判据自己定。

能查到什么 / 查不到什么（写清楚，免得把"没查"当成"没问题"）：
  查得到（客观、与字体度量无关）：
    · 画布尺寸、形状越界、图片拉伸、图片与文字重叠
    · 图片左右留白是否一致（含一整排流程图的间距均匀性）
    · 字体契约、行距单位、内页页脚、要点条数
    · 同页重复的长文本 ← 几何校验查不出的那一类
  查不到（需真实字体度量，本脚本没有，故不冒充）：
    · 70pt 封面标题在真实字体下会不会折行
    · 文字块"着墨高度"是否精确垂直居中（只在明显溢出时报，容差放宽到 0.15in）

用法：
    python scripts/verify_pptx.py 课件.pptx [--figures figures/] [--info]

退出码：0 = 无 ERROR（WARN 不算失败）；1 = 有 ERROR。
被 bench.py 当断言引擎调用，所以输出格式（`[ERROR] Pn …` / `[WARN ] Pn …`
与末行 `结论：ERROR n 条，WARN n 条`）是契约，改动要同步 bench.py。
"""
import sys, os, glob, hashlib, argparse, json
from collections import defaultdict

from pptx import Presentation

EMU = 914400.0
SLIDE_W_EMU, SLIDE_H_EMU = 12192000, 6858000
SLIDE_W, SLIDE_H = SLIDE_W_EMU / EMU, SLIDE_H_EMU / EMU
MARGIN_X = 0.76
CONTENT_L, CONTENT_R = MARGIN_X, SLIDE_W - MARGIN_X
BODY_Y, BODY_BOTTOM = 1.42, 6.85

TOL_BOUNDS = 0.02
TOL_CENTER = 0.05
TOL_OVERFLOW = 0.15
TOL_AR = 0.02
TOL_CANVAS = 0.02      # 画布比标称差多少英寸才算真变形，见下面那条检查的注释

FONT_ALLOWED = {"微软雅黑", "华文中宋", None, ""}
FOOTER_KEYS = ("教材：", "人教A版", "必修", "选择性必修")

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def inch(v):
    return (v or 0) / EMU


def is_pic(sh):
    return sh.shape_type == 13 or sh.__class__.__name__ == "Picture"


def src_crop(p):
    """(l, r, t, b) 裁切比例。渲染器用 a:srcRect 裁掉图的白边，裁完的实际显示
    比例 = 源比例 × (1-l-r)/(1-t-b) —— 不把这一层算进去，裁剪会被误判成拉伸。"""
    return (p.crop_left or 0.0, p.crop_right or 0.0,
            p.crop_top or 0.0, p.crop_bottom or 0.0)


def is_txt(sh):
    return sh.has_text_frame and sh.text_frame.text.strip() != ""


def paras(sh):
    """[(text, max_size_pt, spcPts, spcAft, spcBef)]，跳过空段。"""
    out = []
    for p in sh.text_frame.paragraphs:
        t = "".join(r.text for r in p.runs).strip()
        if not t:
            continue
        sizes = [r.font.size.pt for r in p.runs if r.font.size]
        pPr = p._p.find(A + "pPr")
        spc = aft = bef = None
        if pPr is not None:
            ln = pPr.find(A + "lnSpc")
            if ln is not None:
                e = ln.find(A + "spcPts")
                if e is not None:
                    spc = int(e.get("val")) / 100.0
            for tag, key in ((A + "spcAft", "aft"), (A + "spcBef", "bef")):
                e = pPr.find(tag)
                if e is not None:
                    pts = e.find(A + "spcPts")
                    if pts is not None:
                        v = int(pts.get("val")) / 100.0
                        if key == "aft":
                            aft = v
                        else:
                            bef = v
        out.append((t, max(sizes) if sizes else None, spc, aft, bef))
    return out


def font_of(run):
    rPr = run._r.find(A + "rPr")
    latin = ea = None
    if rPr is not None:
        for tag in ("latin", "ea"):
            e = rPr.find(A + tag)
            if e is not None:
                v = e.get("typeface")
                if tag == "latin":
                    latin = v
                else:
                    ea = v
    return latin, ea


def spacing_kind(p):
    pPr = p._p.find(A + "pPr")
    if pPr is None:
        return None
    ln = pPr.find(A + "lnSpc")
    if ln is None:
        return None
    if ln.find(A + "spcPts") is not None:
        return "pts"
    if ln.find(A + "spcPct") is not None:
        return "pct"
    return None


def anchor_of(sh):
    bodyPr = sh.text_frame._txBody.find(A + "bodyPr")
    return bodyPr.get("anchor") if bodyPr is not None else None


def est_ink_h(sh, box_w_in):
    """粗估着墨高度，只用于"明显溢出"这一档判断。"""
    total = 0.0
    ps = paras(sh)
    for i, (t, size, spc, aft, bef) in enumerate(ps):
        size = size or 28
        lh = (spc / 72.0) if spc else size * 1.2 / 72.0
        w_pt = sum(size if ord(c) > 0x2E80 else size * 0.5 for c in t)
        lines = max(1, int(w_pt / max(box_w_in * 72.0, 1)) + (1 if w_pt % max(box_w_in * 72.0, 1) else 0))
        total += lines * lh
        if bef:
            total += bef / 72.0
        if i < len(ps) - 1 and aft:
            total += aft / 72.0
    return total


def scan(path, figures_dir=None):
    """量一份成品，返回**带类别标签**的记录。

    → {"prs": 演示文稿, "errors": [rec], "warns": [rec], "info": [str]}
      rec = {"page": int, "cat": str|None, "shape": str|None,
             "value": float|None, "msg": str}

    **为什么要类别标签，而不是让调用方去正则匹配消息里的中文散文。**
    基准要按类别计分（哪些告警算缺陷、哪些只是本技能的文风），而「拿中文散
    文当键」这件事一旦某天有人顺手润色了一句提示语，分类就会**静默**落到
    「未知」上 —— 缺陷计数悄悄少一截，而报告看上去一切正常。这正是本项目
    反复吃过的那个亏。所以类别写在**判据发生的那一行**（`cat=` 参数），
    改文案改不掉它。

    `value` 只在有意义的地方给，用来做阈值判断 —— 比如「越出版心」既包括
    封面贴边那种真缺陷（0.00 → 13.33），也包括比版心多出 0.06in 这种没有
    视觉意义的溢出，两者混在一个计数里就没法用了。

    老调用方要的是 `(页号, 消息)` 元组，那个契约由 `check()` 保持不变。
    """
    prs = Presentation(path)
    errs, warns, info = [], [], []

    def E(s, m, cat=None, shape=None, value=None):
        errs.append({"page": s, "cat": cat, "shape": shape,
                     "value": value, "msg": m})

    def W(s, m, cat=None, shape=None, value=None):
        warns.append({"page": s, "cat": cat, "shape": shape,
                      "value": value, "msg": m})

    # 画布容差。这条检查的目的只有一个：画布不是 16:9 时投影会**整体变形**。
    # 实测事故：基线那份是 12191695×6858000，比标称窄 **305 EMU = 0.0003 英寸**
    # —— 0.0025% 的差，投影上看不出来，却被判成 ERROR，于是「基线 1 ERROR」
    # 这个数被当成技能的优势。那是狼来了。变形的门槛设在 0.02in：4:3 那种
    # 真变形（差 3.5in）远超它，而浮点/取整误差远达不到。
    dw = abs(prs.slide_width - SLIDE_W_EMU) / EMU
    dh = abs(prs.slide_height - SLIDE_H_EMU) / EMU
    if max(dw, dh) > TOL_CANVAS:
        E(0, f"画布 {prs.slide_width}×{prs.slide_height} EMU，"
             f"应为 {SLIDE_W_EMU}×{SLIDE_H_EMU}",
          cat="verify.canvas.not_169", value=max(dw, dh))

    src_ar = {}       # md5 -> (宽高比, 文件名)
    src_ink = {}      # md5 -> (着墨带上沿, 下沿) 占整张画布的比例
    if figures_dir and os.path.isdir(figures_dir):
        try:
            from PIL import Image, ImageChops
            for f in glob.glob(os.path.join(figures_dir, "**", "*"), recursive=True):
                if os.path.splitext(f)[1].lower() not in (".png", ".jpg", ".jpeg", ".gif"):
                    continue
                with open(f, "rb") as fh:
                    h = hashlib.md5(fh.read()).hexdigest()
                with Image.open(f) as im:
                    src_ar[h] = (im.size[0] / im.size[1], os.path.basename(f))
                    rgba = im.convert("RGBA")
                    # 别叫 W / H —— 模块里 W() 是「告警」函数，W, H = ... 会把它
                    # 就地覆盖成整数，之后 check() 里任何一处 W(...) 都 TypeError。
                    # 也就是说：只要传了 --figures 且课件有**一条**告警，复核就崩。
                    iw, ih = rgba.size
                    flat = Image.alpha_composite(
                        Image.new("RGBA", rgba.size, (255, 255, 255, 255)), rgba
                    ).convert("RGB")
                    mask = ImageChops.difference(
                        flat, Image.new("RGB", flat.size, (255, 255, 255))
                    ).convert("L").point(lambda v: 255 if v > 12 else 0)
                    box = mask.getbbox()
                # 自己量一遍源图的着墨带，不复用渲染器的判断 —— 复核要独立于被检代码
                src_ink[h] = ((box[1] / ih, box[3] / ih) if box else (0.0, 1.0))
        except ImportError:
            info.append("未装 Pillow，跳过「图片拉伸」与「着墨一致性」检查")

    def vis_ink_h(p):
        """这张图在版面上**看得见的图形**有多高（英寸）。

        图框高度不算数：源图可能四周补了白边，渲染器也可能用 a:srcRect 裁掉了
        白边。要拿"显示区"与"源图着墨带"的交集来算 —— 否则三个补白成方形的
        文件会量出三个相同的框高，而实际图形高度差近一倍，正是要抓的那个毛病。
        量不到（源图不在 --figures 里 / 没装 Pillow）返回 None，不冒充通过。
        """
        try:
            h = hashlib.md5(p.image.blob).hexdigest()
        except Exception:
            return None
        if h not in src_ink:
            return None
        t0, b0 = src_ink[h]                      # 源图着墨带（比例）
        cl, cr, ct, cb = src_crop(p)             # 显示区（比例）
        d0, d1 = ct, 1.0 - cb
        if d1 - d0 <= 0.01:
            return None
        overlap = max(0.0, min(b0, d1) - max(t0, d0))
        return inch(p.height) * overlap / (d1 - d0)

    gutters = []          # 全部并排页的 (左空 − 右空)，用于求本册的图文间隙

    for si, slide in enumerate(prs.slides, 1):
        shapes = list(slide.shapes)
        pics = [s for s in shapes if is_pic(s)]
        txts = [s for s in shapes if is_txt(s)]
        n_txt = len(txts)

        # 底部堆叠区（强调条 / 驱动问题）的顶边
        stack_top = BODY_BOTTOM
        for sh in shapes:
            t = inch(sh.top)
            if BODY_BOTTOM - 1.5 <= t < BODY_BOTTOM and not is_pic(sh):
                szs = [r.font.size.pt for p in sh.text_frame.paragraphs
                       for r in p.runs if r.font.size] if sh.has_text_frame else []
                if szs and max(szs) <= 32 and inch(sh.height) < 1.2:
                    stack_top = min(stack_top, t)

        # ---- 越界
        for sh in shapes:
            l, t = inch(sh.left), inch(sh.top)
            r, b = l + inch(sh.width), t + inch(sh.height)
            if l < -TOL_BOUNDS or t < -TOL_BOUNDS or r > SLIDE_W + TOL_BOUNDS or b > SLIDE_H + TOL_BOUNDS:
                E(si, f"越出画布：{sh.name} [{l:.2f},{t:.2f} → {r:.2f},{b:.2f}]",
                  cat="verify.shape.offscreen", shape=sh.name)
            elif r > CONTENT_R + TOL_BOUNDS or l < CONTENT_L - TOL_BOUNDS:
                # value = 溢出量（英寸），取左右两边大的那个 —— 阈值判据靠它。
                W(si, f"越出版心：{sh.name} 左 {l:.2f} 右 {r:.2f}（版心 {CONTENT_L:.2f}~{CONTENT_R:.2f}）",
                  cat="verify.shape.outside_content", shape=sh.name,
                  value=max(CONTENT_L - l, r - CONTENT_R))

        # ---- 图片：拉伸
        for p in pics:
            try:
                h = hashlib.md5(p.image.blob).hexdigest()
            except Exception:
                continue
            ar_shape = p.width / p.height if p.height else 0
            if h in src_ar:
                ar_src, fname = src_ar[h]
                cl, cr, ct, cb = src_crop(p)
                if (1 - cl - cr) > 0.01 and (1 - ct - cb) > 0.01:
                    ar_src = ar_src * (1 - cl - cr) / (1 - ct - cb)
                if ar_src and abs(ar_shape - ar_src) / ar_src > TOL_AR:
                    E(si, f"图片被拉伸：{fname} 源比例 {ar_src:.3f} → 版面 {ar_shape:.3f}",
                      cat="verify.pic.stretched", shape=fname,
                      value=abs(ar_shape - ar_src) / ar_src)

        # ---- 图片分组（按竖直重叠 >50% 视为同一排）
        groups = []
        for p in sorted(pics, key=lambda s: s.left):
            for g in groups:
                ga = g[0]
                ov = min(ga.top + ga.height, p.top + p.height) - max(ga.top, p.top)
                if ov > 0.5 * min(ga.height, p.height):
                    g.append(p)
                    break
            else:
                groups.append([p])

        for g in groups:
            gl = min(s.left for s in g)
            gr = max(s.left + s.width for s in g)
            gt = min(s.top for s in g)
            gb = max(s.top + s.height for s in g)

            # 左侧文字列（整块在图的左边且竖直重叠）→ 图栏从它的右边 + 间隙起算。
            # 重叠门槛取 10%：文字块常常比图矮得多（一页三行字配一张满高的图，
            # 重叠也只有 30% 上下），门槛一高就认不出这个文字列，进而把"图在自己
            # 栏里居中"误判成"图没居中"。
            cont_l = CONTENT_L
            cont_r = CONTENT_R
            mate = None
            mate_side = None
            for t in txts:
                ov = min(t.top + t.height, gb) - max(t.top, gt)
                if ov > 0.1 * (gb - gt) and (t.left + t.width) <= gl + EMU * 0.05:
                    if t.left + t.width > cont_l * EMU:
                        cont_l = inch(t.left + t.width)
                        mate = t
                        mate_side = "left"
            # 右边那一栏的文字块也要认。此前只找图**左边**的文字（左文右图），
            # 于是 [两栏] 把图放在 ## 左 时会找不到 mate，退化成「要求图在整页
            # 版心里居中」，误报「图片未水平居中」—— 而 ## 左/## 右 是文档里
            # 写着的合法写法，渲染器也确实那样产出。两边都找，才是真的「图在
            # 自己那一栏里居中」。
            for t in txts:
                ov = min(t.top + t.height, gb) - max(t.top, gt)
                if ov > 0.1 * (gb - gt) and t.left >= gr - EMU * 0.05:
                    if inch(t.left) < cont_r:
                        cont_r = inch(t.left)
                        mate = t
                        mate_side = "right"
            lg = inch(gl) - cont_l
            rg = cont_r - inch(gr)
            # 栏间隙该减外边距，可这两项哪边是哪个，取决于文字在图左还是图右：
            #   左文右图：lg = 栏间隙(0.613)、rg = 外边距(0.113) → lg − rg = 0.500
            #   左图右文：lg = 外边距(0.113)、rg = 栏间隙(0.614) → rg − lg = 0.501
            # 两种排布渲染器给的数**完全镜像**，所以只差一个符号。原来固定算
            # lg − rg，图在左时就得到 −0.501，被当成「图文间隙为负 —— 图压到了
            # 文字列上」误报。按 mate 在哪一侧取符号，两种排布才是同一条判据。
            d = (rg - lg) if mate_side == "right" else (lg - rg)

            if len(g) == 1:
                gutters.append((si, mate is not None, d))
                if mate is None and abs(lg - rg) > TOL_CENTER:
                    E(si, f"图片未水平居中：{g[0].name} 左空 {lg:.3f}in / 右空 {rg:.3f}in",
                      cat="verify.pic.offcenter", shape=g[0].name, value=abs(lg - rg))
            else:
                if abs(d) > TOL_CENTER:
                    E(si, f"一排 {len(g)} 张图整体未居中：左空 {lg:.3f} / 右空 {rg:.3f}",
                      cat="verify.row.off_center", value=abs(d))
                gaps = [inch(g[i + 1].left - (g[i].left + g[i].width)) for i in range(len(g) - 1)]
                if gaps and (max(gaps) - min(gaps)) > 0.02:
                    E(si, f"一排图间距不均：{['%.3f' % x for x in gaps]}",
                      cat="verify.row.gap_uneven", value=max(gaps) - min(gaps))
                # 流程页的判据：一排图垂直中线对齐（箭头串起来），且**着墨高度一致**。
                # 裁切之后图框就是着墨区，所以直接比 height 就是在比看得见的图形高度 ——
                # 这一条正是"A5 之前第三个锥体只有前两个一半高"的验收标准。
                cys = [inch(s.top + s.height / 2) for s in g]
                if max(cys) - min(cys) < 0.05:
                    hs = [vis_ink_h(s) for s in g]
                    if all(x is not None for x in hs) and max(hs) - min(hs) > 0.02:
                        E(si, f"流程页同组图着墨高度不一致："
                              f"{['%.3f' % x for x in hs]}"
                              f"（{max(hs) / min(hs):.2f} 倍差距；"
                              f"同一尺度是这一页能被读懂的前提）",
                          cat="verify.flow.ink_mismatch", value=max(hs) / min(hs))

        # ---- 图片与文字着墨重叠（只对左文右图那种真并排查，框重叠常有）
        for p in pics:
            for t in txts:
                if not (p.left < t.left + t.width and t.left < p.left + p.width):
                    continue
                inkh = est_ink_h(t, inch(t.width))
                ink_top = inch(t.top) if anchor_of(t) in ("t", None) else \
                    inch(t.top) + (inch(t.height) - inkh) / 2
                ink_bot = ink_top + inkh
                if ink_top < gb / EMU and ink_bot > gt / EMU:
                    if p.left < t.left + t.width * 0.98:
                        W(si, f"图片与文字可能重叠：{p.name} 与 {t.name}",
                          cat="verify.overlap.pic_text", shape=p.name)

        # ---- 正文块明显溢出正文区
        #
        # **每页最高的那个文字块是标题，不参与这条检查。** 标题按定义就坐在正文
        # 区之上，拿它去比「正文区顶」必然误报。
        #
        # 实测事故：基线那份课件的节标题是 30pt、框高正好 1.00in —— 两道守卫
        # （字号 > 40 算标题、高度 < 1.0 跳过）一道都没拦住，于是 10 页里报了 9 页
        # 「正文块上沿高于正文区顶」。可那份课件的正文规规矩矩从 1.90in 起排，
        # **一个毛病都没有**。技能自己的产出躲过这条纯属侥幸：它的标题框 0.79in，
        # 恰好卡在高度守卫外面。
        #
        # 这条误报很毒：它长得像最硬的那种信号（纯几何、可重复、只有一方触发），
        # 差点被当成「基线和技能的唯一区分点」。所以排掉它的同时必须配对照，
        # 证明检查没被修哑 —— 见 fixtures/mutate_pptx.py 的 body-rides-up。
        title_sh = min(txts, key=lambda s: s.top) if txts else None
        for t in txts:
            if t is title_sh:
                continue
            tszs = [r.font.size.pt for p in t.text_frame.paragraphs for r in p.runs if r.font.size]
            if not tszs or max(tszs) > 40 or inch(t.height) < 1.0:
                continue
            inkh = est_ink_h(t, inch(t.width))
            top, bot = inch(t.top), inch(t.top + t.height)
            ink_top = top if anchor_of(t) in ("t", None) else top + (bot - top - inkh) / 2
            ink_bot = ink_top + inkh
            if ink_top < BODY_Y - TOL_OVERFLOW:
                # 这一条是五个真卡组里唯一一条**只有基线触发**的告警
                # （基线 9/10 页，技能产出 0、人写的参赛稿 0）。正文从 0.45in
                # 起排而正文区从 1.42in 起 —— 正文骑到标题带上，等于没有标题带。
                W(si, f"正文块 {t.name} 上沿高于正文区顶 {BODY_Y}：{ink_top:.3f}in",
                  cat="verify.body.above_area", shape=t.name, value=BODY_Y - ink_top)
            if ink_bot > stack_top + TOL_OVERFLOW:
                W(si, f"正文块 {t.name} 下沿 {ink_bot:.3f}in 压到堆叠区顶 {stack_top:.3f}in",
                  cat="verify.body.into_stack", shape=t.name, value=ink_bot - stack_top)

        # ---- 字体
        for sh in shapes:
            if not sh.has_text_frame:
                continue
            for p in sh.text_frame.paragraphs:
                for run in p.runs:
                    if not run.text.strip():
                        continue
                    latin, ea = font_of(run)
                    for role, v in (("latin", latin), ("ea", ea)):
                        if v not in FONT_ALLOWED:
                            E(si, f"字体不在契约内：{sh.name} 的 a:{role}={v!r}（{run.text[:12]}）",
                              cat="verify.font.contract", shape=sh.name)
                    if latin and "Times" in latin:
                        E(si, f"出现 Times New Roman：{sh.name}",
                          cat="verify.font.times", shape=sh.name)

        # ---- 行距必须绝对（封面是单行元素，不参与高度模型，跳过）
        for sh in shapes:
            if si == 1 or not sh.has_text_frame or inch(sh.height) < 1.0:
                continue
            for p in sh.text_frame.paragraphs:
                if not "".join(r.text for r in p.runs).strip():
                    continue
                k = spacing_kind(p)
                if k == "pct":
                    E(si, f"行距写成百分比 spcPct：{sh.name}",
                      cat="verify.spacing.pct", shape=sh.name)
                elif k is None:
                    W(si, f"行距未显式指定：{sh.name}",
                      cat="verify.spacing.missing", shape=sh.name)

        # ---- 内页页脚
        if si > 1:
            for sh in txts:
                body = sh.text_frame.text.strip()
                if any(k in body for k in FOOTER_KEYS):
                    E(si, f"内页出现课题/教材出处：{sh.name}｜{body[:40]}",
                      cat="verify.footer.leak", shape=sh.name)

        # ---- 同页重复长文本
        # 按**形状身份**收，不按名字收。
        # 原来收的是 sh.name：同名同文的两块会并成一个名字，len==1 就不报。
        # 而「渲染器把同一块吐了两次」恰恰必然同名 —— 也就是说，这条检查
        # 唯一漏掉的情形，正是它最该抓的那个。改成按 id(sh) 计数：
        # 两个形状 → 两条记录 → 报；同一形状里同段文字出现两次 → 仍是一条。
        seen = defaultdict(dict)      # norm -> {id(sh): sh.name}
        for sh in shapes:
            if not sh.has_text_frame:
                continue
            for t, *_ in paras(sh):
                norm = "".join(t.split())
                if len(norm) >= 8:
                    seen[norm][id(sh)] = sh.name
        for norm, by_shape in seen.items():
            if len(by_shape) > 1:
                names = sorted(by_shape.values())
                E(si, f"同页重复文本（{len(names)} 处）："
                      f"{'/'.join(names)}｜{norm[:30]}",
                  cat="verify.text.duplicate", value=len(names))

        # ---- 要点条数 / 页信息
        for sh in shapes:
            if not sh.has_text_frame or inch(sh.height) < 1.0:
                continue
            n = len(paras(sh))
            if n > 6:
                W(si, f"要点 {n} 行（规则 7 上限 6）：{sh.name}",
                  cat="verify.bullets.too_many", shape=sh.name, value=n)

        title = ""
        if txts:
            first = min(txts, key=lambda s: s.top)
            title = first.text_frame.text.strip().replace("\n", " ")[:20]
        info.append(f"P{si:<2} 形状 {len(shapes)}（图 {len(pics)}）"
                    f" 标题「{title}」")

    # ---- 并排页的图文间隙
    # 左空−右空 正好等于该版式族的栏间隙：[标题] 并排是 0.35，[两栏] 是 0.50。
    # 两个族本来就用不同的栏间隙，所以不跨族比"一致性"，只查有没有离谱的值 ——
    # 负数说明图压到文字列上，过大说明图被甩到离文字很远的地方。
    if gutters:
        FAMILY_GAPS = {0.35, 0.50}
        for si, has_mate, d in gutters:
            if not has_mate:
                continue
            if d < -TOL_CENTER:
                E(si, f"图文间隙为负（{d:.3f}in）：图压到了文字列上",
                  cat="verify.gap.negative", value=d)
            elif d > 0.60:
                W(si, f"图文间隙偏大：{d:.3f}in，图离文字列太远",
                  cat="verify.gap.large", value=d)
            elif abs(d - 0.35) > TOL_CENTER and abs(d - 0.50) > TOL_CENTER:
                W(si, f"图文间隙 {d:.3f}in 不属于任何一个已知版式族（0.35 / 0.50）",
                  cat="verify.gap.unknown_family", value=d)
        info.append(f"并排页图文间隙（左空−右空）：{['%.3f' % d for _, _, d in gutters]}")
        info.append("→ 等于栏间隙即说明图是在自己那一栏里居中的（0.35=[标题]并排，0.50=[两栏]）")

    return {"prs": prs, "errors": errs, "warns": warns, "info": info}


def check(path, figures_dir=None):
    """向后兼容的薄包装：老调用方要 `(prs, errors, warns, info)`，
    且 errors / warns 里是 `(页号, 消息)` 二元组。

    **别把这个契约改掉。** `evals/fixtures/test_ink_check.py` 里写的是
    `for _, m in errs`，`mutate_pptx.py` 里写的是 `x[1] if isinstance(x, tuple)` ——
    两者都是回归层的一部分，改了这里就会静默打断 13 条变异断言。
    要类别标签请用 `scan()`。
    """
    r = scan(path, figures_dir)
    return (r["prs"],
            [(x["page"], x["msg"]) for x in r["errors"]],
            [(x["page"], x["msg"]) for x in r["warns"]],
            r["info"])


def main():
    # 输出编码必须写死，理由和 SKILL.md 里那条读 docx 的命令一样：Windows 上
    # Python 的 stdout 默认走 GBK，而本脚本会 print `✓`（U+2713）。实测——一份
    # **完全合格**的课件跑出来是 UnicodeEncodeError + 退出码 1，也就是说脚本
    # 恰好在"没问题"的时候崩溃并报失败。这类失败最难查：它长得像真 bug。
    # 顺带解决管道/重定向出去的中文变乱码。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("pptx")
    ap.add_argument("--figures", default=None)
    ap.add_argument("--info", action="store_true")
    ap.add_argument("--json", action="store_true",
                    help="打成 JSON 而不是中文报告。给基准用 —— 它要按类别计分，"
                         "不该去正则匹配提示语里的中文散文。")
    a = ap.parse_args()

    r = scan(a.pptx, a.figures)
    prs, errs, warns, info = r["prs"], r["errors"], r["warns"], r["info"]
    n = len(prs.slides._sldIdLst)

    if a.json:
        # 人类报告走 stdout 是给眼睛看的；机器读数也走 stdout，但只有一份 ——
        # `--json` 时不打中文报告，否则调用方得在一堆散文里找那个 JSON。
        print(json.dumps({
            "file": a.pptx,
            "slides": n,
            "canvas_emu": [prs.slide_width, prs.slide_height],
            "errors": errs, "warns": warns,
            "n_errors": len(errs), "n_warns": len(warns),
        }, ensure_ascii=False, indent=1))
        return 1 if errs else 0

    print(f"文件：{a.pptx}")
    print(f"画布：{prs.slide_width}×{prs.slide_height} EMU "
          f"({prs.slide_width / EMU:.5f}×{prs.slide_height / EMU:.5f} in)")
    print(f"页数：{n}")
    print(f"结论：ERROR {len(errs)} 条，WARN {len(warns)} 条\n")
    for x in errs:
        print(f"[ERROR] P{x['page']} {x['msg']}")
    for x in warns:
        print(f"[WARN ] P{x['page']} {x['msg']}")
    if a.info:
        print("\n--- 逐页信息 ---")
        for x in info:
            print(" ", x)
    if not errs and not warns:
        print("✓ 全部检查通过")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
