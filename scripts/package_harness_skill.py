#!/usr/bin/env python3
"""Create a portable teacher skill bundle using only Git-tracked project files."""
import argparse
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TEACHER = 'high-school-math-teacher-agent'
SKILLS = ('learning-task-designer', 'answer-key-builder', 'math-error-diagnosis',
          'solution-refiner', 'draft-coach', 'learning-evidence-bridge',
          'remedial-lesson-planner', 'lesson-materials-builder')
PREFIX = TEACHER + '/'


def package(output):
    tracked = subprocess.check_output(['git', 'ls-files', '-z', '--', *SKILLS,
                                       'docs/teaching-loop.md', 'AGENTS.md'], cwd=ROOT).decode().split('\0')
    entry = (ROOT / TEACHER / 'SKILL.md').read_text(encoding='utf-8')
    entry = entry.replace('../docs/teaching-loop.md', 'docs/teaching-loop.md')
    banner = ('\n\n> 便携包使用说明：本文件所在目录是技能包根目录。下游技能位于本目录下的同名文件夹；'
              '读取对应的 `SKILL.md`，相对路径、脚本和模板均相对于那个子技能目录。'
              '工作台及数据库不包含在此便携包中，任务发布和版本记录需依赖原项目工作台，'
              '在当前宿主无法运行时只能交付草稿，不得声称已发布或持久化。\n')
    end = entry.find('\n---', 4)
    if not entry.startswith('---\n') or end < 0:
        raise ValueError('Invalid teacher skill frontmatter')
    entry = entry[:end+4] + banner + entry[end+4:]
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(PREFIX + 'SKILL.md', entry)
        for name in sorted(filter(None, tracked)):
            path = ROOT / name
            if not path.is_file():
                raise FileNotFoundError(path)
            archive.write(path, PREFIX + name)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', help='output .zip path')
    args = parser.parse_args()
    print(package(args.output))


if __name__ == '__main__':
    main()
