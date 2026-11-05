#!/usr/bin/env python3
"""Compile a trusted reference-answer source twice and report layout issues.

This checks compilation, not mathematical correctness or grading validity.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    report = {'source': str(source), 'pdf': None, 'success': False,
              'scope': '编译、缺字、引用与溢出版心；不验证数学或评分',
              'passes': [], 'issues': []}
    engine = shutil.which('xelatex')
    if not source.is_file() or source.suffix != '.tex':
        report['issues'].append('源文件必须是存在的 .tex 文件')
    elif engine is None:
        report['issues'].append('未找到 XeLaTeX，请配置已有 TeX Live/MacTeX')
    else:
        command = [engine, '-no-shell-escape', '-interaction=nonstopmode',
                   '-halt-on-error', '-file-line-error',
                   '-output-directory=' + str(output), source.name]
        for index in range(1, 3):
            try:
                result = subprocess.run(command, cwd=source.parent, capture_output=True,
                                        text=True, encoding='utf-8', errors='replace', timeout=120)
            except (OSError, subprocess.TimeoutExpired) as exc:
                report['issues'].append(type(exc).__name__)
                break
            (output / f'xelatex-pass-{index}.txt').write_text(result.stdout + result.stderr)
            report['passes'].append({'pass': index, 'exit_code': result.returncode})
            if result.returncode:
                report['issues'].append('XeLaTeX 编译失败，检查实际编译日志')
                break
        logpath = output / (source.stem + '.log')
        log = logpath.read_text(errors='replace') if logpath.exists() else ''
        for pattern in (r'Missing character:[^\n]*', r'Overfull \\[hv]box[^\n]*',
                        r'LaTeX Warning: (?:Reference|Citation)[^\n]*',
                        r'LaTeX Warning: There were undefined references[^\n]*'):
            report['issues'].extend(re.findall(pattern, log))
        pdf = output / (source.stem + '.pdf')
        if len(report['passes']) == 2 and not report['issues'] and pdf.is_file() and pdf.stat().st_size:
            report.update(success=True, pdf=str(pdf))
        elif not report['issues']:
            report['issues'].append('未生成有效 PDF')
    (output / 'build-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['success'] else 1


if __name__ == '__main__':
    sys.exit(main())
