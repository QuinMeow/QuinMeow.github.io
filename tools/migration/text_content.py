"""Readable metadata from legacy HTML without counting markup as prose."""

import html
import re
from html.parser import HTMLParser


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "pre", "code"}:
            self.hidden += 1
        if tag in {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "pre", "code"}:
            self.hidden = max(0, self.hidden - 1)
        self.parts.append(" ")

    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


def visible_text(source):
    source = re.sub(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$", "", source, flags=re.S | re.M)
    source = re.sub(r"(?m)^#{1,6}\s+", "", source)
    parser = VisibleText()
    parser.feed(source)
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip()


def word_count(source):
    text = visible_text(source)
    return len(re.findall(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]|[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", text))


def markdown_headings(source):
    literals = []

    def protect(match):
        literals.append(match[0])
        return f"MIGRATION_HEADING_LITERAL_{len(literals)-1}_END"

    source = re.sub(r"<pre\b[^>]*>.*?</pre>|<code\b[^>]*>.*?</code>|^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$", protect, source, flags=re.S | re.M | re.I)

    def heading(match):
        text = re.sub(r"\s+", " ", match[3]).strip()
        identity = re.search(r'\bid="([^"]+)"', match[2])
        anchor = f'<a id="{html.escape(html.unescape(identity[1]), quote=True)}"></a>\n\n' if identity else ""
        return "\n\n" + anchor + "#" * int(match[1]) + " " + text + "\n\n"

    source = re.sub(r"<h([1-6])\b([^>]*)>(.*?)</h\1>", heading, source, flags=re.S | re.I)
    for index in reversed(range(len(literals))):
        source = source.replace(f"MIGRATION_HEADING_LITERAL_{index}_END", literals[index])
    return source
