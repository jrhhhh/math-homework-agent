#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测 verify_pptx 的「流程页着墨高度一致」这条检查 —— 两个方向都测。

    python evals/fixtures/test_ink_check.py

## 这条检查差点被误判成死代码

它的判据是 `vis_ink_h()`：拿「显示区」与「源图着墨带」的**交集**算看得见的
图形高度，而不是直接量图框。夹具用三张 370×370 画布完全相同、着墨高
100/100/190px（比值 1.9×）的源图。

单看渲染器产出，它恒为 0 ERROR —— 很容易就此得出结论「这检查是哑的」。
**那个结论是错的。** 真渲染器会给每张图按各自着墨带写 a:srcRect 并归一化
可见高度，三张框高都是 1.925in，看得见的图形**本来就该一样高**，不报才对。

要证它活着，必须**造出反例**：框高相同但**不裁切**（模拟一个按画布、而不是
按着墨带归一化的渲染器）。这时三张的可见着墨变成 0.526/0.526/0.994，差 1.89×，
检查报出来。

所以这条脚本两个方向都钉：渲染器产出必须干净，坏渲染器必须被抓。
「没报」不等于「没问题」—— 得有个必须报的对照，才配说这句话。
"""

import os
import shutil
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
FIG = os.path.join(HERE, "figures")
PY = sys.executable
TMP = os.path.join(os.environ.get("TEMP", "/tmp"), "lm-ink-check")

EXPECT = "流程页同组图着墨高度不一致"


def build(md, out):
    p = subprocess.run([PY, os.path.join(ROOT, "scripts", "build_pptx.py"),
                        md, "-o", out], capture_output=True, cwd=ROOT)
    return p.returncode == 0, p.stdout.decode("utf-8", "replace")


def main():
    os.makedirs(TMP, exist_ok=True)
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from pptx import Presentation
    from verify_pptx import check

    md = os.path.join(HERE, "flow-ink-mismatch.md")
    good = os.path.join(TMP, "good.pptx")
    ok, log = build(md, good)
    if not ok:
        print("✗ 渲染失败：\n%s" % log[-500:])
        return 1

    # ① 渲染器产出：可见着墨**本来就该**一致，必须干净
    prs, errs, warns, info = check(good, FIG)
    hit = [m for _, m in errs if EXPECT in m]
    if hit:
        print("✗ 渲染器产出被判着墨不一致 —— 归一化坏了：")
        print("   ", hit[0])
        return 1
    if errs or warns:
        print("✗ 渲染器产出不干净：ERROR %d / WARN %d" % (len(errs), len(warns)))
        for _, m in list(errs)[:3]:
            print("   ", m[:100])
        return 1
    print("✓ ① 渲染器产出干净（可见着墨已归一化，三张等高才对）")

    # ② 坏渲染器：框高相同但不裁切 → 必须报
    bad = os.path.join(TMP, "nocrop.pptx")
    shutil.copyfile(good, bad)
    p = Presentation(bad)
    for s in p.slides[1].shapes:
        if s.shape_type != 13:
            continue
        s.crop_left = s.crop_right = s.crop_top = s.crop_bottom = 0.0
    p.save(bad)

    prs, errs, warns, info = check(bad, FIG)
    hit = [m for _, m in errs if EXPECT in m]
    if not hit:
        print("✗ ② 坏渲染器（框高相同、不裁切）没被抓住 —— 这条检查是哑的")
        return 1
    print("✓ ② 坏渲染器被抓：%s" % hit[0][:78])

    # ③ 没装 Pillow / 源图不在 --figures 里时，必须返回 None 而不是冒充通过
    prs, errs2, warns2, info2 = check(bad, os.path.join(TMP, "空目录"))
    leaked = [m for _, m in errs2 if EXPECT in m]
    if leaked:
        print("✗ ③ 拿不到源图却仍报了着墨不一致 —— 那是编的")
        return 1
    print("✓ ③ 拿不到源图时不报（判据要求量得到才判，量不到不冒充通过）")

    print()
    print("着墨检查：两个方向 + 量不到的情形，都符合预期")
    return 0


if __name__ == "__main__":
    sys.exit(main())
