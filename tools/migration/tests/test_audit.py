import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit import audit
from convert import convert_export
from test_convert import fixture


class AuditTests(unittest.TestCase):
    def test_acceptance_checks_actual_generated_files_and_counts(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            root = Path(temp)
            convert_export(fixture(), root / "posts", root / "report.json", ["old.test"], ["cdn.test"], ["r18"])
            result = audit(root / "report.json", root / "posts", root / "legacy-pages")
            self.assertEqual(result["posts"], 1)
            self.assertEqual(result["uniqueRoutes"], 1)
            self.assertFalse(result["networkVerified"])
            self.assertEqual(result["inlineMediaByHost"], {"cdn.test": 1})


if __name__ == "__main__":
    unittest.main()
