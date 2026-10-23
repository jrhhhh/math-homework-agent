#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成流程页夹具用的 PNG。

    python evals/fixtures/make_fig_fixture.py 输出目录

为什么运行时生成、而不是把 PNG 提交进仓库：
  `flow-ink-mismatch` 这条夹具的**全部意义**就在于「三个文件画布完全相同
  （370×370），只有着墨高度不同」—— 三张图长得一模一样，差异只在内容高度上。
  文件一旦提交，这件事就只能靠注释说；由脚本生成则是自证的，而且仓库里不留二进制。
"""

import os
import sys

from PIL import Image, ImageDraw

W = H = 370          # 三张图画布完全相同 —— 这正是这条夹具要证明的
INK_TOP = 100
INK_SHORT = 200      # 着墨高 100
INK_TALL = 290       # 着墨高 190，比值 1.9×


def _draw(path, top, bottom, width):
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    x0 = (W - width) // 2
    d.rectangle([x0, top, x0 + width, bottom], fill="black")
    im.save(path)


def main(outdir):
    os.makedirs(outdir, exist_ok=True)

    # flow-ink-mismatch：同一组，前两张矮、第三张高 —— 画布却都是 370×370
    _draw(os.path.join(outdir, "ink1.png"), INK_TOP, INK_SHORT, 220)
    _draw(os.path.join(outdir, "ink2.png"), INK_TOP, INK_SHORT, 220)
    _draw(os.path.join(outdir, "ink3.png"), INK_TOP, INK_TALL, 220)

    # flow-caption-overflow：四张正常图，用来把注意力留给说明行溢出
    for i in range(1, 5):
        _draw(os.path.join(outdir, "fx%d.png" % i), 120, 250, 220)

    for n in sorted(os.listdir(outdir)):
        p = os.path.join(outdir, n)
        im = Image.open(p)
        print("  %-10s %dx%d" % (n, im.size[0], im.size[1]))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
