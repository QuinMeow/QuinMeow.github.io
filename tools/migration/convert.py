"""Convert an allowlisted, sanitized WordPress JSON export to Fuwari content."""

import argparse
import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from html_safety import redact_emails, sanitize
from policy import Report, UrlPolicy, excluded_terms, original_path, select_posts
from shortcodes import expand_shortcodes
from text_content import markdown_headings, visible_text, word_count


def plain(value):
    return html.unescape(re.sub(r"<[^>]*>", "", value or "")).strip()


def published_date(post, site):
    value = post.get("date", "").replace(" ", "T")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        gmt = post.get("date_gmt", "")
        delta = None
        if gmt and not gmt.startswith("0000"):
            try:
                delta = parsed - datetime.fromisoformat(gmt.replace(" ", "T"))
            except ValueError:
                pass
        if delta is not None and -12 * 3600 <= delta.total_seconds() <= 14 * 3600 and delta.total_seconds() % 900 == 0:
            parsed = parsed.replace(tzinfo=timezone(delta))
        elif site.get("timezone"):
            parsed = parsed.replace(tzinfo=ZoneInfo(site["timezone"]))
        else:
            offset = site.get("utc_offset_hours")
            if offset is None:
                raise ValueError("An explicit site timezone is required for local WordPress dates")
            parsed = parsed.replace(tzinfo=timezone(timedelta(hours=float(offset))))
    return parsed.isoformat(timespec="seconds")


def frontmatter(post, terms, site, report):
    selected = [terms[int(key)] for key in post.get("term_ids", []) if int(key) in terms]
    categories = [term["name"] for term in selected if term["taxonomy"] == "category"]
    tags = [term["name"] for term in selected if term["taxonomy"] == "post_tag"]
    clean = lambda value: redact_emails(plain(value), report)
    return {
        "title": clean(post["title"]), "published": published_date(post, site),
        "description": clean(post.get("excerpt", ""))[:240], "image": "", "tags": [clean(tag) for tag in tags],
        "category": clean(categories[0]) if categories else "", "draft": False, "lang": "zh_CN",
        "slug": original_path(post).strip("/"), "wpId": int(post["id"]), "originalPath": original_path(post),
        "wpTimezone": site.get("timezone", ""), "wpType": post["type"], "wpCategories": [clean(c) for c in categories],
    }


def serialize_frontmatter(values):
    # JSON values are valid YAML scalars and avoid fragile manual quoting.
    return "---\n" + "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in values.items()) + "\n---\n\n"


def convert_export(data, output, report_path, site_hosts, media_hosts, blocked_slugs, pages_output=None, blocked_tags=("h",), verified_media=None, unavailable_media=None, recovered_media=None):
    if data.get("schema_version") != 1:
        raise ValueError("Expected sanitized WordPress export schema_version 1")
    if not media_hosts:
        raise ValueError("At least one explicitly verified media host is required")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be empty; refusing to overwrite or mix previous content")
    pages_output = pages_output or output.parent / "legacy-pages"
    if pages_output.exists() and any(pages_output.iterdir()):
        raise ValueError("Pages output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    pages_output.mkdir(parents=True, exist_ok=True)
    report = Report()
    terms = {int(term["id"]): term for term in data["terms"]}
    blocked = excluded_terms(list(terms.values()), set(blocked_slugs), set(blocked_tags))
    if not blocked:
        raise ValueError("No adult-resource category matched the exclusion policy; refusing an unchecked export")
    posts = select_posts(data["posts"], blocked, report)
    expected = data.get("export_summary", {}).get("public_exported")
    if expected is not None and int(expected) != len(data["posts"]):
        raise ValueError("Source export count does not match its declared public_exported count")
    if len({int(post["id"]) for post in posts}) != len(posts):
        raise ValueError("Duplicate WordPress post ID")
    routes = {}
    for post in posts:
        path = original_path(post)
        if path in routes:
            raise ValueError(f"Duplicate permalink: {path}")
        routes[path] = path
        routes[path.rstrip("/")] = path
        routes[f"id:{post['id']}"] = path
    attachments = {int(item["id"]): item for item in data.get("attachments", [])}
    manifest = []
    for post in posts:
        policy = UrlPolicy(site_hosts, media_hosts, routes, report, int(post["id"]), data["site"].get("upload_base_url", ""), data["site"].get("cdn_base_url", ""), verified_media, unavailable_media, recovered_media)
        body = expand_shortcodes(post["content"], attachments, policy)
        body = markdown_headings(sanitize(body, policy)).strip()
        metadata = frontmatter(post, terms, data["site"], report)
        metadata["description"] = metadata["description"] or redact_emails(visible_text(body), report)[:180]
        metadata["wordCount"] = word_count(body)
        thumbnail = attachments.get(int(post.get("thumbnail_id", 0)))
        if thumbnail:
            metadata["image"] = policy.url(thumbnail["url"], media=True) or ""
        if not metadata["image"]:
            first_image = re.search(r'<img\b[^>]*\bsrc="([^"]+)"', body)
            if first_image:
                metadata["image"] = html.unescape(first_image[1])
        filename = f"wp-{int(post['id'])}.md"
        destination = output if post["type"] == "post" else pages_output
        (destination / filename).write_text(serialize_frontmatter(metadata) + body + "\n", encoding="utf-8", newline="\n")
        manifest.append({"wpId": int(post["id"]), "path": original_path(post), "file": filename, "type": post["type"]})
        report.count("convertedPosts" if post["type"] == "post" else "convertedPages")
    result = {
        "schemaVersion": 1, "policy": {"excludedCategorySlugs": sorted(blocked_slugs), "excludedTagSlugs": sorted(blocked_tags), "comments": "omitted", "mediaHosts": sorted(media_hosts), "unavailableMediaUrls": sorted(unavailable_media or []), "recoveredMedia": recovered_media or {}},
        "counts": report.counts, "issues": report.issues, "routes": manifest,
    }
    if "export_summary" in data:
        summary = data["export_summary"]
        result["sourceSelection"] = {"publicExported": int(summary["public_exported"]), "commentsExported": int(summary.get("comments_exported", 0)),
                                     "blockedCategoryIds": list(map(int, summary.get("blocked_category_ids", []))), "blockedTagIds": list(map(int, summary.get("blocked_tag_ids", [])))}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Private sanitized export outside the public repository")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--pages-output", type=Path)
    parser.add_argument("--media-allowlist", type=Path, help="Exact historical URL-to-verified-HTTPS-URL map")
    parser.add_argument("--unavailable-media", type=Path, help="Exact public URLs confirmed unavailable at both CDN and origin")
    parser.add_argument("--recovered-media", type=Path, help="Exact original URL to verified recovered local asset map")
    parser.add_argument("--site-host", action="append", required=True)
    parser.add_argument("--media-host", action="append", required=True)
    parser.add_argument("--exclude-category", action="append", default=["r18"])
    parser.add_argument("--exclude-tag", action="append", default=["h"])
    args = parser.parse_args()
    data = json.loads(args.source.read_text(encoding="utf-8-sig"))
    allowlist = json.loads(args.media_allowlist.read_text(encoding="utf-8")) if args.media_allowlist else {}
    unavailable = json.loads(args.unavailable_media.read_text(encoding="utf-8")) if args.unavailable_media else []
    recovered = json.loads(args.recovered_media.read_text(encoding="utf-8")) if args.recovered_media else {}
    result = convert_export(data, args.output, args.report, args.site_host, args.media_host, args.exclude_category, args.pages_output, args.exclude_tag, allowlist, unavailable, recovered)
    print(json.dumps({"counts": result["counts"], "issueCount": len(result["issues"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
