"""Typeset and compile an exam reference answer that already passed its gate.

The online reply is the reviewed deliverable. This module adds an opt-in
export pass: the model transcribes that exact reply into LaTeX, then the real
XeLaTeX build script compiles it in an isolated directory. Compilation and
layout are checked; the mathematics is not verified again.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading

from . import model

ROOT = Path(__file__).resolve().parents[1]
SOLVER = ROOT / 'answer-key-builder'
STYLE = SOLVER / 'assets' / 'reference-answer.sty'
BUILDER = SOLVER / 'scripts' / 'build_reference_pdf.py'
MAX_REPLY_CHARS = 120_000
MAX_SOURCE_CHARS = 200_000
MAX_ATTEMPTS = 3
UNSAFE_TEX = re.compile(
    r'\\(?:write18|openout|read|input|include|includeonly|immediate|directlua)\b'
    r'|\\(?:usepackage|RequirePackage)\s*\{[^}]*shellesc[^}]*\}')


def compile_source(source, output_dir):
    """Run the trusted two-pass XeLaTeX script and return its JSON report."""
    process = subprocess.run(
        [sys.executable, str(BUILDER), str(source), '--output-dir', str(output_dir)],
        cwd=str(Path(source).resolve().parent), capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=300)
    try:
        report = json.loads(process.stdout)
    except ValueError:
        return {'success': False, 'pdf': None, 'passes': [],
                'issues': ['编译脚本未返回有效报告。' + (process.stderr or '')[-800:]]}
    if not isinstance(report, dict):
        return {'success': False, 'pdf': None, 'passes': [], 'issues': ['编译报告格式无效。']}
    return report


def extract_tex(raw):
    """Accept a bare document even if the model wrapped it in a code fence."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError('模型没有返回 LaTeX 源码。')
    text = raw.strip()
    if text.startswith('{'):
        try:
            payload = json.loads(text)
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            for key in ('latex_source', 'latex', 'tex', 'source'):
                if isinstance(payload.get(key), str):
                    text = payload[key].strip()
                    break
    if text.startswith('```'):
        text = re.sub(r'^```[A-Za-z0-9_-]*[ \t]*\n?', '', text)
        text = re.sub(r'\n?```[ \t]*$', '', text).strip()
    start = text.find('\\documentclass')
    if start < 0:
        raise ValueError('模型输出不是完整的 LaTeX 文档。')
    return text[start:]


