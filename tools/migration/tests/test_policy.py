import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from policy import Report, UrlPolicy, excluded_terms, original_path, select_posts


class SelectionTests(unittest.TestCase):
    def test_all_adult_descendants_are_excluded(self):
        terms = [
            {"id": 1, "taxonomy": "category", "slug": "source-share", "parent": 0},
            {"id": 2, "taxonomy": "category", "slug": "child", "parent": 1},
            {"id": 3, "taxonomy": "category", "slug": "grandchild", "parent": 2},
            {"id": 4, "taxonomy": "post_tag", "slug": "child", "parent": 1},
        ]
        self.assertEqual(excluded_terms(terms, {"source-share", "r18"}), {1, 2, 3})

    def test_publish_only_password_protection_and_exclusion(self):
        good = {"id": 1, "type": "post", "status": "publish", "password": "", "term_ids": [5]}
        posts = [good, {**good, "id": 2, "status": "draft"}, {**good, "id": 3, "password": "secret"},
                 {**good, "id": 4, "term_ids": [5, 9]}, {**good, "id": 5, "type": "attachment"}]
        report = Report()
        self.assertEqual(select_posts(posts, {9}, report), [good])
        self.assertEqual(report.counts["sourcePosts"], 5)
        self.assertEqual(report.counts["passwordProtected"], 1)

    def test_permalink_hierarchy_is_not_regenerated(self):
        self.assertEqual(original_path({"id": 17, "link": "https://old.test/tech/tools/17/"}), "/tech/tools/17/")


class UrlPolicyTests(unittest.TestCase):
    def setUp(self):
        self.report = Report()
        self.policy = UrlPolicy(["old.test"], ["cdn.test"], {"/tech/17/": "/tech/17/", "id:17": "/tech/17/"}, self.report, 17)

    def test_internal_urls_and_wp_query_links_rewrite(self):
        self.assertEqual(self.policy.url("https://old.test/tech/17/#example"), "/tech/17/#example")
        self.assertEqual(self.policy.url("http://old.test/?p=17"), "/tech/17/")

    def test_historic_category_paths_resolve_only_known_public_ids(self):
        self.assertEqual(self.policy.url("https://old.test/old-category/17/#section"), "/tech/17/#section")
        self.assertEqual(self.policy.url("https://old.test/?p=17/?amp=1"), "/tech/17/")
        self.assertEqual(self.policy.url("https://old.test/private/999/"), "https://old.test/private/999/")
        self.assertEqual(self.report.issues[-1]["kind"], "unresolvedInternalLink")

    def test_only_verified_media_is_retained_without_host_guessing(self):
        self.assertEqual(self.policy.url("https://cdn.test/uploads/a.jpg", True), "https://cdn.test/uploads/a.jpg")
        self.assertIsNone(self.policy.url("https://old.test/uploads/a.jpg", True))
        self.assertIsNone(self.policy.url("/uploads/a.jpg", True))
        self.assertIsNone(self.policy.url("https://secret:pass@cdn.test/a.jpg", True))

    def test_no_executable_protocol_or_private_system_link(self):
        self.assertIsNone(self.policy.url("javascript:alert(1)"))
        self.assertIsNone(self.policy.url("mailto:private@example.test"))
        self.assertIsNone(self.policy.url("https://old.test/wp-admin/"))

    def test_exact_verified_external_url_not_whole_host_is_allowed(self):
        self.policy.verified_media = {"http://other.test/a.jpg": "https://other.test/a.jpg"}
        self.assertEqual(self.policy.url("http://other.test/a.jpg", True), "https://other.test/a.jpg")
        self.assertIsNone(self.policy.url("https://other.test/b.jpg", True))


if __name__ == "__main__":
    unittest.main()
