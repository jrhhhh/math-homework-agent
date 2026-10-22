#!/usr/bin/env python3
"""按声明式清单批量生成课件配图（静态图与 GIF 动画）。

用法:
    python make_figures.py figures.json -o figures/
    python make_figures.py --check-fonts

设计要点:
  - 用 JSON 而非 YAML 声明（本机未安装 pyyaml，且 JSON 无歧义、零依赖）。
  - 数学表达式用 sympy 解析后 lambdify 成 numpy 函数。表达式写错时立刻报错，
    好过画出一张形状可疑但"看着像"的图 —— 后者会一路混进课件里。
  - 中文字体配置在模块顶层完成，见 _setup_fonts()。
"""

import argparse
import json
import os
import sys

# Windows 控制台默认走 GBK，打印 ✓ 这类符号会抛 UnicodeEncodeError 而中断出图。
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import matplotlib

matplotlib.use("Agg")

import numpy as np

# --------------------------------------------------------------------------
# 中文字体配置
#
# matplotlib 默认字体不含中文字形，中文标签会渲染成一串方框（豆腐块），
# 而且**不报错** —— 图能正常生成，只是字全是空框。这是本脚本最容易踩的坑，
# 所以放在最前面，并在 --check-fonts 里提供显式校验。
# --------------------------------------------------------------------------
FONT_CANDIDATES = ["Microsoft YaHei", "SimHei", "SimSun", "KaiTi"]
matplotlib.rcParams["font.sans-serif"] = FONT_CANDIDATES + ["DejaVu Sans"]
# 中文环境下负号走 Unicode U+2212，雅黑无此字形，会显示成方框。必须关掉。
matplotlib.rcParams["axes.unicode_minus"] = False

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

# 与 SKILL.md 内置版式一致的配色。避免红绿同时高饱和，兼顾色觉障碍学生。
C = {
    "main": "#2b6cb0",   # 主曲线 / 主对象
    "aux": "#718096",    # 辅助线、参考线
    "hi": "#dd6b20",     # 强调：切线、目标对象
    "trail": "#a0aec0",  # 渐隐：逼近过程中的中间态
    "text": "#1a202c",   # 文字与标注
    "fill": "#bee3f8",   # 填充
}

DPI = 200
GIF_DPI = 110


# --------------------------------------------------------------------------
# 基础设施
# --------------------------------------------------------------------------

def setup(verbose=True, prefer=None):
    """确认中文字体可用，返回实际解析到的字体名。

    默认刻意用无衬线（微软雅黑）：图内标签字号小，衬线体在投影距离下笔画
    糊成一团。这与课件正文用华文中宋（衬线）是**有意的不一致**，不是疏漏。
    确实需要统一时，在 figures.json 顶层写 `"font": "华文中宋"` 覆盖。
    """
    from matplotlib import font_manager

    order = ([prefer] if prefer else []) + FONT_CANDIDATES
    available = {f.name for f in font_manager.fontManager.ttflist}
    resolved = next((n for n in order if n in available), None)

    if resolved is None:
        sys.stderr.write(
            "警告: 未找到任何中文字体 %s\n"
            "      图形中的中文将渲染为方框。请安装其中一种字体，\n"
            "      或在 FONT_CANDIDATES 中补充本机已有的中文字体名。\n"
            % order
        )
    else:
        plt.rcParams["font.sans-serif"] = [resolved] + order + ["DejaVu Sans"]
        if verbose:
            print(f"  中文字体: {resolved}")
    return resolved


def compile_expr(expr, var="x"):
    """把表达式字符串编译成可作用于 numpy 数组的函数。

    用 sympy 解析而非 eval：报错信息会指出具体位置，且能直接做符号求导
    （见 df 省略时自动求导）。
    """
    import sympy as sp

    sym = sp.Symbol(var)
    try:
        parsed = sp.sympify(expr)
    except (sp.SympifyError, SyntaxError) as e:
        raise ValueError(f"表达式无法解析: {expr!r}\n  {e}") from e
    return sp.lambdify(sym, parsed, "numpy"), parsed, sym


def sp_derivative_fn(parsed, sym):
    """符号求导后编译。用于 df 省略时自动推导切线斜率。"""
    import sympy as sp

    return sp.lambdify(sym, sp.diff(parsed, sym), "numpy")


