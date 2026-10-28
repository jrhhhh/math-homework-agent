"""Render this run's PPTX statically with explicit macOS Chinese font configuration."""
import json,os,shutil,subprocess
from pathlib import Path
from xml.sax.saxutils import escape
root=Path(__file__).resolve().parents[1]
decks=list(root.glob('lessons/*/课件.pptx'))
if len(decks)!=1:raise SystemExit('Expected exactly one generated PPTX')
for cmd in ('soffice','pdftoppm'):
 if not shutil.which(cmd):raise SystemExit('Missing required renderer: '+cmd)
fonts=[Path('/System/Library/Fonts'),Path('/System/Library/Fonts/Supplemental'),Path('/Library/Fonts')]
fonts=[p for p in fonts if p.is_dir()]
if not fonts:raise SystemExit('No expected macOS system font folders; supply Chinese fonts before rendering')
cache=root/'font-cache';cache.mkdir(exist_ok=True)
config=Path(__file__).with_name('fontconfig.xml')
config.write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig>'+''.join('<dir>'+escape(str(p))+'</dir>' for p in fonts)+'<cachedir>'+escape(str(cache))+'</cachedir><alias><family>sans-serif</family><prefer><family>Hiragino Sans GB</family></prefer></alias><alias><family>serif</family><prefer><family>Songti SC</family></prefer></alias></fontconfig>',encoding='utf-8')
preview=root/'课件静态预览-可读';preview.mkdir(exist_ok=True)
env=os.environ.copy();env['FONTCONFIG_FILE']=str(config.resolve())
profile=(root/'lo-profile-readable').as_uri()
convert=subprocess.run(['soffice','-env:UserInstallation='+profile,'--headless','--convert-to','pdf','--outdir',str(preview),str(decks[0])],capture_output=True,text=True,timeout=120,env=env)
pdf=preview/'课件.pdf'
if convert.returncode or not pdf.exists():raise RuntimeError('Static conversion failed: '+convert.stderr)
raster=subprocess.run(['pdftoppm','-png','-r','90',str(pdf),str(preview/'幻灯片')],capture_output=True,text=True,timeout=120)
if raster.returncode:raise RuntimeError('PDF rendering failed: '+raster.stderr)
images=sorted(preview.glob('幻灯片-*.png'))
result={'renderer':'LibreOffice static PDF + Poppler','font_config':'absolute file; system macOS Chinese fonts','exit_codes':[convert.returncode,raster.returncode],
        'pages':len(images),'images':[str(p.relative_to(root)) for p in images],
        'scope':'仅用于静态预览；不代表 PowerPoint 动画播放效果。','stderr':convert.stderr[-1500:]}
Path(__file__).with_name('readable-preview.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
