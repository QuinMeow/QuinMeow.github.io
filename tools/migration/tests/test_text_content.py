import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from text_content import markdown_headings, visible_text, word_count


class TextContentTests(unittest.TestCase):
    def test_markup_and_code_do_not_pollute_description(self):
        source = "<h2>Title</h2><p>Hello <strong>world</strong>.</p><pre><code>code words</code></pre>"
        self.assertEqual(visible_text(source), "Title Hello world .")
        self.assertEqual(word_count(source), 3)

    def test_cjk_characters_count_individually_for_reading_time(self):
        self.assertEqual(word_count("<p>\u4f60\u597d Astro static-site</p>"), 4)

    def test_heading_conversion_preserves_anchor_and_code_examples(self):
        source = '<h2 id="old-anchor">A <em>heading</em></h2><pre><code>&lt;h2&gt;Example&lt;/h2&gt;</code></pre>'
        converted = markdown_headings(source)
        self.assertIn('<a id="old-anchor"></a>\n\n## A <em>heading</em>', converted)
        self.assertIn("&lt;h2&gt;Example&lt;/h2&gt;", converted)


if __name__ == "__main__":
    unittest.main()
