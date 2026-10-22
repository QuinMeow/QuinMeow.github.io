"""Strict public-content selection and legacy URL policy."""

from dataclasses import dataclass, field
import re
from urllib.parse import urlsplit, urlunsplit


@dataclass
class Report:
    counts: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)

    def count(self, name, amount=1):
        self.counts[name] = self.counts.get(name, 0) + amount

    def issue(self, post_id, kind, detail=""):
        self.issues.append({"wpId": post_id, "kind": kind, "detail": detail})


def excluded_terms(terms, blocked_slugs, blocked_tags=()):
    """Resolve the entire blocked category subtree before selecting posts."""
    categories = {int(t["id"]): t for t in terms if t["taxonomy"] == "category"}
    blocked = {key for key, term in categories.items() if term["slug"] in blocked_slugs}
    while True:
        children = {key for key, term in categories.items() if int(term.get("parent", 0)) in blocked}
        expanded = blocked | children
        if expanded == blocked:
            return blocked | {int(t["id"]) for t in terms if t["taxonomy"] == "post_tag" and t["slug"] in blocked_tags}
        blocked = expanded


def select_posts(posts, blocked, report):
    selected = []
    for post in posts:
        report.count("sourcePosts")
        reason = None
        if post.get("type") not in {"post", "page"}:
            reason = "unsupportedType"
        elif post.get("status") != "publish":
            reason = "notPublished"
        elif post.get("password"):
            reason = "passwordProtected"
        elif blocked.intersection(map(int, post.get("term_ids", []))):
            reason = "excludedCategory"
        if reason:
            report.count(reason)
        else:
            selected.append(post)
    return selected


class UrlPolicy:
    def __init__(self, site_hosts, media_hosts, routes, report, post_id, upload_base_url="", cdn_base_url="", verified_media=None):
        self.site_hosts = {host.lower() for host in site_hosts}
        self.media_hosts = {host.lower() for host in media_hosts}
        self.routes = routes
        self.report = report
        self.post_id = post_id
        self.upload_base = urlsplit(upload_base_url)
        self.cdn_base = urlsplit(cdn_base_url)
        self.verified_media = verified_media or {}

    def url(self, value, media=False):
        value = value.strip()
        if not value:
            return None
        parsed = urlsplit(value)
        if parsed.username or parsed.password:
            self.report.issue(self.post_id, "credentialUrl")
            return None
        mapped_upload = (self.upload_base.hostname and self.cdn_base.hostname in self.media_hosts
                         and parsed.hostname == self.upload_base.hostname and parsed.path.startswith(self.upload_base.path))
        if mapped_upload:
            parsed = parsed._replace(scheme=self.cdn_base.scheme, netloc=self.cdn_base.netloc)
            value = urlunsplit(parsed)
            self.report.count("mappedUploadUrls")
        if media:
            verified = self.verified_media.get(value)
            if verified and urlsplit(verified).scheme == "https":
                self.report.count("verifiedHistoricalMediaUrls")
                return verified
            if parsed.scheme not in {"http", "https", ""} or parsed.hostname not in self.media_hosts:
                self.report.issue(self.post_id, "unverifiedMediaHost", parsed.hostname or "relative")
                return None
            # Keep the exact verified CDN host/path; do not invent upload mappings.
            return value if parsed.scheme else "https:" + value
        if parsed.scheme and parsed.scheme not in {"http", "https"}:
            self.report.count("removedUnsafeLinks")
            return None
        if parsed.hostname in self.site_hosts or (not parsed.netloc and parsed.path.startswith("/")):
            query_match = re.search(r"(?:^|&)p=(\d+)(?=[^\d]|$)", parsed.query)
            query_id = query_match[1] if query_match else None
            target = self.routes.get(f"id:{query_id}") if query_id else None
            target = target or self.routes.get(parsed.path)
            legacy_id = re.search(r"/(\d+)/?$", parsed.path)
            target = target or (self.routes.get(f"id:{legacy_id[1]}") if legacy_id else None)
            if parsed.path == "/" and not parsed.query:
                target = "/"
            if target:
                return urlunsplit(("", "", target, "", parsed.fragment))
            if parsed.path.startswith("/wp-"):
                self.report.issue(self.post_id, "legacySystemLink", parsed.path)
                return None
            self.report.issue(self.post_id, "unresolvedInternalLink", parsed.path)
        return value


def original_path(post):
    path = urlsplit(post["link"]).path
    if not path.startswith("/") or path in {"/", ""} or ".." in path.split("/"):
        raise ValueError(f"Post {post['id']} has an invalid public permalink")
    return path.rstrip("/") + "/"
