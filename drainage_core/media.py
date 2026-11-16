"""Resolve frozen media by content hash after a project/package is relocated."""

from hashlib import sha256
from pathlib import Path
import re


def read_blob(info, *, roots=()):
    digest = info.get("sha256", "")
    if not re.fullmatch("[a-f0-9]{64}", digest):
        raise ValueError("Invalid media content hash")
    candidates = []
    if info.get("blob_path"):
        candidates.append(Path(info["blob_path"]))
    candidates.extend(Path(root) / "blobs" / digest for root in roots)
    candidates.append(Path(__file__).resolve().parents[1] / "data/public/blobs" / digest)
    for file in candidates:
        if file.is_file():
            payload = file.read_bytes()
            if sha256(payload).hexdigest() != digest:
                raise ValueError("Media snapshot hash mismatch")
            return payload
    raise FileNotFoundError("Cached media missing; copy the source blobs with the project")
