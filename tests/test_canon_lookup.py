import io
import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "questforge-runtime" / "scripts" / "canon_lookup.py"
spec = importlib.util.spec_from_file_location("canon_lookup", MODULE_PATH)
canon = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = canon
spec.loader.exec_module(canon)


class CanonLookupTests(unittest.TestCase):
    def make_zip(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as zf:
            zf.writestr(
                "checkpoints/CHECKPOINT-320.md",
                "Harrow & Flint agreed that Ody may draw against the reserve only for surveyed acquisitions.",
            )
            zf.writestr("characters/someone.md", "Unrelated material about a ferryman.")
        return out.getvalue()

    def test_zip_finds_historical_agreement(self):
        sha, matches = canon.search_zip_bytes(self.make_zip(), "Harrow Flint reserve acquisitions", 5)
        self.assertEqual(64, len(sha))
        self.assertTrue(matches)
        self.assertEqual("checkpoints/CHECKPOINT-320.md", matches[0].path)
        self.assertIn("reserve", matches[0].excerpt.lower())

    def test_empty_query_rejected(self):
        with self.assertRaises(ValueError):
            canon.retrieve(" ", local_archive="anything.zip")

    def test_not_established_is_fail_closed(self):
        with tempfile.NamedTemporaryFile(suffix=".zip") as f:
            f.write(self.make_zip())
            f.flush()
            result = canon.retrieve("purple dragon mortgage", local_archive=f.name)
        self.assertEqual("not_established", result["status"])
        self.assertEqual([], result["matches"])


if __name__ == "__main__":
    unittest.main()
