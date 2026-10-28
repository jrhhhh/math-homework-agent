#!/usr/bin/env python3
"""Regenerate native theme decks and optional previews from maintained sources."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import build_pptx

ROOT = Path(__file__).resolve().parents[1]


def preview(deck, fontconfig=None):
    from PIL import Image, ImageDraw
    if not shutil.which('soffice') or not shutil.which('pdftoppm'):
        raise RuntimeError('预览需要 soffice 和 pdftoppm。')
    env = os.environ.copy()
    if fontconfig:
        env['FONTCONFIG_FILE'] = str(Path(fontconfig).resolve())
    with tempfile.TemporaryDirectory(prefix='math-theme-preview-') as name:
        folder = Path(name)
        subprocess.run(['soffice', '-env:UserInstallation='+(folder/'profile').as_uri(),
                        '--headless', '--convert-to', 'pdf', '--outdir', str(folder), str(deck)],
                       check=True, capture_output=True, env=env, timeout=120)
        subprocess.run(['pdftoppm', '-png', '-scale-to', '1000', str(folder/(deck.stem+'.pdf')),
                        str(folder/'page')], check=True, capture_output=True, timeout=120)
        files = sorted(folder.glob('page-*.png'))
        if len(files) != 8:
            raise RuntimeError('主题样册预期8页。')
        canvas = Image.new('RGB', (960, 1120), '#E8E5E1')
        draw = ImageDraw.Draw(canvas)
        for j, i in enumerate(range(8)):
            with Image.open(files[i]) as im:
                im = im.convert('RGB'); im.thumbnail((470, 264))
                x, y = (j%2)*480, (j//2)*280
                canvas.paste(im, (x, y))
                draw.text((x+8,y+266), str(i+1), fill='#444444')
        canvas.save(deck.with_suffix('.preview.png'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--render', action='store_true', help='输出两套主题的真实渲染预览')
    parser.add_argument('--fontconfig', help='用于 LibreOffice 的字体配置文件')
    args = parser.parse_args()
    for theme in ['scholar-red', 'ink-teal']:
        out = ROOT/'assets/themes'/f'{theme}.pptx'
        result = build_pptx.build(ROOT/'assets/themes/showcase.md', out, theme=theme)
        print(theme, result[1], '页')
        if args.render:
            preview(out, args.fontconfig)
    for source in sorted((ROOT/'assets/templates').glob('*.md')):
        build_pptx.build(source, source.with_suffix('.pptx'))
    source = ROOT/'assets/examples/trigonometric/lesson.md'
    build_pptx.build(source, source.with_suffix('.pptx'))


if __name__ == '__main__':
    main()
