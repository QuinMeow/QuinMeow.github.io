import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from convert import convert_export, published_date


def fixture():
    post = {"id": 7, "type": "post", "status": "publish", "password": "", "title": 'Title "quoted"',
            "content": '<p>Public</p><img src="https://cdn.test/a.jpg">', "excerpt": "Excerpt", "date": "2020-01-02 03:04:05",
            "link": "https://old.test/tech/tools/7/", "term_ids": [2, 3]}
    return {"schema_version": 1, "site": {"timezone": "Asia/Shanghai", "utc_offset_hours": 8},
            "terms": [{"id": 1, "taxonomy": "category", "name": "Excluded", "slug": "r18", "parent": 0},
                      {"id": 2, "taxonomy": "category", "name": "Technology", "slug": "tech", "parent": 0},
                      {"id": 3, "taxonomy": "post_tag", "name": "Tooling", "slug": "tooling", "parent": 0}],
            "posts": [post, {**post, "id": 8, "content": "PRIVATE BODY", "title": "PRIVATE TITLE", "term_ids": [1]}],
            "attachments": [], "comments": [{"email": "secret@example.test", "body": "PRIVATE COMMENT"}]}


class ConversionTests(unittest.TestCase):
    def run_conversion(self, data, root):
        return convert_export(data, root / "posts", root / "report.json", ["old.test"], ["cdn.test"], ["r18"])

    def test_named_timezone_takes_precedence_over_stale_wordpress_offset(self):
        self.assertEqual(published_date({"date": "2020-01-02 03:04:05"}, {"timezone": "Asia/Shanghai", "utc_offset_hours": 0}),
                         "2020-01-02T03:04:05+08:00")

    def test_actual_source_local_and_gmt_pair_takes_precedence(self):
        self.assertEqual(published_date({"date": "2020-01-02 03:04:05", "date_gmt": "2020-01-01 19:04:05"},
                                        {"timezone": "UTC", "utc_offset_hours": 0}), "2020-01-02T03:04:05+08:00")

    def test_description_fallback_and_word_count_use_visible_prose(self):
        data = fixture()
        data["posts"][0].update(excerpt="", content='<h2>Heading</h2><p>First visible paragraph.</p><pre><code>ignored code</code></pre>')
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            root = Path(temp)
            self.run_conversion(data, root)
            content = (root / "posts/wp-7.md").read_text(encoding="utf-8")
            self.assertIn('description: "Heading First visible paragraph."', content)
            self.assertIn("wordCount: 4", content)
            self.assertIn("## Heading", content)

    def test_only_public_selected_content_and_metadata_are_written(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            root = Path(temp)
            report = self.run_conversion(fixture(), root)
            content = (root / "posts/wp-7.md").read_text(encoding="utf-8")
            self.assertIn('slug: "tech/tools/7"', content)
            self.assertIn('published: "2020-01-02T03:04:05+08:00"', content)
            self.assertIn('originalPath: "/tech/tools/7/"', content)
            combined = content + (root / "report.json").read_text(encoding="utf-8")
            self.assertNotIn("PRIVATE", combined)
            self.assertNotIn("secret@example.test", combined)
            self.assertEqual(report["counts"]["excludedCategory"], 1)
            self.assertEqual(len(list((root / "posts").glob("*.md"))), 1)

    def test_pages_are_separate_from_post_cards(self):
        data = fixture()
        data["posts"].append({**data["posts"][0], "id": 9, "type": "page", "link": "https://old.test/about/"})
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            root = Path(temp)
            self.run_conversion(data, root)
            self.assertTrue((root / "legacy-pages/wp-9.md").exists())
            self.assertFalse((root / "posts/wp-9.md").exists())

    def test_fail_closed_without_adult_exclusion_taxonomy(self):
        data = fixture()
        data["terms"] = data["terms"][1:]
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            with self.assertRaisesRegex(ValueError, "No adult-resource"):
                self.run_conversion(data, Path(temp))

    def test_existing_content_is_never_silently_overwritten(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            root = Path(temp)
            self.run_conversion(fixture(), root)
            with self.assertRaisesRegex(ValueError, "must be empty"):
                self.run_conversion(fixture(), root)

    def test_duplicate_routes_are_rejected(self):
        data = fixture()
        data["posts"].append({**data["posts"][0], "id": 10})
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            with self.assertRaisesRegex(ValueError, "Duplicate permalink"):
                self.run_conversion(data, Path(temp))


if __name__ == "__main__":
    unittest.main()
