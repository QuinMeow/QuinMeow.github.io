"""Offline acceptance checks; this does not claim live CDN availability."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from html_safety import redact_emails
from policy import Report


def audit(report_path, posts_dir, pages_dir):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    files = set()
    ids, paths = set(), set()
    media = Counter()
    post_count = page_count = 0
    for route in report["routes"]:
        wp_id, path = route["wpId"], route["path"]
        if wp_id in ids or path in paths:
            raise ValueError("Duplicate route or WordPress ID in public manifest")
        ids.add(wp_id)
        paths.add(path)
        folder = posts_dir if route["type"] == "post" else pages_dir
        if not re.fullmatch(r"wp-\d+\.md", route["file"]):
            raise ValueError("Unsafe generated filename in manifest")
        filename = folder / route["file"]
        content = filename.read_text(encoding="utf-8")
        files.add(filename.resolve())
        if not content.startswith("---\n"):
            raise ValueError(f"Missing frontmatter: {filename.name}")
        frontmatter, body = content[4:].split("\n---\n", 1)
        metadata = dict(line.split(": ", 1) for line in frontmatter.splitlines())
        if json.loads(metadata["wpId"]) != wp_id or json.loads(metadata["originalPath"]) != path:
            raise ValueError(f"Manifest mismatch: {filename.name}")
        if json.loads(metadata["draft"]) is not False:
            raise ValueError("Draft unexpectedly exported")
        if redact_emails(content, Report()) != content:
            raise ValueError(f"Email unexpectedly exported: {filename.name}")
        inert_removed = re.sub(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$", "", body, flags=re.S | re.M)
        if re.search(r"<(?:script|iframe|object|embed|form)\b|\son[a-z]+\s*=|<!--", inert_removed, re.I):
            raise ValueError(f"Executable or commented HTML survived: {filename.name}")
        for url in re.findall(r'<(?:img|audio|video|source)\b[^>]*\bsrc="([^"]+)"', body):
            media[urlsplit(url).hostname or "relative"] += 1
        if route["type"] == "post":
            post_count += 1
        else:
            page_count += 1
    actual_files = {p.resolve() for folder in (posts_dir, pages_dir) for p in folder.glob("*.md")}
    if actual_files != files:
        raise ValueError("Generated content files do not exactly match the route manifest")
    if report["counts"].get("convertedPosts", 0) != post_count or report["counts"].get("convertedPages", 0) != page_count:
        raise ValueError("Acceptance count mismatch")
    if report.get("sourceSelection", {}).get("commentsExported", 0):
        raise ValueError("Source exporter unexpectedly included comments")
    return {"posts": post_count, "pages": page_count, "uniqueRoutes": len(paths), "inlineMediaByHost": dict(media),
            "issuesByKind": dict(Counter(issue["kind"] for issue in report["issues"])), "networkVerified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("docs/migration-report.json"))
    parser.add_argument("--posts", type=Path, default=Path("src/content/posts"))
    parser.add_argument("--pages", type=Path, default=Path("src/content/legacy-pages"))
    args = parser.parse_args()
    print(json.dumps(audit(args.report, args.posts, args.pages), ensure_ascii=False, indent=2))
