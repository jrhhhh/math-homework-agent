# 中学数学课件配图 recipe

`make_figures.py` 的用法与常见图形的画法。所有 recipe 已在本机实测可跑
（matplotlib 3.10.9 + numpy + Pillow）。

配图的目的是**让抽象概念有图形依托**。中学数学的黑板推导已经足够，课件配图的价值
在于把「变化」「逼近」「等积」这类在静态黑板上说不清的东西可视化出来。

**目录**

| 节 | 内容 |
|---|---|
| [零](#零先做字体配置最容易翻车的一步) | 字体配置（不配就是满屏方框，且不报错） |
| [一](#一输出规格) | 输出规格：长宽比决定渲染器怎么摆图、`pad_to_aspect` |
| [配色](#配色) | 一组低饱和配色与用法 |
| [二](#二函数图像) | 函数图像 recipe |
| [三](#三割线逼近切线本技能最有价值的配图) | 割线逼近切线（静态 + GIF） |
| [四](#四立体几何柱体--锥体与等高截面) | 立体几何：柱锥、等高截面、叠书 |
| [五](#五三棱柱分割成三个三棱锥) | 三棱柱分割成三个三棱锥 |
| [六](#六figuresjson-输入格式) | `figures.json` 格式与 recipe 参数表 |
| [七](#七检查清单) | 出图后的检查清单 |

画之前先看第零节和第一节 —— 这两节踩过坑，且失败时都不报错。

---

## 零、先做字体配置（最容易翻车的一步）

matplotlib 默认字体不含中文，中文标签会渲染成一串方框（豆腐块），而且**不报错** ——
图能正常生成，只是字全是空框，容易到最后一刻才发现。

所以每个画图入口都先执行：

```python
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun']
matplotlib.rcParams['axes.unicode_minus'] = False   # 负号显示为方框的经典坑
```

`axes.unicode_minus = False` 单独提醒：中文环境下负号会走 Unicode 的 U+2212，
而雅黑里没有这个字形，于是 `-1` 会显示成一个框。这一行是必须的。

3D 图的中文标签同样受这套配置影响，不需要额外设置。

**图内文字刻意用无衬线（微软雅黑），而页面正文用衬线（华文中宋）—— 这是有意的
不一致。** 理由是阅读距离不同：正文在投影上是成句给人读的，衬线的笔锋帮助眼睛串行；
图内标签只有几个字、字号又小（等效 12–14pt），衬线的细笔画在投影距离和视频压缩下
最先糊掉。所以图内一律无衬线、笔画等粗。

需要时可用 `figures.json` 里的 `"font"` 键按份覆盖（如整套图想统一成华文中宋），
但**改之前先确认该字体确实装了** —— 没装就是满屏方框，而且不报错。

---

## 一、输出规格

正文区约 11.7 × 4.5 英寸。**图能画多大，由它的长宽比决定，不由 `figsize` 决定** ——
`bbox_inches='tight'` 加裁白之后，画布只剩内容本身，`figsize` 只影响分辨率不影响形状。
所以设 `figsize` 时要想的是「内容的形状」，不是「画布的形状」：

| 长宽比 | 渲染器怎么摆 | 适用 |
|---|---|---|
| ≥ 1.5（横幅） | 上图下文，图占满版心宽（11.8 in） | `[纯图]`、流程页的主角图 |
| 1.0 – 1.5（近方） | 左文右图并排，图栏约占版心 54% | `[标题]` 版式的常规配图 |
| < 1.0（竖幅） | 同上，并排；图栏内会剩些纵向空白 | 叠书、单个柱锥这类本身竖长的对象 |

**渲染器自己按长宽比分派版式**，你不用在 `课件.md` 里指定「这页是并排还是上图下文」。
两种摆法图都在自己的栏内水平居中，所以竖幅图不会一边顶着版心、一边空出半页。

竖幅图不是错误，但**一页里只放一张竖幅图会显得空**。竖长对象（如圆柱）配竖排要点、
或把两张竖图并排，版面才撑得起来。立体图尤其容易踩这个坑：mplot3d 的
`set_box_aspect` 只管投影比例，画布恒定是正方形，实际形状要靠裁白之后才知道 ——
所以**出图后一定量一下**，别照着 `figsize` 猜。

统一 `dpi=200`（投影足够清晰，文件又不会过大）。导出用
`fig.savefig(path, bbox_inches='tight', facecolor='white')` —— 白底很重要，
透明底在深色 PowerPoint 主题下会看不清坐标轴。

### 可选后处理：`pad_to_aspect(path, ar)`

`bbox_inches='tight'` 裁完白，画布形状完全由内容决定，`figsize` 说了不算。这意味着
同一组图的长宽比会各不相同：`prism_split` 的前两步是近方的立体图，第三步为了
「三个锥横向排开」需要宽画幅，裁完就是 1.8 的横幅。

`figures.json` 里给图加一个 `"aspect": 1.0`，脚本会在裁白之后把画布补白到统一比例
（内容居中，补的是白色，与页面底色一致所以看不出来）：

```json
{"name": "prism", "recipe": "prism_split", "aspect": 1.0}
```

**补白已经改变不了流程页的排版。** 渲染器量的是**着墨区**（画布上真正有图形的那块），
摆图之前用 `a:srcRect` 把白边裁掉 —— 所以补白动不了最终图形的大小，只是让文件画布统一。

补白真正还有用的地方是 `[标题]` 版式：渲染器按**文件**长宽比决定这页排成「左文右图
并排」还是「上图下文」（见第一节的表），补白会影响这个分派。想控制单张图怎么摆时才需要它。

流程页真正的要求是**各步的图形形状接近**，而不是文件画布接近。补白恰恰会把这件事藏起来：
棱柱分割那组三个文件都是 370×370 的正方形，着墨区却是 0.60 / 0.60 / 1.89 ——
看文件以为一致，看图形差 1.9 倍，而按画布排出来的结果就是第三个锥体只有前两个一半高。

所以渲染器量着墨区，形状差到排不开时会告警
（`流程页统一比例后图形仅 X in 高`）。**告警时的正确反应是重出图让各步形状接近，
或者拆页，不是补白** —— 补白正是当初把这个问题盖住的那个动作。

## 配色

与内置版式一致的一组低饱和色，避免红绿同时高饱和（色觉障碍学生分辨困难）：

```python
C = {
    'main':  '#2b6cb0',   # 主曲线 / 主对象
    'aux':   '#718096',   # 辅助线、参考线
    'hi':    '#dd6b20',   # 强调：切线、目标对象
    'trail': '#a0aec0',   # 渐隐：逼近过程中的中间态
    'text':  '#1a202c',   # 文字与标注
    'fill':  '#bee3f8',   # 填充
}
```

原则：**同一张图里主对象用 `main`，要强调的那个用 `hi`，过程中的中间态用 `trail`
且越接近极限越深**（透明度递增），这样「逼近」这件事在静态图上也能读出来。

---

## 二、函数图像

```python
import numpy as np, matplotlib.pyplot as plt

def plot_function(f, xlim, path, fml=r'$f(x)=x^2$', x0=None, size=(6.0, 4.0)):
    fig, ax = plt.subplots(figsize=size, dpi=200)
    x = np.linspace(*xlim, 400)
    ax.plot(x, f(x), lw=2.5, color=C['main'], label=fml)
    ax.axhline(0, color=C['aux'], lw=0.8)
    ax.axvline(0, color=C['aux'], lw=0.8)
    ax.grid(alpha=0.25, ls=':')
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(fontsize=12, frameon=False)
    fig.savefig(path, bbox_inches='tight', facecolor='white')
```

要点：去掉上右边框、网格用浅虚线 —— 中学课件里图是配角，不该比正文抢眼。

## 三、割线逼近切线（本技能最有价值的配图）

这是「导数」一课的核心可视化。**静态版**在一张图上叠加多条割线，
用透明度区分先后，让「逼近」的过程凝固在纸面上：

```python
def secant_to_tangent(f, df, x0, hs, path, size=(7.5, 4.2)):
    fig, ax = plt.subplots(figsize=size, dpi=200)
    x = np.linspace(x0 - 1.5, x0 + 2.5, 400)
    ax.plot(x, f(x), lw=2.5, color=C['main'], label=r'$f(x)=x^2$')

    # 割线：h 越小颜色越深，读者能看出「在往哪儿走」
    for i, h in enumerate(hs):
        k = (f(x0 + h) - f(x0)) / h
        xs = np.array([x0 - 0.8, x0 + h + 0.8])
        ax.plot(xs, f(x0) + k * (xs - x0), lw=1.8,
                color=C['trail'], alpha=0.35 + 0.5 * i / max(len(hs) - 1, 1))
        ax.plot([x0, x0 + h], [f(x0), f(x0 + h)], 'o',
                color=C['trail'], ms=4, alpha=0.6)

    # 切线最后画，压在割线之上
    k = df(x0)
    xs = np.array([x0 - 1.2, x0 + 1.4])
    ax.plot(xs, f(x0) + k * (xs - x0), lw=2.2, color=C['hi'],
            ls='--', label=f'切线 k={k:g}')
    ax.plot([x0], [f(x0)], 'o', color=C['text'], ms=6, zorder=5)
    ax.annotate(r'$P$', (x0, f(x0)), textcoords='offset points',
                xytext=(-14, 6), fontsize=13)
    ax.grid(alpha=0.25, ls=':')
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(fontsize=12, frameon=False)
    fig.savefig(path, bbox_inches='tight', facecolor='white')
```

`hs` 建议 `[1.0, 0.5, 0.2]` —— 三条够表达趋势，再多就糊成一团。

### GIF 版

只有当「连续逼近」的渐近感本身是教学重点时才用 GIF。做法：

```python
from matplotlib.animation import FuncAnimation, PillowWriter

def secant_gif(f, df, x0, path, n=40, size=(7.5, 4.2)):
    fig, ax = plt.subplots(figsize=size, dpi=110)   # GIF 降 dpi 控制体积
    x = np.linspace(x0 - 1.5, x0 + 2.5, 400)

    def draw(i):
        ax.clear()
        h = 1.0 * (0.02 / 1.0) ** (i / (n - 1))      # 1.0 → 0.02，几何衰减
        ax.plot(x, f(x), lw=2.5, color=C['main'])
        k = (f(x0 + h) - f(x0)) / h
        xs = np.array([x0 - 0.8, x0 + h + 0.8])
        ax.plot(xs, f(x0) + k * (xs - x0), lw=1.8, color=C['trail'])
        ax.plot([x0, x0 + h], [f(x0), f(x0 + h)], 'o', color=C['trail'], ms=5)
        kt = df(x0)
        xt = np.array([x0 - 1.2, x0 + 1.4])
        ax.plot(xt, f(x0) + kt * (xt - x0), lw=2.2, color=C['hi'], ls='--')
        ax.plot([x0], [f(x0)], 'o', color=C['text'], ms=6)
        ax.set_title(f'Δt = {h:.3f}    k = {k:.3f}', fontsize=13, color=C['text'])
        ax.grid(alpha=0.25, ls=':')
        ax.spines[['top', 'right']].set_visible(False)

    FuncAnimation(fig, draw, frames=n).save(path, writer=PillowWriter(fps=15))
```

两个坑：

- **按几何衰减而非线性递减**取 `h`。线性递减时前半段几乎看不出变化，
  后半段又跳得太快，观感是「卡住然后突然结束」。
- GIF 的 `dpi` 降到 110，`fps` 15。dpi 200 的 40 帧 GIF 会有好几 MB，
  插进 pptx 后放映明显卡顿。

## 四、立体几何：柱体 / 锥体与等高截面

「祖暅原理」这类内容需要 3D。用 `mplot3d`：

```python
from mpl_toolkits.mplot3d import Axes3D   # 导入以注册 3d projection
import numpy as np, matplotlib.pyplot as plt

def cylinder_with_section(r=1.0, h=2.0, z=1.2, path='cyl.png', size=(5.2, 4.0)):
    fig = plt.figure(figsize=size, dpi=200)
    ax = fig.add_subplot(111, projection='3d')

    # 侧面
    t = np.linspace(0, 2 * np.pi, 60)
    zz = np.linspace(0, h, 30)
    T, Z = np.meshgrid(t, zz)
    ax.plot_surface(r * np.cos(T), r * np.sin(T), Z,
                    color=C['fill'], alpha=0.35, linewidth=0)

    # 等高截面
    ax.plot(r * np.cos(t), r * np.sin(t), z, color=C['hi'], lw=2.2)

    # 顶底圆
    for zc, lw in ((0, 1.2), (h, 1.2)):
        ax.plot(r * np.cos(t), r * np.sin(t), zc, color=C['main'], lw=lw)

    ax.set_box_aspect((1, 1, h / (2 * r)))
    ax.set_axis_off()          # 课件里的立体图不需要坐标轴
    ax.view_init(elev=18, azim=-58)
    fig.savefig(path, bbox_inches='tight', facecolor='white')
```

要点：

- `set_axis_off()` —— 立体图的坐标轴在中学课件里是干扰项，直接关掉
- `set_box_aspect` 按真实比例设，否则圆柱会被压成扁饼
- `view_init(elev=18, azim=-58)` 是立体感与可读性的折中角度；`elev` 太高会俯视
  看不出高，太低会侧视看不出圆
- `alpha=0.35` 的半透明侧面能让内部截面可见 —— 截面是这节课的主角

### 圆锥：`cone`

例题「已知底面半径 r、高 h，求体积 V」的配图。**题面里的 r 和 h 得在图上看得见**，
否则学生要自己在脑子里对号入座：

```python
def cone(r=1.0, h=2.0, path='cone.png', size=(5.2, 4.0)):
    fig = plt.figure(figsize=size, dpi=200)
    ax = fig.add_subplot(111, projection='3d')

    # 用 (T, S) 参数化：S=0 是顶点，S=1 是底面。半径随 S 线性张开 ——
    # 这正是圆锥区别于圆柱的地方，圆柱那种等半径网格画不出锥面。
    t = np.linspace(0, 2 * np.pi, 60)
    T, S = np.meshgrid(t, np.linspace(0, 1, 30))
    ax.plot_surface(r * S * np.cos(T), r * S * np.sin(T), h * (1 - S),
                    color=C['fill'], alpha=0.35, linewidth=0)

    ax.plot(r * np.cos(t), r * np.sin(t), 0, color=C['main'], lw=1.2)   # 底面圆
    ax.plot([0, 0], [0, 0], [0, h], color=C['hi'], lw=1.6, ls='--')     # 高（辅助线）
    ax.plot([0, r], [0, 0], [0, 0], color=C['hi'], lw=1.6)              # 半径
    ax.text(0, 0, h + 0.06 * h, 'h', color=C['hi'], fontsize=13,
            ha='center', va='bottom')
    ax.text(r * 0.5, 0, 0, 'r', color=C['hi'], fontsize=13, va='top')

    ax.set_box_aspect((1, 1, h / (2 * r)))
    ax.set_axis_off()
    ax.view_init(elev=18, azim=-58)
    fig.savefig(path, bbox_inches='tight', facecolor='white')
```

参数与默认值刻意与 `cylinder` **同名同值**（`r`/`h`/`size`），视角也一致
（`elev=18, azim=-58`）：这一课的推理是「锥是等底等高柱的 1/3」，两张图分别看时还好，
一旦并排或前后翻页，比例或视角不一致就把那个关系看没了。

高画成**虚线**：它是辅助线，不是几何体的边，与实线的底面圆区分开。

### 叠书 → 斜棱柱（祖暅原理的情境引入）

这个不需要 3D，用 2D 矩形叠出「斜推」更清楚：

```python
def stacked_books(path, n=7, shear=0.35, size=(6.0, 4.0)):
    fig, ax = plt.subplots(figsize=size, dpi=200)
    for i in range(n):
        x0 = i * shear
        ax.add_patch(plt.Rectangle((x0, i), 2.4, 0.9, facecolor=C['fill'],
                                   edgecolor=C['main'], lw=1.6))
    ax.annotate('', xy=(n * shear + 2.4, 0.45), xytext=(2.4, 0.45),
                arrowprops=dict(arrowstyle='->', color=C['hi'], lw=2))
    ax.text(n * shear + 1.2, 0.05, '斜推', color=C['hi'], fontsize=13, ha='center')
    ax.set_xlim(-0.4, n * shear + 3.2)
    ax.set_ylim(-0.6, n + 0.6)
    ax.set_aspect('equal')
    ax.axis('off')
    fig.savefig(path, bbox_inches='tight', facecolor='white')
```

「每本书没变 → 体积没变」这个推理，画出来比讲出来快得多，这正是情境引入的意义。

## 五、三棱柱分割成三个三棱锥

推导 `V = 1/3 Sh` 的关键动画，拆成三张静态图排在**同一页**（流程页）比做动画更清楚 ——
学生要能同时看到「原来的棱柱长什么样」和「切出来的锥长什么样」，
拆成三张幻灯片翻过去就丢掉了这个对照：

```python
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

def _tetra_faces(v):
    """四顶点 → 四个三角面，供 Poly3DCollection 使用"""
    a, b, c, d = v
    return [[a, b, c], [a, b, d], [a, c, d], [b, c, d]]

def prism_split(step, path, size=(5.2, 4.0), wide_size=(8.2, 3.6), gap=2.2):
    """step: 1=完整三棱柱, 2=切出第一个锥, 3=三锥横向排开"""
    fig = plt.figure(figsize=(wide_size if step >= 3 else size), dpi=200)
    ax = fig.add_subplot(111, projection='3d')

    A = np.array([[0.,0.,0.],[1.6,0.,0.],[0.8,1.4,0.]])
    B = A + np.array([0., 0., 2.0])

    if step < 3:
        # 前两步：棱柱轮廓 + 逐渐分离出的锥
        for verts, al in ((A, 0.30), (B, 0.18)):
            ax.add_collection3d(Poly3DCollection(
                [verts], facecolor=C['fill'], edgecolor=C['main'], lw=1.4, alpha=al))
        for i in range(3):
            ax.plot(*zip(A[i], B[i]), color=C['main'], lw=1.4)
        if step == 2:
            ax.add_collection3d(Poly3DCollection(
                _tetra_faces(np.array([A[0], A[1], A[2], B[2]])),
                facecolor=C['hi'], edgecolor=C['hi'], lw=1.5, alpha=0.5))
        ax.set_box_aspect((1.6, 1.4, 2.0))
    else:
        # 第三步：三个锥沿 x 轴并排 —— 沿质心炸开或沿 z 轴分开都会糊成一团，
        # 横向排开是唯一一眼能读出“三等分”的摆法，代价是需要更宽的画幅
        tetras = [
            (np.array([A[0], A[1], A[2], B[2]]), C['main']),
            (np.array([A[0], A[1], B[2], B[1]]), C['hi']),
            (np.array([A[0], B[1], B[2], B[0]]), '#2f855a'),
        ]
        for i, (v, col) in enumerate(tetras):
            shifted = v + np.array([(i - 1) * gap, 0., 0.])
            ax.add_collection3d(Poly3DCollection(
                _tetra_faces(shifted), facecolor=col, edgecolor=col, lw=1.5, alpha=0.45))
        ax.set_xlim(-0.4 - gap, 2.0 + gap)
        ax.set_box_aspect((2.4 + 2 * gap, 2.3, 2.9))

    ax.set_axis_off(); ax.view_init(elev=16, azim=-60)
    fig.savefig(path, bbox_inches='tight', facecolor='white')
```

三个坑，都踩过：

- **`add_collection3d(plt.Polygon(...), zdir=...)` 只接受二维多边形**，传三维顶点会直接抛
  `ValueError: 'vertices' must be 2D`。任意朝向的面必须用 `Poly3DCollection`。
- **三锥分离别沿质心炸开、也别沿 z 轴堆**：前者三块互相穿插看不出个数，后者会被
  `zlim` 裁掉。沿 x 轴横向排开才对。
- `view_init` 的 `azim` 要和上一节保持一致 —— 同一节课里的多张立体图视角统一，
  学生才能把不同图上的同一个棱对应起来。

这三张的**着墨形状**差得比较远：前两步约 0.6（竖高），第三步约 1.9（横宽）。流程页按
着墨区等比排，所以第三步会被压到跟前两步同高、再横着铺满余下的宽度 —— 排得下，但整排
会偏小（约 2.9in 高）。

想让它更饱满，正解是**改这一组图的形状**（把第三步的三个锥排紧凑些，让它的着墨区靠近
前两步），而**不是配 `"aspect": 1.0` 补白** —— 渲染器量着墨区、并把白边裁掉再排，补白
出不了任何效果（见第一节）。

---

## 六、`figures.json` 输入格式

`make_figures.py` 读一份声明式清单，避免每次重新写脚本：

```json
{
  "output_dir": "figures",
  "figures": [
    {"name": "books", "recipe": "stacked_books", "n": 7, "shear": 0.35, "size": [6.0, 4.0]},
    {"name": "cyl",   "recipe": "cylinder", "r": 1.0, "h": 2.0, "z": 1.2, "size": [5.2, 4.0]},
    {"name": "prism", "recipe": "prism_split", "size": [5.2, 4.0], "wide_size": [8.2, 3.6],
     "aspect": 1.0},
    {"name": "secant_approach", "recipe": "secant",
     "f": "x**2", "df": "2*x", "x0": 1.0, "hs": [1.0, 0.5, 0.2], "size": [7.5, 4.2]},
    {"name": "approach_anim", "recipe": "secant_gif", "f": "x**2", "df": "2*x", "x0": 1.0}
  ]
}
```

跑：`python make_figures.py figures.json -o .`（`--only books` 可只重出某一张，
`--check-fonts` 先验证中文字体是否可用）。

**为什么是 JSON 不是 YAML**：这台机器上没装 `pyyaml`，而 JSON 是标准库自带的。
写成 YAML 会让技能多出一个「先 pip install」的前置步骤 —— 对一个要求开箱即用的
技能来说不划算。JSON 手写稍啰嗦（键要加引号），但换来零依赖。

已实现的 recipe 与参数：

| recipe | 参数 | 产出 |
|---|---|---|
| `function` | `f` `xlim` `fml` `x0` `size` | 1 张函数图像 |
| `secant` | `f` `df` `x0` `hs` `size` | 1 张静态割线逼近图 |
| `secant_gif` | `f` `df` `x0` `n` `size` | 1 个 GIF |
| `cylinder` | `r` `h` `z` `size` | 1 张圆柱+等高截面 |
| `cone` | `r` `h` `size` | 1 张圆锥，标注底面半径与高（例题配图） |
| `stacked_books` | `n` `shear` `size` | 1 张叠书斜推 |
| `prism_split` | `size` `wide_size` `gap` | **3 张** `名字_1/2/3.png` |

所有 recipe 都额外接受两个通用键：

| 键 | 作用 |
|---|---|
| `aspect` | 裁白后补白到该长宽比（宽/高），内容居中。影响 `[标题]` 版式怎么摆，不影响流程页 |
| `font` | 覆盖字体候选表。默认无衬线（见第零节），没特殊理由不要动 |

### 这条 recipe 表盖不到的图（重要）

上面六条是**程序化生成的几何示意图**，覆盖的是「用坐标和参数描述得清楚的图形」。
真实中学课件里配图远不止这一类。数一下作者本人的参赛 PPT（13 页，12 张去重后的图）：
其中 **7 张长宽比 ≥ 3 的宽条** —— 288×62、197×62、303×73、311×73、305×83、1208×288，
以及一张 641×37（一个单行公式）—— 都是公式或推导过程的截图条。那 7 张本技能一张都
做不出来：

| 你要的图 | 能不能做 | 怎么办 |
|---|---|---|
| 函数图像、割线切线、柱锥、叠书、棱柱分割 | ✅ recipe 直接出 | 见上表 |
| 三角恒等变形、判别式推导这类**公式推导条** | ⛔ | 用 `课件.md` 的要点行写公式，或自己截图插入 |
| 教材原图、试卷截图、手写板书照片 | ⛔ | 自己截图放进 `figures/`，再 `!img:` 引用 |
| 真实照片（跳台、建筑、实物） | ⛔ | 同上（注意版权，课堂内部使用另说） |
| 上面没列的任意几何图形（正四面体、球缺、旋转体…） | ⛔ 需要新写 recipe | 见下 |

**手工插入的图完全合法**：`!img:` 只要求「文件在 `figures/` 下」，不要求「由本脚本生成」。
截一张教材图或公式图放进目录，渲染器一视同仁 —— 量长宽比、居中、并排都照做。

**需要新图形时不要硬凑近似的 recipe。** 写一个新 recipe 加到 `make_figures.py` 的
`RECIPES` 字典里，比用 `cylinder` 冒充球缺靠谱得多 —— 图会画错，而画错的图比没有图更坏，
因为它看起来是对的。写新 recipe 前先读同文件里 `recipe_cylinder`，它演示了本文件出图的
全部约定：`dpi=200`、`bbox_inches='tight'`、白底、无衬线中文、`axes.unicode_minus = False`。

配图数量上，**不要为了凑密度而把同一张图重复用在几页**。样本 PPT 的建构段确实配得比
本技能默认的更密（一页 2–3 张），但那是靠公式截图条堆出来的；用示意图硬凑到那个密度，
一页塞三张几何图反而比一张图更乱。

`f` / `df` 用字符串写表达式，脚本内用 `sympy.lambdify` 编译成 numpy 函数 ——
表达式写错时会立刻报出来，好过画出一张形状可疑但「看着像」的图。

---

## 七、检查清单

出图后**必须用眼睛看**，前两条是踩过的坑 —— 它们都不会报错，只能靠看：

- [ ] **图上中文不是方框**（字体配置生效；`--check-fonts` 只能证明字体存在，不能
      证明字形齐全，最终还是要看图）
- [ ] **负号正常显示**（`axes.unicode_minus = False` 生效）
- [ ] 白底（不是透明底）
- [ ] **量一下实际长宽比**，别照着 `figsize` 猜（见第一节）—— 它直接决定渲染器把这页
      排成并排还是上图下文，猜错就白画了
- [ ] 同一份课件里的图配色一致、立体图视角一致
- [ ] **流程页的一组图，着墨区形状接近**（肉眼比一下"图形本身"的高度，不要比文件画布 ——
      补白会让文件画布一致而图形差一倍，这是踩过的坑，见第一节 `pad_to_aspect`）
- [ ] GIF 文件 < 2MB，`fps` 不超过 20
- [ ] 图中字号在投影距离下可读（图内文字 ≥ 12pt 等效）
