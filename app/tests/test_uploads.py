import base64
from io import BytesIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from app import uploads

PNG_BYTES = b'\x89PNG\r\n\x1a\n' + b'0' * 24
PNG_BASE64 = base64.b64encode(PNG_BYTES).decode()
PDF_BYTES = b'%PDF-1.4\n' + b'0' * 24
PDF_BASE64 = base64.b64encode(PDF_BYTES).decode()


def docx_bytes(text='第一段'):
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('word/document.xml',
                         '<?xml version="1.0" encoding="UTF-8"?>'
                         '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                         'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
                         + text + '</w:t></w:r></w:p></w:body></w:document>')
    return buffer.getvalue()


class UploadTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / 'uploads'
        self.env = patch.dict(os.environ, {'MATH_UPLOAD_DIR': str(self.folder)}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_normalize_accepts_request_and_stored_forms(self):
        self.assertEqual(uploads.normalize_attachments(None), [])
        request = uploads.normalize_attachments([
            {'name': 'draft.png', 'base64': PNG_BASE64},
            {'name': 'problem.pdf', 'base64': PDF_BASE64},
        ])
        self.assertEqual(request[0]['ext'], '.png')
        self.assertEqual(request[1]['ext'], '.pdf')
        stored = uploads.normalize_attachments([{
            'sha256': 'a' * 64, 'ext': '.pdf', 'size': 10,
            'kind': 'pdf', 'mime': 'application/pdf'}])
        self.assertEqual(stored[0]['kind'], 'pdf')

    def test_persist_writes_content_addressed_files_and_dedupes(self):
        data = uploads.persist({'attachments': [
            {'name': 'draft.png', 'base64': PNG_BASE64},
            {'name': 'problem.pdf', 'base64': PDF_BASE64},
            {'name': 'same.png', 'base64': PNG_BASE64},
        ]})
        self.assertEqual(len(data['attachments']), 2)
        kinds = [item['kind'] for item in data['attachments']]
        self.assertEqual(kinds, ['image', 'pdf'])
        for item in data['attachments']:
            self.assertNotIn('base64', item)
            self.assertNotIn('name', item)
            path = self.folder / (item['sha256'] + item['ext'])
            self.assertTrue(path.is_file())
        self.assertEqual(len(list(self.folder.iterdir())), 2)

    def test_persist_rejects_bad_content_and_limits(self):
        with self.assertRaisesRegex(ValueError, '编码'):
            uploads.persist({'attachments': [{'name': 'x.png', 'base64': 'not base64!'}]})
        with self.assertRaisesRegex(ValueError, 'PNG'):
            uploads.persist({'attachments': [
                {'name': 'x.png', 'base64': base64.b64encode(b'GIF89a').decode()}]})
        with self.assertRaisesRegex(ValueError, 'DOCX'):
            uploads.persist({'attachments': [
                {'name': 'x.docx', 'base64': base64.b64encode(b'not a zip').decode()}]})
        too_many = [{'name': f'{i}.txt', 'base64': base64.b64encode(b'x').decode()}
                    for i in range(4)]
        with self.assertRaisesRegex(ValueError, '3'):
            uploads.normalize_attachments(too_many)
        with self.assertRaisesRegex(ValueError, '支持'):
            uploads.normalize_attachments([{'name': 'x.exe', 'base64': 'eA=='}])

    def test_normalize_rejects_invalid_metadata(self):
        for payload, message in [
            ({'sha256': 'not-a-hash', 'ext': '.png', 'size': 1,
              'kind': 'image', 'mime': 'image/png'}, '指纹'),
            ({'sha256': 'a' * 64, 'ext': '.gif', 'size': 1,
              'kind': 'image', 'mime': 'image/gif'}, '格式'),
            ({'sha256': 'a' * 64, 'ext': '.png', 'size': 0,
              'kind': 'image', 'mime': 'image/png'}, '大小'),
            ({'sha256': 'a' * 64, 'ext': '.png', 'size': 1,
              'kind': 'pdf', 'mime': 'image/png'}, '类型'),
        ]:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, message):
                    uploads.normalize_attachments([payload])

    def test_path_for_refuses_traversal_and_missing_files(self):
        self.assertIsNone(uploads.path_for('../etc/passwd', '.png'))
        self.assertIsNone(uploads.path_for('a' * 64, '.gif'))
        self.assertIsNone(uploads.path_for('a' * 64, '.png'))
        data = uploads.persist({'attachments': [{'name': 'draft.png', 'base64': PNG_BASE64}]})
        item = data['attachments'][0]
        self.assertIsNotNone(uploads.path_for(item['sha256'], item['ext']))
        self.assertEqual(uploads.mime_for('.webp'), 'image/webp')
        self.assertTrue(uploads.is_inline('.md'))
        self.assertFalse(uploads.is_inline('.docx'))

    def test_extract_text_from_digital_documents_only(self):
        self.assertEqual(uploads.extract_text('lesson.txt', base64.b64encode('第一行\n第二行'.encode()).decode())['text'],
                         '第一行\n第二行')
        docx = base64.b64encode(docx_bytes('教学目标')).decode()
        self.assertEqual(uploads.extract_text('lesson.docx', docx)['text'], '教学目标')
        with self.assertRaisesRegex(ValueError, '文字识别'):
            uploads.extract_text('draft.png', PNG_BASE64)
        empty = uploads.extract_text('empty.txt', base64.b64encode(b'   ').decode())
        self.assertEqual(empty['text'], '')
        self.assertIn('扫描版', empty['warning'])

    def test_extract_text_truncates_long_text(self):
        text = '数' * 20010
        result = uploads.extract_text('long.txt', base64.b64encode(text.encode()).decode())
        self.assertTrue(result['truncated'])
        self.assertEqual(len(result['text']), 20000)


if __name__ == '__main__':
    unittest.main()
