"""Allowlisted legacy HTML with explicit media-host validation."""

import html
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit


ALLOWED = set("a abbr b blockquote br caption cite code col colgroup dd del details div dl dt em figcaption figure h1 h2 h3 h4 h5 h6 hr i img kbd li mark ol p pre q s samp section small source span strong sub summary sup table tbody td th thead time tr u ul video audio".split())
VOID = {"br", "col", "hr", "img", "source"}
DROP_CONTENT = {"script", "style", "iframe", "object", "embed", "form", "textarea", "button", "svg", "math", "template", "noscript"}
GLOBAL_ATTRS = {"class", "id", "title", "lang", "dir"}
ELEMENT_ATTRS = {
    "a": {"href", "rel"}, "img": {"src", "alt", "width", "height", "srcset", "sizes", "loading", "decoding"},
    "audio": {"src", "controls", "preload", "loop"}, "video": {"src", "poster", "controls", "preload", "width", "height", "loop", "muted"},
    "source": {"src", "srcset", "type", "media", "sizes"}, "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan", "scope"},
    "ol": {"start", "reversed"}, "li": {"value"}, "time": {"datetime"}, "col": {"span"}, "colgroup": {"span"},
}
EMAIL = re.compile(r"(?<![/\w.-])[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![\w.-])")
HTTP_URL = re.compile(r"https?://[^\s<>\"']+", re.I)
UNAVAILABLE_LABEL = "\u5386\u53f2\u56fe\u7247\u6682\u4e0d\u53ef\u7528\uff0c\u67e5\u770b\u539f\u59cb\u94fe\u63a5"


def redact_emails(value, report):
    urls = []

    def protect_url(match):
        candidate = match[0]
        try:
            parsed = urlsplit(html.unescape(candidate))
        except ValueError:
            return candidate
        if parsed.username or parsed.password:
            report.count("removedCredentialUrls")
            return "[sensitive URL removed]"
        if not parsed.hostname:
            return candidate
        urls.append(candidate)
        return f"MIGRATION_PUBLIC_URL_{len(urls)-1}_END"

    # Public object filenames may contain multiple @ separators and resemble
    # email addresses. Redact prose, never rewrite an already-safe media path.
    value = HTTP_URL.sub(protect_url, value)
    value, count = EMAIL.subn("[email removed]", value)
    report.count("redactedEmails", count)
    for index, url in enumerate(urls):
        value = value.replace(f"MIGRATION_PUBLIC_URL_{index}_END", url)
    return value


