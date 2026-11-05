import json
from pathlib import Path
import tempfile
import unittest

from app.server import Store
from app.exam_export import ExamExporter, extract_tex


TEX = r'''\documentclass[UTF8]{ctexart}
\usepackage{reference-answer}
\begin{document}
\papertitle{测试卷}{高中}
\question{1}{5}
\finalanswer{\(x=1\)。}
\end{document}
'''


class ExamExportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'data.db')
        self.sid = self.store.create_session('试卷')
        self.rid = self.store.submit(self.sid, {'problem': '解 x+1=2。', 'mode': 'exam_answer'}, True)
        self.store.update(self.rid, 'ready', {'status': 'ready',
            'output': {'reply': '1. 解方程 x+1=2，得 x=1。', 'result': None}, 'attempts': []})

    def tearDown(self):
        self.tmp.cleanup()

    def exporter(self, generator, compiler):
        return ExamExporter(self.store, generator=generator, compiler=compiler,
                            output_root=Path(self.tmp.name) / 'exports')

    def test_successful_export_is_reused(self):
        calls = {'generate': 0, 'compile': 0}

        def generator(prompt):
            calls['generate'] += 1
            return {'raw': '```latex\n' + TEX + '```'}

        def compiler(source, output):
            calls['compile'] += 1
            output.mkdir(parents=True, exist_ok=True)
            (output / 'main.pdf').write_bytes(b'%PDF-1.4 fake')
            return {'success': True, 'pdf': str(output / 'main.pdf'),
                    'passes': [{'pass': 1, 'exit_code': 0}, {'pass': 2, 'exit_code': 0}], 'issues': []}

        exporter = self.exporter(generator, compiler)
        first = exporter.export(self.rid)
        self.assertTrue(first['success'])
        self.assertEqual(first['attempts'], 1)
        self.assertIsNotNone(exporter.file_path(self.rid, 'pdf'))
        self.assertIn(r'\question{1}{5}', exporter.file_path(self.rid, 'tex').read_text(encoding='utf-8'))

        second = exporter.export(self.rid)
        self.assertTrue(second['success'])
        self.assertEqual(calls, {'generate': 1, 'compile': 1})

    def test_compile_failure_is_repaired_without_changing_math(self):
        sources = [TEX.replace(r'\finalanswer', r'\unknowncommand{'), TEX]
        calls = {'count': 0}

        def generator(prompt):
            if calls['count'] == 1:
                self.assertIn('只修复排版与编译问题', prompt)
            calls['count'] += 1
            return {'raw': sources[calls['count'] - 1]}

        def compiler(source, output):
            text = source.read_text(encoding='utf-8')
            if r'\unknowncommand' in text:
                return {'success': False, 'pdf': None, 'passes': [{'pass': 1, 'exit_code': 1}],
                        'issues': ['XeLaTeX 编译失败，检查实际编译日志']}
            output.mkdir(parents=True, exist_ok=True)
            (output / 'main.pdf').write_bytes(b'%PDF-1.4 fake')
            return {'success': True, 'pdf': str(output / 'main.pdf'),
                    'passes': [{'pass': 1, 'exit_code': 0}, {'pass': 2, 'exit_code': 0}], 'issues': []}

        result = self.exporter(generator, compiler).export(self.rid)
        self.assertTrue(result['success'])
        self.assertEqual(result['attempts'], 2)

    def test_failed_export_keeps_source_and_reports_issues(self):
        def generator(prompt):
            return {'raw': TEX}

        def compiler(source, output):
            return {'success': False, 'pdf': None, 'passes': [{'pass': 1, 'exit_code': 1}],
                    'issues': ['XeLaTeX 编译失败，检查实际编译日志']}

        exporter = self.exporter(generator, compiler)
        result = exporter.export(self.rid)
        self.assertFalse(result['success'])
        self.assertEqual(result['attempts'], 3)
        self.assertIn('XeLaTeX 编译失败', result['issues'][0])
        self.assertIsNotNone(exporter.file_path(self.rid, 'tex'))
        self.assertIsNone(exporter.file_path(self.rid, 'pdf'))

    def test_only_current_ready_exam_answer_can_be_exported(self):
        exporter = self.exporter(lambda prompt: {'raw': TEX}, lambda source, output: {'success': True})
        self.sid2 = self.store.create_session('普通练习')
        rid2 = self.store.submit(self.sid2, {'problem': 'x+1=2', 'mode': 'solve'}, True)
        self.store.update(rid2, 'ready', {'status': 'ready', 'output': {'reply': 'x=1', 'result': None}})
        with self.assertRaises(ValueError) as context:
            exporter.ensure_exportable(rid2)
        self.assertIn('生成试卷参考答案', str(context.exception))

        self.store.submit(self.sid, {'problem': '新版本', 'mode': 'exam_answer'}, True)
        with self.assertRaises(ValueError) as context:
            exporter.ensure_exportable(self.rid)
        self.assertIn('历史版本', str(context.exception))

    def test_unsafe_tex_commands_are_not_compiled(self):
        def compiler(source, output):
            raise AssertionError('不安全源码不应进入编译器')

        result = self.exporter(lambda prompt: {'raw': TEX.replace(
            r'\finalanswer', r'\immediate\write18{echo bad}\finalanswer')}, compiler).export(self.rid)
        self.assertFalse(result['success'])
        self.assertEqual(result['attempts'], 1)
        self.assertIn('禁止', result['issues'][0])

    def test_source_without_template_style_is_rejected_before_compile(self):
        bad = TEX.replace(r'\usepackage{reference-answer}', '')

        def compiler(source, output):
            raise AssertionError('未使用模板样式的源码不应进入编译器')

        result = self.exporter(lambda prompt: {'raw': bad}, compiler).export(self.rid)
        self.assertFalse(result['success'])
        self.assertEqual(result['attempts'], 3)
        self.assertIn('reference-answer', result['issues'][0])

    def test_scoring_table_must_use_scoring_environment(self):
        bad = TEX.replace(r'\finalanswer{\(x=1\)。}',
                          r'\textbf{采分点}\begin{tabular}{cc}1&2\end{tabular}')

        def compiler(source, output):
            raise AssertionError('用普通 tabular 代替采分表时不应进入编译器')

        result = self.exporter(lambda prompt: {'raw': bad}, compiler).export(self.rid)
        self.assertFalse(result['success'])
        self.assertEqual(result['attempts'], 3)
        self.assertIn('scoring', result['issues'][0])

    def test_missing_xelatex_keeps_source(self):
        from unittest.mock import patch
        exporter = ExamExporter(self.store, generator=lambda prompt: {'raw': TEX},
                                output_root=Path(self.tmp.name) / 'exports')
        with patch('app.exam_export.shutil.which', return_value=None):
            result = exporter.export(self.rid)
        self.assertFalse(result['success'])
        self.assertIn('XeLaTeX', result['issues'][0])
        self.assertIsNotNone(exporter.file_path(self.rid, 'tex'))
        self.assertIsNone(exporter.file_path(self.rid, 'pdf'))

    def test_source_extraction_rejects_non_latex(self):
        with self.assertRaises(ValueError):
            extract_tex('这里没有 LaTeX 文档。')
        self.assertTrue(extract_tex('说明\n' + TEX).startswith(r'\documentclass'))
        self.assertTrue(extract_tex(json.dumps({'latex_source': TEX})).startswith(r'\documentclass'))


if __name__ == '__main__':
    unittest.main()
