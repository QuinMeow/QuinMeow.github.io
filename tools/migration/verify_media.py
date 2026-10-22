"""Check historical media URLs without downloading or storing media files."""

import argparse
import html
import json
import ssl
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen


class MediaUrls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = set()

    def handle_starttag(self, tag, attrs):
        if tag not in {"img", "audio", "video", "source"}:
            return
        values = dict(attrs)
        for key in ("src", "data-src", "data-lazy-src", "data-original", "poster"):
            if values.get(key):
                self.urls.add(html.unescape(values[key]))
        for key in ("srcset", "data-srcset", "data-lazy-srcset"):
            for entry in values.get(key, "").split(","):
                if entry.strip():
                    self.urls.add(html.unescape(entry.strip().split()[0]))


def verify(url, timeout=7):
    parsed = urlsplit(url)
    candidate = urlunsplit(parsed._replace(scheme="https", path=quote(parsed.path, safe="/%:@"), query=quote(parsed.query, safe="=&%/:?+@")))
    result = {"source": url, "checked": candidate, "verified": False}
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BlogMigrationCheck/1.0)", "Range": "bytes=0-0"}
    for method in ("HEAD", "GET"):
        try:
            with urlopen(Request(candidate, headers=headers, method=method), timeout=timeout, context=ssl.create_default_context()) as response:
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                result.update(status=response.status, contentType=content_type, finalUrl=response.url)
                if method == "GET":
                    response.read(1)
                result["verified"] = response.status in {200, 206} and content_type.startswith(("image/", "audio/", "video/")) and urlsplit(response.url).scheme == "https"
                if result["verified"]:
                    return result
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            result["error"] = str(error)[:220]
            if isinstance(error, HTTPError):
                result["status"] = error.code
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allowlist", type=Path, required=True)
    parser.add_argument("--skip-host", action="append", default=[])
    args = parser.parse_args()
    data = json.loads(args.source.read_text(encoding="utf-8-sig"))
    collector = MediaUrls()
    for post in data["posts"]:
        collector.feed(post["content"])
    urls = []
    for url in sorted(collector.urls):
        parsed = urlsplit(url)
        if parsed.scheme in {"http", "https", ""} and parsed.hostname and parsed.hostname not in args.skip_host:
            urls.append(url if parsed.scheme else "https:" + url)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(verify, urls))
    allowlist = {result["source"]: result["checked"] for result in results if result["verified"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.allowlist.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"httpsOnly": True, "mediaFilesStored": False, "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.allowlist.write_text(json.dumps(allowlist, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"checked": len(results), "verified": len(allowlist), "failed": len(results) - len(allowlist), "mediaFilesStored": False}))


if __name__ == "__main__":
    main()
