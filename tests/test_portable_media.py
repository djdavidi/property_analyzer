from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from drainage_core.media import read_blob


class PortableMediaTests(unittest.TestCase):
    def test_stale_absolute_path_falls_back_to_frozen_source_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "blobs").mkdir()
            payload = b"frozen image bytes"
            digest = sha256(payload).hexdigest()
            (root / "blobs" / digest).write_bytes(payload)
            self.assertEqual(
                read_blob(
                    {"sha256": digest, "blob_path": str(root / "old-machine/missing.png")},
                    roots=[root],
                ),
                payload,
            )

    def test_corruption_is_rejected_instead_of_silently_using_another_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "blobs").mkdir()
            payload = b"frozen image bytes"
            digest = sha256(payload).hexdigest()
            (root / "blobs" / digest).write_bytes(payload)
            bad = root / "bad.png"
            bad.write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                read_blob({"sha256": digest, "blob_path": str(bad)}, roots=[root])

    def test_media_hash_cannot_be_a_path(self):
        with self.assertRaisesRegex(ValueError, "Invalid media"):
            read_blob({"sha256": "../private-file"})


if __name__ == "__main__":
    unittest.main()