class Sanitizer(HTMLParser):
    def __init__(self, policy):
        super().__init__(convert_charrefs=False)
        self.policy = policy
        self.parts = []
        self.dropped = []
        self.opened = []

    def srcset(self, value):
        entries = []
        for entry in value.split(","):
            tokens = entry.strip().split()
            if not tokens:
                continue
            url = self.policy.url(tokens[0], media=True)
            if not url:
                continue
            descriptor = tokens[1] if len(tokens) == 2 and re.fullmatch(r"\d+(?:\.\d+)?[wx]", tokens[1]) else ""
            entries.append(url + (" " + descriptor if descriptor else ""))
        return ", ".join(entries) or None

    def handle_starttag(self, tag, attrs):
        if self.dropped:
            if tag in DROP_CONTENT:
                self.dropped.append(tag)
            return
        if tag in DROP_CONTENT:
            if tag == "iframe":
                fallback = self.policy.url(dict(attrs).get("src", ""))
                if fallback:
                    self.parts.append(f'<a class="legacy-embed-source" href="{html.escape(fallback, quote=True)}">Original embedded content</a>')
            self.dropped.append(tag)
            self.policy.report.count("removedExecutableElements")
            return
        if tag not in ALLOWED:
            return
        values = dict(attrs)
        if tag == "img":
            lazy_src = next((values.get(key) for key in ("data-src", "data-lazy-src", "data-original", "data-actualsrc") if values.get(key)), None)
            if lazy_src:
                values["src"] = lazy_src
            lazy_set = values.get("data-srcset") or values.get("data-lazy-srcset")
            if lazy_set:
                values["srcset"] = lazy_set
            values["loading"] = "lazy"
            values["decoding"] = "async"
        accepted = []
        for key, value in values.items():
            if key not in GLOBAL_ATTRS | ELEMENT_ATTRS.get(tag, set()):
                continue
            if key in {"src", "poster"}:
                value = self.policy.url(value or "", media=True)
            elif key == "href":
                value = self.policy.url(value or "")
            elif key == "srcset":
                value = self.srcset(value or "")
            elif key in {"width", "height", "colspan", "rowspan", "span"}:
                value = value if value and value.isdigit() else None
            if value is None and key not in {"controls", "loop", "muted", "reversed"}:
                continue
            accepted.append(f' {key}' if value is None else f' {key}="{html.escape(value, quote=True)}"')
        if tag == "img" and not any(attr.startswith(" src=") for attr in accepted):
            fallback = self.policy.url(values.get("src", ""))
            known_missing = bool(fallback and self.policy.is_unavailable(fallback))
            if not known_missing:
                self.policy.report.issue(self.policy.post_id, "removedUnverifiedImage")
            if fallback:
                label = UNAVAILABLE_LABEL if known_missing else values.get("alt") or "Original image source"
                if "a" in self.opened:
                    self.parts.append(f'<span class="legacy-media-source" title="{html.escape(fallback, quote=True)}">{html.escape(label)}</span>')
                else:
                    self.parts.append(f'<a class="legacy-media-source" href="{html.escape(fallback, quote=True)}">{html.escape(label)}</a>')
            return
        self.parts.append("<" + tag + "".join(accepted) + ">")
        if tag not in VOID:
            self.opened.append(tag)

    def handle_endtag(self, tag):
        if self.dropped:
            if tag == self.dropped[-1]:
                self.dropped.pop()
            return
        if tag not in self.opened:
            return
        # Close intervening tags to avoid raw HTML swallowing the rest of a post.
        while self.opened:
            closing = self.opened.pop()
            self.parts.append(f"</{closing}>")
            if closing == tag:
                break

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if not self.dropped:
            bare = data.strip()
            if not {"a", "pre", "code"}.intersection(self.opened) and not re.search(r"\s", bare):
                parsed = urlsplit(bare)
                if parsed.hostname in self.policy.site_hosts:
                    rewritten = self.policy.url(bare)
                    if rewritten and rewritten != bare:
                        anchor = f'<a href="{html.escape(rewritten, quote=True)}">{html.escape(bare)}</a>'
                        self.parts.append(data.replace(bare, anchor))
                        self.policy.report.count("rewrittenBareInternalLinks")
                        return
            self.parts.append(data)

    def handle_entityref(self, name):
        if not self.dropped:
            self.parts.append(f"&{name};")

    def handle_charref(self, name):
        if not self.dropped:
            self.parts.append(f"&#{name};")

    def result(self):
        return "".join(self.parts) + "".join(f"</{tag}>" for tag in reversed(self.opened))


def sanitize(source, policy):
    parts = []
    # Leave fenced examples inert and intact; sanitize only rendered HTML/Markdown.
    chunks = re.split(r"(^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\2[ \t]*$)", source, flags=re.M | re.S)
    for index in range(0, len(chunks), 3):
        raw = chunks[index]

        def markdown_link(match):
            media, label, target = match.groups()
            target = target.strip().split(' "', 1)[0].strip("<>")
            safe = policy.url(target, media=bool(media))
            if not safe:
                fallback = policy.url(target) if media else None
                if fallback:
                    text = UNAVAILABLE_LABEL if policy.is_unavailable(fallback) else label or "Original image source"
                    return f'<a href="{html.escape(fallback, quote=True)}">{html.escape(text)}</a>'
                return label
            tag = f'<img src="{html.escape(safe, quote=True)}" alt="{html.escape(label, quote=True)}">' if media else f'<a href="{html.escape(safe, quote=True)}">{html.escape(label)}</a>'
            return tag

        raw = re.sub(r"(!?)\[([^\]\n]*)\]\(([^)\n]*)\)", markdown_link, raw)
        raw = re.sub(r"(?m)^\s*\[[^\]\n]+\]:\s*(?:javascript|data|vbscript):[^\n]*$", "", raw, flags=re.I)
        parser = Sanitizer(policy)
        parser.feed(raw)
        parser.close()
        parts.append(parser.result())
        if index + 1 < len(chunks):
            parts.append(chunks[index + 1])
    return redact_emails("".join(parts), policy.report)