def trim_white(path, pad=10, tol=6):
    """裁掉纯白边。

    `bbox_inches="tight"` 裁的是**坐标区**，不是**画出来的内容**。对 3D 图尤其致命：
    mplot3d 无论 `figsize` 和 `set_box_aspect` 怎么设，都恒定输出正方形画布，
    而内容只占中间一条横带 —— 实测 (8.2, 3.6) 的画幅出来仍是 297×297。
    不裁的话，这张图插进版面会按高度被压缩得很小，两侧留一大片空白。

    用与白底的像素差找边界。容差 6 是为了避开抗锯齿产生的极浅灰噪点。
    """
    from PIL import Image, ImageChops

    im = Image.open(path).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    mask = ImageChops.difference(im, bg).convert("L").point(lambda p: 255 if p > tol else 0)
    box = mask.getbbox()
    if not box:
        return path

    l, t, r, b = box
    l, t = max(0, l - pad), max(0, t - pad)
    r, b = min(im.width, r + pad), min(im.height, b + pad)
    if (r - l, b - t) == im.size:
        return path

    im.crop((l, t, r, b)).save(path)
    return path


def pad_to_aspect(path, ar):
    """把图补白到指定宽高比（ar = 宽/高），内容居中。

    trim_white 之后长宽比由内容决定，同一组流程图的画幅可能差很多 ——
    实测棱柱分割那组从 0.62（竖幅）到 1.81（横幅），并排在一页里第三个明显
    矮一截。给 `figures.json` 里同组的图都写 `"aspect": 1.0` 就能出一排
    整齐的方格。

    这是**可选**的美化，不是流程页能用的前提：[流程] 渲染器本身就会在单格内
    等比缩放并双向居中，长宽比不一致也能正确排布。
    """
    from PIL import Image

    im = Image.open(path).convert("RGB")
    w, h = im.size
    if w / h < ar:                 # 太瘦 → 补宽
        nw, nh = int(round(h * ar)), h
    else:                          # 太胖 → 补高
        nw, nh = w, int(round(w / ar))
    if (nw, nh) == (w, h):
        return path

    canvas = Image.new("RGB", (nw, nh), (255, 255, 255))
    canvas.paste(im, ((nw - w) // 2, (nh - h) // 2))
    canvas.save(path)
    return path


def save(fig, path, aspect=None):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    # 白底很重要：透明底在深色 PowerPoint 主题下会看不清坐标轴。
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    trim_white(path)
    if aspect:
        pad_to_aspect(path, float(aspect))
    size_kb = os.path.getsize(path) / 1024
    print(f"  ✓ {path}  ({size_kb:.0f} KB)")
    return path


def new_axes(size, is3d=False):
    fig = plt.figure(figsize=tuple(size), dpi=DPI)
    if is3d:
        ax = fig.add_subplot(111, projection="3d")
        ax.set_axis_off()  # 课件里的立体图不需要坐标轴
    else:
        ax = fig.add_subplot(111)
        ax.grid(alpha=0.25, ls=":")
        ax.spines[["top", "right"]].set_visible(False)
    return fig, ax


# --------------------------------------------------------------------------
# recipes
# --------------------------------------------------------------------------

def recipe_function(spec, out):
    """函数图像 + 坐标轴。用于引入情境（如跳水轨迹）。"""
    f, _, _ = compile_expr(spec["f"])
    xlim = spec.get("xlim", [-3, 3])
    fig, ax = new_axes(spec.get("size", [6.0, 4.0]))

    x = np.linspace(xlim[0], xlim[1], 500)
    ax.plot(x, f(x), lw=2.5, color=C["main"], label=spec.get("label", ""))

    ax.axhline(0, color=C["aux"], lw=0.8)
    ax.axvline(0, color=C["aux"], lw=0.8)

    if spec.get("xlabel"):
        ax.set_xlabel(spec["xlabel"], fontsize=12, color=C["text"])
    if spec.get("ylabel"):
        ax.set_ylabel(spec["ylabel"], fontsize=12, color=C["text"])
    if spec.get("label"):
        ax.legend(fontsize=12, frameon=False)

    # 可选：标注某个点（如运动员起跳点、顶点）
    for pt in spec.get("points", []):
        ax.plot([pt[0]], [pt[1]], "o", color=C["hi"], ms=6, zorder=5)
        if len(pt) > 2:
            ax.annotate(pt[2], pt[:2], textcoords="offset points",
                        xytext=(8, 6), fontsize=12, color=C["text"])

    return save(fig, out, spec.get("aspect"))


def _draw_secants(ax, f, x0, hs):
    """在 ax 上叠加一族割线：h 越小颜色越深，让'逼近'在静态图上也能读出来。"""
    n = max(len(hs) - 1, 1)
    for i, h in enumerate(hs):
        k = (f(x0 + h) - f(x0)) / h
        xs = np.array([x0 - 0.8, x0 + h + 0.8])
        ax.plot(xs, f(x0) + k * (xs - x0), lw=1.8, color=C["trail"],
                alpha=0.35 + 0.5 * i / n)
        ax.plot([x0, x0 + h], [f(x0), f(x0 + h)], "o",
                color=C["trail"], ms=4, alpha=0.6)


def recipe_secant(spec, out):
    """割线逼近切线（静态版）：一张图上凝固整个逼近过程。

    这是"导数"一课最有价值的配图。三条割线足以表达趋势，再多就糊成一团。
    """
    f, parsed, sym = compile_expr(spec["f"])
    df = (compile_expr(spec["df"])[0] if spec.get("df")
          else sp_derivative_fn(parsed, sym))
    x0 = float(spec.get("x0", 1.0))
    hs = spec.get("hs", [1.0, 0.5, 0.2])

    fig, ax = new_axes(spec.get("size", [7.5, 4.2]))
    x = np.linspace(x0 - 1.5, x0 + 2.5, 500)
    ax.plot(x, f(x), lw=2.5, color=C["main"], label=spec.get("label", ""))

    _draw_secants(ax, f, x0, hs)

    # 切线最后画，压在割线之上
    k = float(df(x0))
    xs = np.array([x0 - 1.2, x0 + 1.4])
    ax.plot(xs, f(x0) + k * (xs - x0), lw=2.2, color=C["hi"], ls="--",
            label=f"切线 k={k:g}")
    ax.plot([x0], [f(x0)], "o", color=C["text"], ms=6, zorder=5)
    ax.annotate("P", (x0, f(x0)), textcoords="offset points",
                xytext=(-14, 6), fontsize=13, color=C["text"])
    ax.legend(fontsize=12, frameon=False)
    return save(fig, out, spec.get("aspect"))


def recipe_secant_gif(spec, out):
    """割线逼近切线的 GIF 动画。

    只有当'连续逼近'的渐近感本身是教学重点时才用。否则优先流程页
    （同一页上排开静态多帧），因为 GIF 对播放环境有要求，且体积大。
    """
    f, parsed, sym = compile_expr(spec["f"])
    df = (compile_expr(spec["df"])[0] if spec.get("df")
          else sp_derivative_fn(parsed, sym))
    x0 = float(spec.get("x0", 1.0))
    n = int(spec.get("frames", 40))
    h0, h1 = spec.get("h_range", [1.0, 0.02])

    fig = plt.figure(figsize=tuple(spec.get("size", [7.5, 4.2])), dpi=GIF_DPI)
    ax = fig.add_subplot(111)
    x = np.linspace(x0 - 1.5, x0 + 2.5, 400)
    kt = float(df(x0))

    def draw(i):
        ax.clear()
        # 按几何衰减取 h：线性递减时前半段看不出变化、后半段跳得太快，
        # 观感是"卡住然后突然结束"。
        h = h0 * (h1 / h0) ** (i / max(n - 1, 1))
        ax.plot(x, f(x), lw=2.5, color=C["main"])

        k = (f(x0 + h) - f(x0)) / h
        xs = np.array([x0 - 0.8, x0 + h + 0.8])
        ax.plot(xs, f(x0) + k * (xs - x0), lw=1.8, color=C["trail"])
        ax.plot([x0, x0 + h], [f(x0), f(x0 + h)], "o", color=C["trail"], ms=5)

        xt = np.array([x0 - 1.2, x0 + 1.4])
        ax.plot(xt, f(x0) + kt * (xt - x0), lw=2.2, color=C["hi"], ls="--")
        ax.plot([x0], [f(x0)], "o", color=C["text"], ms=6)

        ax.set_title(f"Δt = {h:.3f}     k = {k:.3f}", fontsize=13,
                     color=C["text"])
        ax.grid(alpha=0.25, ls=":")
        ax.spines[["top", "right"]].set_visible(False)

    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    FuncAnimation(fig, draw, frames=n).save(out, writer=PillowWriter(fps=15))
    plt.close(fig)
    size_mb = os.path.getsize(out) / 1024 / 1024
    print(f"  ✓ {out}  ({size_mb:.1f} MB, {n} 帧)")
    if size_mb > 2:
        print("    ! 超过 2MB，放映可能卡顿。试试调小 frames 或 size。")
    return out


def recipe_cylinder(spec, out):
    """带等高截面的柱体。用于祖暅原理、柱锥体积。"""
    r = float(spec.get("r", 1.0))
    h = float(spec.get("h", 2.0))
    z = float(spec.get("z", 1.2))

    fig, ax = new_axes(spec.get("size", [5.2, 4.0]), is3d=True)

    t = np.linspace(0, 2 * np.pi, 60)
    T, Z = np.meshgrid(t, np.linspace(0, h, 30))
    ax.plot_surface(r * np.cos(T), r * np.sin(T), Z,
                    color=C["fill"], alpha=0.35, linewidth=0)

    ax.plot(r * np.cos(t), r * np.sin(t), z, color=C["hi"], lw=2.2)  # 截面

    for zc in (0, h):
        ax.plot(r * np.cos(t), r * np.sin(t), zc, color=C["main"], lw=1.2)

    # 按真实比例设 box aspect，否则圆柱会被压成扁饼
    ax.set_box_aspect((1, 1, h / (2 * r)))
    ax.view_init(elev=18, azim=-58)  # 立体感与可读性的折中角度
    return save(fig, out, spec.get("aspect"))


def recipe_cone(spec, out):
    """圆锥，标注底面半径 r 与高 h。

    用于例题「已知底面半径 r、高 h，求体积 V」的配图 —— 题面里的 r 和 h 得在图上
    看得见，否则学生要自己在脑子里对号入座。

    参数与 `recipe_cylinder` 同名同默认值（r/h/size/aspect），视角也一致
    （elev=18, azim=-58）：这一课的推理是「锥是等底等高柱的 1/3」，两张图分别看时
    还好，一旦并排或前后翻页，比例或视角不一致就把那个关系看没了。
    """
    r = float(spec.get("r", 1.0))
    h = float(spec.get("h", 2.0))
    label_r = spec.get("label_r", "r")
    label_h = spec.get("label_h", "h")

    fig, ax = new_axes(spec.get("size", [5.2, 4.0]), is3d=True)

    # 用 (T, S) 参数化：S=0 是顶点，S=1 是底面。底面半径随 S 线性张开 —— 这就是
    # 圆锥区别于圆柱的地方，所以不能用 recipe_cylinder 那种等半径的网格。
    t = np.linspace(0, 2 * np.pi, 60)
    T, S = np.meshgrid(t, np.linspace(0, 1, 30))
    ax.plot_surface(r * S * np.cos(T), r * S * np.sin(T), h * (1 - S),
                    color=C["fill"], alpha=0.35, linewidth=0)

    ax.plot(r * np.cos(t), r * np.sin(t), 0, color=C["main"], lw=1.2)   # 底面圆
    # 高画成虚线：它是辅助线，不是几何体的边（与实线的母线区分开）
    ax.plot([0, 0], [0, 0], [0, h], color=C["hi"], lw=1.6, ls="--")
    ax.plot([0, r], [0, 0], [0, 0], color=C["hi"], lw=1.6)              # 半径

    ax.text(0, 0, h + 0.06 * h, label_h, color=C["hi"], fontsize=13,
            ha="center", va="bottom")
    ax.text(r * 0.5, 0, 0, label_r, color=C["hi"], fontsize=13,
            ha="center", va="top")

    # 与 recipe_cylinder 同一句、同一个理由：不按真实比例设 box aspect，
    # 圆锥会被压成扁饼。
    ax.set_box_aspect((1, 1, h / (2 * r)))
    ax.view_init(elev=18, azim=-58)
    return save(fig, out, spec.get("aspect"))


def recipe_stacked_books(spec, out):
    """叠书 → 斜推。祖暅原理的情境引入用。

    这个不需要 3D：2D 矩形叠出的"斜推"比三维透视图更清楚，
    而且"每本书没变→体积没变"的推理一眼可见。
    """
    n = int(spec.get("n", 7))
    shear = float(spec.get("shear", 0.35))

    fig, ax = plt.subplots(figsize=tuple(spec.get("size", [6.0, 4.0])), dpi=DPI)
    for i in range(n):
        ax.add_patch(plt.Rectangle((i * shear, i), 2.4, 0.9,
                                   facecolor=C["fill"], edgecolor=C["main"],
                                   lw=1.6))
    ax.annotate("", xy=(n * shear + 2.4, 0.45), xytext=(2.4, 0.45),
                arrowprops=dict(arrowstyle="->", color=C["hi"], lw=2))
    ax.text(n * shear + 1.2, -0.15, spec.get("arrow_label", "斜推"),
            color=C["hi"], fontsize=13, ha="center")

    ax.set_xlim(-0.4, n * shear + 3.2)
    ax.set_ylim(-0.8, n + 0.6)
    ax.set_aspect("equal")
    ax.axis("off")
    return save(fig, out, spec.get("aspect"))


def _tetra_faces(v):
    """四面体的四个三角面。v 是 4×3 顶点数组。"""
    return [[v[0], v[1], v[2]], [v[0], v[1], v[3]],
            [v[0], v[2], v[3]], [v[1], v[2], v[3]]]


def recipe_prism_split(spec, out):
    """三棱柱分割成三个等体积三棱锥，输出三张递进的图。

    推导 V = 1/3·Sh 的关键可视化。三张静态图排在同一页（流程页）比做动画更清楚 ——
    学生能同时看到原棱柱和切出的锥，拆成三张幻灯片翻过去就丢了这个对照。

    三张的着墨形状本来就不同（第 3 步要宽画幅才能把三个锥横向排开）：前两步约 0.6，
    第三步约 1.9。流程页按着墨区等比排，形状差这么多时第三步会被迫缩到和前两步同高，
    横向铺满剩下的宽度 —— 结果是能看，但整排会偏小。

    想让这一页更饱满，正确做法是**改这一组图的形状**（比如把第 3 步的三个锥排得更
    紧凑一些，让它的着墨区接近前两步），而不是配 `"aspect": 1.0` 补白：补白只改变
    文件画布，渲染器量的是着墨区，会把白边裁掉再排，所以补不出任何效果。

    分割方式（A 为下底，B 为上底，Bᵢ = Aᵢ 正上方）：
        T1 = A₀A₁A₂B₂    T2 = A₀A₁B₂B₁    T3 = A₀B₁B₂B₀
    三者体积均为 Sh/3，这正是课本采用的经典分法。
    """
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    # 第 3 步要横向排开三个锥，所以用更宽的画幅；前两步用常规竖幅
    gap = float(spec.get("gap", 2.2))
    wide = spec.get("wide_size", [8.2, 3.6])
    normal = spec.get("size", [5.2, 4.0])
    A = np.array([[0.0, 0.0, 0.0], [1.6, 0.0, 0.0], [0.8, 1.4, 0.0]])
    B = A + np.array([0.0, 0.0, 2.0])

    tetras = [
        (np.array([A[0], A[1], A[2], B[2]]), "#2b6cb0"),
        (np.array([A[0], A[1], B[2], B[1]]), "#dd6b20"),
        (np.array([A[0], B[1], B[2], B[0]]), "#2f855a"),
    ]
    paths = []

    for step in (1, 2, 3):
        fig, ax = new_axes(wide if step == 3 else normal, is3d=True)

        if step == 1:
            # 完整三棱柱
            ax.add_collection3d(Poly3DCollection(
                [A, B], facecolor=C["fill"], edgecolor=C["main"],
                lw=1.4, alpha=0.28))
            for i in range(3):
                ax.plot(*zip(A[i], B[i]), color=C["main"], lw=1.4)
            ax.set_xlim(-0.4, 2.0)
            ax.set_box_aspect((2.4, 2.3, 2.9))

        elif step == 2:
            # 整体轮廓 + 高亮切出的第一个三棱锥 T1
            ax.add_collection3d(Poly3DCollection(
                [A, B], facecolor=C["fill"], edgecolor=C["main"],
                lw=1.0, alpha=0.14))
            for i in range(3):
                ax.plot(*zip(A[i], B[i]), color=C["aux"], lw=1.0)
            ax.add_collection3d(Poly3DCollection(
                _tetra_faces(tetras[0][0]), facecolor=C["hi"],
                edgecolor=C["hi"], lw=1.6, alpha=0.55))
            ax.set_xlim(-0.4, 2.0)
            ax.set_box_aspect((2.4, 2.3, 2.9))

        else:
            # 三个锥沿 x 轴并排。这是课本讲"三棱柱分成三个等体积三棱锥"的
            # 标准呈现：并排且同角度，读者能逐块比出它们形状不同但体积相等。
            # 试过沿竖直方向分离，但三个形状在竖直堆叠下读不出"等分"含义。
            for i, (verts, col) in enumerate(tetras):
                shifted = verts + np.array([(i - 1) * gap, 0.0, 0.0])
                ax.add_collection3d(Poly3DCollection(
                    _tetra_faces(shifted), facecolor=col, edgecolor=col,
                    lw=1.5, alpha=0.45))
            ax.set_xlim(-0.4 - gap, 2.0 + gap)
            ax.set_box_aspect((2.4 + 2 * gap, 2.3, 2.9))

        ax.set_ylim(-0.4, 1.9)
        ax.set_zlim(-0.4, 2.5)
        # azim 与 recipe_cylinder 保持一致：同一节课里多张立体图视角统一，
        # 学生才能把不同图上的同一条棱对应起来。
        ax.view_init(elev=16, azim=-60)

        paths.append(save(fig, out.replace(".png", f"_{step}.png"),
                          spec.get("aspect")))

    return paths


RECIPES = {
    "function": recipe_function,
    "secant": recipe_secant,
    "secant_gif": recipe_secant_gif,
    "cylinder": recipe_cylinder,
    "cone": recipe_cone,
    "stacked_books": recipe_stacked_books,
    "prism_split": recipe_prism_split,
}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def check_fonts():
    print("中文字体检查")
    resolved = setup(verbose=False)
    if resolved is None:
        print("  ✗ 没有可用的中文字体 —— 图形中的中文会变成方框")
        return 1
    print(f"  ✓ 解析到: {resolved}")
    print(f"  候选列表: {FONT_CANDIDATES}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="生成课件配图")
    ap.add_argument("spec", nargs="?", help="figures.json 清单")
    ap.add_argument("-o", "--out", default=None,
                    help="输出目录（不给则用清单里的 output_dir，默认 figures）")
    ap.add_argument("--check-fonts", action="store_true",
                    help="只检查中文字体是否可用")
    ap.add_argument("--only", help="只生成指定 name 的图")
    args = ap.parse_args()

    if args.check_fonts:
        return check_fonts()

    if not args.spec:
        ap.error("需要提供 figures.json，或用 --check-fonts")

    with open(args.spec, encoding="utf-8") as fh:
        spec = json.load(fh)

    setup(prefer=spec.get("font"))
    outdir = args.out or spec.get("output_dir", "figures")
    os.makedirs(outdir, exist_ok=True)

    items = spec.get("figures", [])
    if args.only:
        items = [i for i in items if i.get("name") == args.only]

    failed = []
    for item in items:
        name = item.get("name", "?")
        recipe = item.get("recipe")
        if recipe not in RECIPES:
            failed.append((name, f"未知 recipe: {recipe!r}；"
                                 f"可选 {sorted(RECIPES)}"))
            continue

        ext = ".gif" if recipe == "secant_gif" else ".png"
        out = os.path.join(outdir, f"{name}{ext}")
        print(f"[{name}] recipe={recipe}")
        try:
            RECIPES[recipe](item, out)
        except Exception as e:  # noqa: BLE001 — 单个图失败不该中断整批
            failed.append((name, f"{type(e).__name__}: {e}"))
            print(f"  ✗ {type(e).__name__}: {e}")

    if failed:
        print("\n失败项:")
        for name, err in failed:
            print(f"  · {name}: {err}")
        return 1

    print(f"\n完成，共 {len(items)} 张 → {outdir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