class ExamExporter:
    """Persist per-submission LaTeX sources and compiled PDFs."""

    def __init__(self, store, generator=None, compiler=None, output_root=None):
        self.store = store
        self.generator = generator or model.generate
        self.compiler = compiler or compile_source
        self.output_root = (Path(output_root) if output_root is not None
                            else Path(store.path).resolve().parent / 'answer-exports')
        self._default_compiler = compiler is None
        self._locks = {}
        self._locks_guard = threading.Lock()

    def can_compile(self):
        return (not self._default_compiler) or shutil.which('xelatex') is not None

    def ensure_exportable(self, rid):
        if not isinstance(rid, str) or not re.fullmatch(r'[a-f0-9]{32}', rid):
            raise ValueError('提交编号无效。')
        item = self.store.get(rid)
        if item is None:
            raise ValueError('提交不存在。')
        data = item.get('data') or {}
        if data.get('mode') != 'exam_answer':
            raise ValueError('只有“生成试卷参考答案”模式支持导出。')
        if not item.get('is_current'):
            raise ValueError('这是历史版本，不能导出；请选择当前版本。')
        result = item.get('result') or {}
        if item.get('state') != 'ready' or result.get('status') != 'ready':
            raise ValueError('只有已完成且通过结构校验的参考答案可以导出。')
        reply = (result.get('output') or {}).get('reply')
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError('参考答案正文为空，无法导出。')
        if len(reply) > MAX_REPLY_CHARS:
            raise ValueError('参考答案正文过长，无法导出。')
        return item, reply

    def _lock_for(self, rid):
        with self._locks_guard:
            return self._locks.setdefault(rid, threading.Lock())

    def _paths(self, rid):
        folder = self.output_root / rid
        return {'folder': folder, 'source': folder / 'main.tex',
                'style': folder / 'reference-answer.sty',
                'report': folder / 'build-report.json',
                'build': folder / 'build', 'pdf': folder / 'build' / 'main.pdf'}

    def _version_key(self, item, reply):
        digest = hashlib.sha256()
        digest.update(str(item.get('version', '')).encode('utf-8'))
        digest.update(b'\0')
        digest.update(reply.encode('utf-8'))
        digest.update(b'\0')
        digest.update(STYLE.read_bytes())
        digest.update(BUILDER.read_bytes())
        return digest.hexdigest()[:20]

    def _read_report(self, rid):
        paths = self._paths(rid)
        if not paths['report'].is_file():
            return None
        try:
            report = json.loads(paths['report'].read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        return report if isinstance(report, dict) else None

    def _files(self, rid, report):
        paths = self._paths(rid)
        if report and report.get('success') and paths['pdf'].is_file():
            return {'pdf': f'/api/submissions/{rid}/files/answer-pdf'}
        return {}

    def status(self, rid):
        if not isinstance(rid, str) or not re.fullmatch(r'[a-f0-9]{32}', rid):
            raise ValueError('提交编号无效。')
        item = self.store.get(rid)
        if item is None:
            raise ValueError('提交不存在。')
        if (item.get('data') or {}).get('mode') != 'exam_answer':
            raise ValueError('只有“生成试卷参考答案”模式支持导出。')
        report = self._read_report(rid)
        return {'submission_id': rid, 'can_compile': self.can_compile(),
                'report': report, 'files': self._files(rid, report)}

    def file_path(self, rid, kind):
        if not isinstance(rid, str) or not re.fullmatch(r'[a-f0-9]{32}', rid):
            return None
        if self.store.get(rid) is None:
            return None
        paths = self._paths(rid)
        path = {'tex': paths['source'], 'sty': paths['style'], 'pdf': paths['pdf']}.get(kind)
        if kind == 'pdf':
            report = self._read_report(rid)
            if not report or not report.get('success'):
                return None
        return path if path and path.is_file() else None

    def export(self, rid):
        item, reply = self.ensure_exportable(rid)
        lock = self._lock_for(rid)
        if not lock.acquire(blocking=False):
            raise ValueError('这份参考答案正在导出，请稍候。')
        try:
            return self._export(item, reply)
        finally:
            lock.release()

    def _export(self, item, reply):
        rid = item['id']
        paths = self._paths(rid)
        paths['folder'].mkdir(parents=True, exist_ok=True)
        key = self._version_key(item, reply)
        previous = self._read_report(rid)
        if (previous and previous.get('version_key') == key and previous.get('success')
                and paths['source'].is_file() and paths['pdf'].is_file()):
            return previous

        paths['style'].write_bytes(STYLE.read_bytes())
        shutil.rmtree(paths['build'], ignore_errors=True)
        prompt = self._prompt(item, reply)
        attempts = 0
        last_source = ''
        report = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            attempts = attempt
            raw = self.generator(prompt)
            source_text = extract_tex((raw or {}).get('raw') if isinstance(raw, dict) else raw)
            if len(source_text) > MAX_SOURCE_CHARS:
                raise ValueError('模型返回的 LaTeX 源码超过长度限制。')
            last_source = source_text
            paths['source'].write_text(source_text, encoding='utf-8')
            shutil.rmtree(paths['build'], ignore_errors=True)
            if UNSAFE_TEX.search(source_text):
                report = {'success': False, 'pdf': None, 'passes': [],
                          'issues': ['LaTeX 源码包含工作台禁止的 \\input、\\write18 等命令；未编译。']}
                break
            if not self.can_compile():
                report = {'success': False, 'pdf': None, 'passes': [],
                          'issues': ['本机未找到 XeLaTeX，无法导出 PDF。']}
                break
            report = self.compiler(paths['source'], paths['build'])
            if not isinstance(report, dict):
                report = {'success': False, 'pdf': None, 'passes': [],
                          'issues': ['编译器没有返回有效报告。']}
            if report.get('success'):
                break
            if attempt < MAX_ATTEMPTS:
                prompt = self._repair_prompt(item, source_text, report)

        issues = report.get('issues') if isinstance(report, dict) else []
        if not isinstance(issues, list):
            issues = [str(issues)]
        result = {
            'submission_id': rid,
            'version_key': key,
            'source_version': item.get('version'),
            'success': bool(isinstance(report, dict) and report.get('success')),
            'pdf': 'build/main.pdf' if isinstance(report, dict) and report.get('success') else None,
            'issues': issues,
            'passes': report.get('passes', []) if isinstance(report, dict) else [],
            'attempts': attempts,
            'scope': '仅生成排版源码、实际编译并检查版面；不重新验证数学、题号覆盖或评分建议。',
            'source_sha256': hashlib.sha256(last_source.encode('utf-8')).hexdigest(),
        }
        paths['report'].write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        return result

    def _prompt(self, item, reply):
        specs = '\n\n'.join(
            path.read_text(encoding='utf-8') for path in (
                SOLVER / 'references/exam-answer.md',
                SOLVER / 'references/latex-production.md',
            ))
        return (
            '你是高中数学参考答案的 LaTeX 排版阶段。下面已有一份通过结构校验的在线参考答案；'
            '你的任务只是把它排成可编译的完整 LaTeX 文档。不要重新解题，不要改变任何数学结论、'
            '数值、题号、小问或分值。若在线答案有缺项或矛盾，保留原样，不要自行补造或删题。\n'
            '只输出完整 .tex 源码本身：不要 Markdown 代码围栏，不要解释，不要输出其他文字。\n'
            '文档要求：使用 \\documentclass[11pt,UTF8,fontset=fandol]{ctexart}，'
            '导言区用 \\usepackage{reference-answer}。'
            '可用 \\papertitle{试卷名}{说明}、\\question{题号}{分值}、\\parttitle{小问}{标题}、'
            '\\insight{...}、\\difficulty{等级}{依据}、\\checkpoint{累计分}、'
            '\\begin{scoring}...\\end{scoring} 和 \\finalanswer{...}。'
            '数学公式只写 LaTeX 数学环境（\\(...\\) 与 \\[...\\]）；不要用 Unicode 公式、'
            '程序表达式或把推导整体塞进 \\text{...}。\n'
            '禁止使用 shell escape、\\write18、外部图片文件、\\input 外部文件或绝对路径字体；'
            '中文字体交给 ctex 处理。\n\n'
            '结构示例（只参考文档结构，不要照抄题目或数值）：\n'
            '\\documentclass[11pt,UTF8,fontset=fandol]{ctexart}\n'
            '\\usepackage{reference-answer}\n'
            '\\begin{document}\n'
            '\\papertitle{试卷名称}{适用学段、满分与评分口径}\n'
            '\\section*{一、选择题}\n'
            '\\question{1}{5}\n'
            '\\insight{……}\n'
            '……\n'
            '\\finalanswer{……}\n'
            '\\difficulty{基础}{……}\n'
            '\\end{document}\n\n'
            '排版与交付规范：\n' + specs +
            '\n\n原题（只用于核对题号、小问、条件与分值，不要改写）：\n' + item['data']['problem'] +
            '\n\n在线参考答案 reply（数学内容必须逐项保持一致，只做排版）：\n' + reply
        )

    def _repair_prompt(self, item, source, report):
        issues = report.get('issues') if isinstance(report, dict) else []
        return (
            '上次生成的 LaTeX 未通过实际编译或版面检查。只修复排版与编译问题，'
            '不得改变原题条件、数学结论、题号、小问或分值。输出修正后的完整 .tex 源码，'
            '不要 Markdown 代码围栏或解释。\n'
            '实际编译报告的问题：\n' + json.dumps(issues, ensure_ascii=False, indent=2) +
            '\n\n原题（核对用）：\n' + item['data']['problem'] +
            '\n\n上次源码：\n' + source
        )
