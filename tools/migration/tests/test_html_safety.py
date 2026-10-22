import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from html_safety import sanitize
from policy import Report, UrlPolicy
from shortcodes import expand_shortcodes


class HtmlSafetyTests(unittest.TestCase):
    def setUp(self):
        self.report = Report()
        self.policy = UrlPolicy(["old.test"], ["cdn.test"], {"id:7": "/tech/7/"}, self.report, 7,
                                "https://old.test/wp-content/uploads/", "https://cdn.test")

    def test_scripts_embeds_handlers_styles_and_comments_removed(self):
        result = sanitize('<p onclick="evil()" style="color:red">safe<script>secret()</script><iframe src="https://x.test">embed</iframe><!--private--></p>', self.policy)
        self.assertIn("<p>safe", result)
        self.assertIn('href="https://x.test"', result)
        self.assertNotIn("<iframe", result)
        self.assertNotIn("secret()", result)
        self.assertNotIn("onclick", result)
        self.assertNotIn("<!--", result)

    def test_lazy_images_and_srcset_only_keep_verified_media(self):
        source = '<img src="data:image/gif;base64,AAA" data-src="https://cdn.test/a.jpg" data-srcset="https://cdn.test/a.jpg 1x, https://unknown.test/a.jpg 2x" alt="sample">'
        result = sanitize(source, self.policy)
        self.assertIn('src="https://cdn.test/a.jpg"', result)
        self.assertIn('srcset="https://cdn.test/a.jpg 1x"', result)
        self.assertNotIn("unknown.test", result)
        self.assertNotIn("data-src", result)

    def test_verified_old_upload_mapping_and_external_source_link(self):
        result = sanitize('<img src="http://old.test/wp-content/uploads/2020/a.jpg"><img src="https://other.test/b.jpg" alt="External image">', self.policy)
        self.assertIn('src="https://cdn.test/wp-content/uploads/2020/a.jpg"', result)
        self.assertIn('href="https://other.test/b.jpg"', result)
        self.assertNotIn('src="https://other.test/b.jpg"', result)

    def test_markdown_javascript_links_and_emails_do_not_leak(self):
        result = sanitize('[bad](javascript:alert) ![bad](data:image/png;base64,AAA) contact@example.test <a href="mailto:contact@example.test">email</a>', self.policy)
        self.assertNotIn("javascript:", result)
        self.assertNotIn("data:image", result)
        self.assertNotIn("@", result)
        self.assertNotIn("mailto:", result)

    def test_fenced_html_code_is_not_treated_as_active_markup(self):
        source = '```html\n<script>example()</script>\n```\n\n<script>active()</script>'
        result = sanitize(source, self.policy)
        self.assertIn('<script>example()</script>', result)
        self.assertNotIn("active()", result)

    def test_broken_nesting_is_closed(self):
        self.assertEqual(sanitize("<div><b>text</div>", self.policy), "<div><b>text</b></div>")

    def test_shortcodes_are_translated_without_plugin_execution(self):
        source = '[gallery ids="1,2"] [caption id="attachment_1"]<img src="https://cdn.test/a.jpg">Caption[/caption] [audio mp3="https://cdn.test/a.mp3"][/audio] [secret]'
        result = expand_shortcodes(source, {1: {"url": "https://cdn.test/a.jpg"}}, self.policy)
        self.assertIn("legacy-gallery", result)
        self.assertIn("<figure>", result)
        self.assertIn("<audio controls", result)
        self.assertTrue(any(issue["kind"] == "missingGalleryAttachment" for issue in self.report.issues))
        self.assertTrue(any(issue["kind"] == "unresolvedShortcode" and issue["detail"] == "secret" for issue in self.report.issues))

    def test_code_examples_are_not_executed_as_shortcodes(self):
        source = '<pre><code>[gallery ids="1"] array[i]</code></pre>\n\n```text\n[player]\n```'
        result = expand_shortcodes(source, {}, self.policy)
        self.assertEqual(result, source)
        self.assertFalse(self.report.issues)

    def test_collapse_curly_quotes_preserve_title_and_body(self):
        result = expand_shortcodes('[collapse title=\u201cSpoiler\u201d]Body[/collapse]', {}, self.policy)
        self.assertIn("<details><summary>Spoiler</summary>", result)
        self.assertIn("Body", result)
        self.assertNotIn("[collapse", result)

    def test_unverified_linked_image_does_not_create_nested_anchors(self):
        result = sanitize('<a href="https://friend.test"><img src="https://other.test/avatar.jpg" alt="Friend"></a>', self.policy)
        self.assertEqual(result.count("<a "), 1)
        self.assertIn('<span class="legacy-media-source"', result)
        self.assertIn('title="https://other.test/avatar.jpg"', result)

    def test_retina_filename_is_not_mistaken_for_an_email(self):
        result = sanitize('<img src="https://cdn.test/uploads/image@2x.png"> contact@example.test', self.policy)
        self.assertIn("image@2x.png", result)
        self.assertNotIn("contact@example.test", result)

    def test_gutenberg_bare_article_embed_becomes_canonical_link(self):
        result = sanitize('<div class="wp-block-embed__wrapper">\nhttps://old.test/old-category/7/\n</div>', self.policy)
        self.assertIn('<a href="/tech/7/">', result)
        code = sanitize('<pre>https://old.test/old-category/7/</pre>', self.policy)
        self.assertNotIn("<a", code)


if __name__ == "__main__":
    unittest.main()
