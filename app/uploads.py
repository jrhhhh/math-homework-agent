"""Local attachment storage and digital-text extraction.

Attachments are files the student or teacher uploaded for their own reference.
They are stored locally and never sent to the model. Digital documents (PDF,
DOCX, TXT, MD) may expose their embedded text through an explicit "extract"
action; the student reviews that text before putting it into a problem or
solution field. Images are never transcribed: the project has no handwriting
recognition layer.
"""
import base64
import binascii
from io import BytesIO
import hashlib
import os
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / '.local' / 'uploads'
MAX_BYTES = 5 * 1024 * 1024
MAX_FILES = 3
MAX_EXTRACT_CHARS = 20000
_SHA = re.compile(r'[0-9a-f]{64}')
_ALLOWED = {
    '.png': ('image', 'image/png'),
    '.jpg': ('image', 'image/jpeg'),
    '.webp': ('image', 'image/webp'),
    '.pdf': ('pdf', 'application/pdf'),
    '.docx': ('docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
    '.txt': ('text', 'text/plain'),
    '.md': ('text', 'text/markdown'),
}
EXTENSIONS = set(_ALLOWED)
W_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def upload_dir():
    return Path(os.environ.get('MATH_UPLOAD_DIR', str(DEFAULT_DIR)))


def _extension(name):
    suffix = Path(str(name)).suffix.lower()
    if suffix == '.jpeg':
        suffix = '.jpg'
    return suffix if suffix in _ALLOWED else None


def _kind(extension):
    return _ALLOWED[extension][0]


def _mime(extension):
    return _ALLOWED[extension][1]


def normalize_attachments(value):
    """Validate a request attachment list or already-stored metadata."""
    if value in (None, ''):
        return []
    if not isinstance(value, list):
        raise ValueError('附件必须为数组。')
    if len(value) > MAX_FILES:
        raise ValueError('最多上传 3 个附件。')
    result = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError('附件信息必须为对象。')
        name = item.get('name', '')
        if not isinstance(name, str) or len(name) > 120:
            raise ValueError('附件名称不合法。')
        extension = _extension(name)
        if 'base64' in item:
            encoded = item.get('base64')
            if not extension or not isinstance(encoded, str) or not encoded:
                raise ValueError('附件格式不支持或内容为空。')
            if len(encoded) > MAX_BYTES * 2:
                raise ValueError('单个附件不能超过 5 MB。')
            result.append({'name': name, 'base64': encoded, 'ext': extension})
            continue
        digest = item.get('sha256')
        stored_ext = item.get('ext')
        size = item.get('size')
        kind = item.get('kind')
        mime = item.get('mime')
        if not isinstance(digest, str) or not _SHA.fullmatch(digest):
            raise ValueError('附件指纹不合法。')
        if stored_ext not in _ALLOWED:
            raise ValueError('附件格式不合法。')
        if type(size) is not int or not 0 < size <= MAX_BYTES:
            raise ValueError('附件大小不合法。')
        if kind != _kind(stored_ext) or mime != _mime(stored_ext):
            raise ValueError('附件类型不合法。')
        result.append({'sha256': digest, 'ext': stored_ext, 'size': size,
                       'kind': kind, 'mime': mime})
    return result


def _sniff(raw, extension):
    if extension == '.png':
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('文件内容不是 PNG。')
    elif extension == '.jpg':
        if not raw.startswith(b'\xff\xd8\xff'):
            raise ValueError('文件内容不是 JPEG。')
    elif extension == '.webp':
        if len(raw) < 12 or raw[:4] != b'RIFF' or raw[8:12] != b'WEBP':
            raise ValueError('文件内容不是 WebP。')
    elif extension == '.pdf':
        if not raw.startswith(b'%PDF-'):
            raise ValueError('文件内容不是 PDF。')
    elif extension == '.docx':
        try:
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                if 'word/document.xml' not in archive.namelist():
                    raise ValueError('DOCX 缺少正文。')
        except (zipfile.BadZipFile, KeyError) as exc:
            raise ValueError('文件内容不是有效的 DOCX。') from exc
    elif extension in ('.txt', '.md'):
        try:
            raw.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValueError('文本附件必须是 UTF-8。') from exc
    return _kind(extension), _mime(extension)


def persist(data):
    """Decode request attachments, store by content hash, return metadata only."""
    attachments = data.get('attachments')
    if not attachments:
        return data
    stored = []
    seen = set()
    folder = upload_dir()
    for item in attachments:
        if 'base64' not in item:
            stored.append(item)
            continue
        try:
            raw = base64.b64decode(item['base64'], validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError('附件内容编码无效。') from exc
        if not raw or len(raw) > MAX_BYTES:
            raise ValueError('单个附件不能超过 5 MB。')
        extension = item.get('ext') or _extension(item.get('name'))
        if not extension:
            raise ValueError('附件格式不支持。')
        kind, mime = _sniff(raw, extension)
        digest = hashlib.sha256(raw).hexdigest()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (digest + extension)
        if not path.exists():
            temporary = path.with_name(path.name + '.tmp')
            temporary.write_bytes(raw)
            os.replace(temporary, path)
        key = (digest, extension)
        if key in seen:
            continue
        seen.add(key)
        # Keep only content facts: the original filename can contain a student's name.
        stored.append({'sha256': digest, 'ext': extension, 'size': len(raw),
                       'kind': kind, 'mime': mime})
    data['attachments'] = stored
    data.pop('image', None)
    return data


def path_for(sha256, extension):
    if not isinstance(sha256, str) or not _SHA.fullmatch(sha256):
        return None
    if extension not in _ALLOWED:
        return None
    path = upload_dir() / (sha256 + extension)
    try:
        path = path.resolve()
        if path.parent != upload_dir().resolve():
            return None
    except OSError:
        return None
    return path if path.is_file() else None


def mime_for(extension):
    return _mime(extension) if extension in _ALLOWED else 'application/octet-stream'


def is_inline(extension):
    return extension in ('.png', '.jpg', '.webp', '.pdf', '.txt', '.md')


def extract_text(name, encoded):
    """Return digital text from a document; never OCRs images."""
    extension = _extension(name)
    if extension not in _ALLOWED:
        raise ValueError('只支持 PNG、JPEG、WebP、PDF、DOCX、TXT 或 MD 附件。')
    if _kind(extension) == 'image':
        raise ValueError('图片不做文字识别；请直接填写文字。')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error, TypeError) as exc:
        raise ValueError('附件内容编码无效。') from exc
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('单个附件不能超过 5 MB。')
    if extension in ('.txt', '.md'):
        text = raw.decode('utf-8-sig')
    elif extension == '.docx':
        text = _docx_text(raw)
    else:
        text = _pdf_text(raw)
    text = text.strip()
    truncated = len(text) > MAX_EXTRACT_CHARS
    if truncated:
        text = text[:MAX_EXTRACT_CHARS]
    return {'text': text, 'truncated': truncated,
            'warning': '已截断为 20000 字。' if truncated else
                       ('' if text else '没有提取到可复制文字；扫描版请手动输入或粘贴。')}


def _docx_text(raw):
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            item = archive.getinfo('word/document.xml')
            if item.file_size > 10 * 1024 * 1024:
                raise ValueError('DOCX 正文过大。')
            xml = archive.read(item)
        if b'<!DOCTYPE' in xml.upper():
            raise ValueError('DOCX 包含不支持的 XML 声明。')
        root = ET.fromstring(xml)
    except (KeyError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise ValueError('无法读取该 DOCX。') from exc
    paragraphs = []
    for paragraph in root.iter(W_NS + 'p'):
        text = ''.join(node.text or '' for node in paragraph.iter(W_NS + 't'))
        if text.strip():
            paragraphs.append(text)
    return '\n'.join(paragraphs)


def _pdf_text(raw):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError('读取 PDF 需要安装 pypdf。') from exc
    try:
        reader = PdfReader(BytesIO(raw), strict=True)
        if len(reader.pages) > 100:
            raise ValueError('PDF 最多支持 100 页。')
        return '\n'.join(page.extract_text() or '' for page in reader.pages)
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError('无法读取该 PDF；扫描版请手动输入或粘贴。') from exc
