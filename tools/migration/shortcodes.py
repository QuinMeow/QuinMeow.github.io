"""Small, auditable WordPress shortcode translations; no plugin execution."""

import html
import re


ATTR = re.compile(r"([\w-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s]+))")


def attributes(source):
    source = source.translate(str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'"}))
    return {m[1].lower(): next(value for value in m.groups()[1:] if value is not None) for m in ATTR.finditer(source)}


def expand_shortcodes(source, attachments, policy):
    report, post_id = policy.report, policy.post_id
    literals = []

    def protect(match):
        literals.append(match[0])
        return f"MIGRATION_LITERAL_{len(literals) - 1}_END"

    source = re.sub(r"<pre\b[^>]*>.*?</pre>|<code\b[^>]*>.*?</code>|^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$", protect, source, flags=re.S | re.M | re.I)

    def code(match):
        attrs = attributes(match[2])
        language = attrs.get("language", attrs.get("lang", ""))
        language = re.sub(r"[^\w+-]", "", language)
        body = html.unescape(match[3]).strip("\r\n")
        fence = "`" * max(3, max((len(m[0]) + 1 for m in re.finditer(r"`+", body)), default=3))
        report.count("codeShortcodes")
        return f"\n\n{fence}{language}\n{body}\n{fence}\n\n"

    source = re.sub(r"\[(code|sourcecode)([^\]]*)\](.*?)\[/\1\]", code, source, flags=re.S | re.I)
    source = re.sub(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$", protect, source, flags=re.S | re.M)

    def collapse(match):
        title = html.escape(attributes(match[1]).get("title", "Details"))
        report.count("collapseShortcodes")
        return f"\n\n<details><summary>{title}</summary>\n\n{match[2]}\n\n</details>\n\n"

    source = re.sub(r"\[collapse([^\]]*)\](.*?)\[/collapse\]", collapse, source, flags=re.S | re.I)

    def caption(match):
        content = match[2].strip()
        report.count("captionShortcodes")
        return f"\n\n<figure>{content}</figure>\n\n"

    source = re.sub(r"\[caption([^\]]*)\](.*?)\[/caption\]", caption, source, flags=re.S | re.I)

    def gallery(match):
        attrs = attributes(match[1])
        images = []
        for item in attrs.get("ids", "").split(","):
            if not item.strip().isdigit():
                continue
            attachment = attachments.get(int(item.strip()))
            if not attachment:
                report.issue(post_id, "missingGalleryAttachment", item.strip())
                continue
            url = policy.url(attachment["url"], media=True)
            if url:
                alt = html.escape(attachment.get("alt", ""), quote=True)
                images.append(f'<img src="{html.escape(url, quote=True)}" alt="{alt}" loading="lazy">')
            elif (fallback := policy.url(attachment["url"])):
                images.append(f'<a href="{html.escape(fallback, quote=True)}">Original gallery image source</a>')
        if not images:
            report.issue(post_id, "emptyGallery")
        report.count("galleryShortcodes")
        return "\n\n<div class=\"legacy-gallery\">" + "\n".join(images) + "</div>\n\n"

    source = re.sub(r"\[gallery([^\]]*)\]", gallery, source, flags=re.I)

    def media(match):
        tag, attrs = match[1].lower(), attributes(match[2])
        candidates = [attrs[key] for key in ("src", "mp3", "m4a", "ogg", "wav", "mp4", "webm") if attrs.get(key)]
        url = next((safe for candidate in candidates if (safe := policy.url(candidate, media=True))), None)
        if not url:
            report.issue(post_id, "unresolvedMediaShortcode", tag)
            fallback = next((safe for candidate in candidates if (safe := policy.url(candidate))), None)
            return f'<a href="{html.escape(fallback, quote=True)}">Original {tag} source</a>' if fallback else ""
        report.count("mediaShortcodes")
        return f'\n\n<{tag} controls preload="none" src="{html.escape(url, quote=True)}"></{tag}>\n\n'

    source = re.sub(r"\[(audio|video)([^\]]*)\](?:\s*\[/\1\])?", media, source, flags=re.I)

    def embed(match):
        value = match[1].strip()
        url = policy.url(value)
        report.count("embedsConvertedToLinks")
        return f'\n\n<a href="{html.escape(url, quote=True)}">{html.escape(value)}</a>\n\n' if url else ""

    source = re.sub(r"\[embed\](.*?)\[/embed\]", embed, source, flags=re.S | re.I)

    def player(match):
        report.issue(post_id, "unresolvedPlayer", "legacyWordPressMusicPlugin")
        return '<p class="legacy-note">Legacy music player unavailable; the original WordPress plugin was not migrated.</p>'

    source = re.sub(r"\[player(?:\s+[^\]]*)?\]", player, source, flags=re.I)
    for match in re.finditer(r"\[/?([A-Za-z_][\w:-]*)(?:\s+[^\]\n]*)?\]", source):
        report.issue(post_id, "unresolvedShortcode", match[1])
    for index in reversed(range(len(literals))):
        source = source.replace(f"MIGRATION_LITERAL_{index}_END", literals[index])
    return source
