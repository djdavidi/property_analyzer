"""Portable, opaque evidence attachments. No extraction, execution or jurisdiction rules."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re

MAX_ATTACHMENT_BYTES = 16 * 1024 * 1024
MEDIA_TYPES = {'.pdf':'application/pdf', '.png':'image/png', '.jpg':'image/jpeg',
               '.jpeg':'image/jpeg', '.txt':'text/plain', '.csv':'text/csv'}


def now():
    return datetime.now(timezone.utc).isoformat()


def _filename(value):
    if not isinstance(value,str) or not value or len(value)>180:
        raise ValueError('Attachment filename must be between 1 and 180 characters')
    if value in ('.','..') or any(c in value for c in '/\\\x00\r\n') or any(ord(c)<32 for c in value):
        raise ValueError('Attachment filenames cannot contain paths or control characters')
    suffix=Path(value).suffix.lower()
    if suffix not in MEDIA_TYPES:
        raise ValueError('Supported evidence files: PDF, PNG, JPEG, TXT and CSV; executable files are rejected')
    return suffix


def _content(filename, content):
    suffix=_filename(filename)
    if not isinstance(content,bytes) or not 0<len(content)<=MAX_ATTACHMENT_BYTES:
        raise ValueError('Attachment must contain 1 byte to 16 MB')
    executable=(b'MZ',b'\x7fELF',b'#!',b'\xcf\xfa\xed\xfe',b'\xce\xfa\xed\xfe',
                b'\xfe\xed\xfa\xcf',b'\xfe\xed\xfa\xce',b'\xca\xfe\xba\xbe')
    if content.startswith(executable):
        raise ValueError('Executable attachment content rejected')
    signatures={'.pdf':b'%PDF-', '.png':b'\x89PNG\r\n\x1a\n', '.jpg':b'\xff\xd8\xff', '.jpeg':b'\xff\xd8\xff'}
    if suffix in signatures and not content.startswith(signatures[suffix]):
        raise ValueError('Attachment content does not match its file type')
    if suffix in ('.txt','.csv'):
        try: content.decode('utf-8')
        except UnicodeDecodeError: raise ValueError('Text evidence must be UTF-8') from None
        if b'\x00' in content: raise ValueError('Binary content rejected as text evidence')
    return suffix


class AttachmentStore:
    """Content addressed local bytes. Filenames are metadata, never filesystem paths."""
    def __init__(self, directory):
        self.root=Path(directory)
        if self.root.is_symlink(): raise ValueError('Attachment directory cannot be a symlink')
        self.root.mkdir(parents=True,exist_ok=True)
        self.root=self.root.resolve()

    def _path(self,digest):
        if not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest):
            raise ValueError('Invalid attachment SHA-256')
        path=self.root/digest
        if path.is_symlink(): raise ValueError('Attachment symlink rejected')
        return path

    def add(self, filename, content, metadata=None):
        suffix=_content(filename,content)
        digest=sha256(content).hexdigest(); path=self._path(digest)
        if path.exists():
            if self.read(digest)!=content: raise ValueError('Existing attachment hash mismatch')
        else:
            flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
            fd=os.open(path,flags,0o600)
            with os.fdopen(fd,'wb') as stream: stream.write(content)
        # User metadata cannot override integrity fields.
        info=deepcopy(metadata or {})
        info.update(id=digest,sha256=digest,filename=filename,size_bytes=len(content),
                    media_type=MEDIA_TYPES[suffix],stored_at=info.get('stored_at') or now())
        json.dumps(info,allow_nan=False)
        return info

    def read(self,digest):
        path=self._path(digest)
        fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
        with os.fdopen(fd,'rb') as stream: content=stream.read(MAX_ATTACHMENT_BYTES+1)
        if len(content)>MAX_ATTACHMENT_BYTES or sha256(content).hexdigest()!=digest:
            raise ValueError('Attachment bytes do not match SHA-256')
        return content

    def verify(self,manifests):
        for item in manifests:
            content=self.read(item['sha256'])
            if item.get('id')!=item['sha256'] or item.get('size_bytes')!=len(content):
                raise ValueError('Attachment manifest does not match original bytes')
            _content(item['filename'],content)

    def export(self,manifests):
        self.verify(manifests)
        return [{**deepcopy(item),'content_base64':base64.b64encode(self.read(item['sha256'])).decode('ascii')}
                for item in manifests]

    def import_bundle(self,items):
        verified=[]
        for item in items:
            try: content=base64.b64decode(item['content_base64'],validate=True)
            except (KeyError,ValueError): raise ValueError('Invalid attachment bundle encoding') from None
            if sha256(content).hexdigest()!=item.get('sha256') or item.get('id')!=item.get('sha256'):
                raise ValueError('Imported attachment hash mismatch')
            if len(content)!=item.get('size_bytes'): raise ValueError('Imported attachment size mismatch')
            _content(item['filename'],content)
            verified.append((item,content))
        # Validate the entire bundle before writing any bytes.
        return [self.add(item['filename'],content,{k:v for k,v in item.items() if k!='content_base64'})
                for item,content in verified]


def validate_references(assessment):
    """Dangling references are errors, while absent evidence remains an explicit gap."""
    manifests=assessment.get('attachments',[])
    ids={item['id'] for item in manifests}
    for item in manifests:
        if item.get('id')!=item.get('sha256') or not re.fullmatch('[a-f0-9]{64}',str(item.get('sha256',''))):
            raise ValueError('Invalid attachment manifest digest')
        _filename(item['filename'])
    for record in assessment.get('records',[])+assessment.get('credit_history',[]):
        for ref in record.get('evidence_refs',[]):
            if ref.get('attachment_id') and ref['attachment_id'] not in ids:
                raise ValueError('Evidence references an attachment missing from this case')
            if 'page' in ref and ref['page'] is not None and (isinstance(ref['page'],bool) or not isinstance(ref['page'],int) or ref['page']<1):
                raise ValueError('Document page references must be positive whole numbers')
