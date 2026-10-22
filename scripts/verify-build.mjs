import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";
import { resolve, join, sep } from "node:path";

const output = resolve(process.argv[2] || "dist");
const publicationOrigin = new URL(process.env.SITE_URL || "https://quinmeow.github.io/").origin;
const report = JSON.parse(await readFile("docs/migration-report.json", "utf8"));
const routes = new Set();
const ids = new Set();

for (const route of report.routes) {
  assert(!routes.has(route.path), `Duplicate path: ${route.path}`);
  assert(!ids.has(route.wpId), `Duplicate ID: ${route.wpId}`);
  assert(!route.path.includes("/r18/"), "Excluded adult route in manifest");
  routes.add(route.path);
  ids.add(route.wpId);
  const file = resolve(output, "." + decodeURIComponent(route.path), "index.html");
  assert(file.startsWith(output + sep), "Route escapes output directory");
  const html = await readFile(file, "utf8");
  assert(html.includes("<h1"), `Missing article heading: ${route.path}`);
  assert(html.includes(publicationOrigin), `Missing publication origin: ${route.path}`);
  assert(!/giscus|disqus|wp-comments-post\.php|comment_author_email/i.test(html), `Comment system in ${route.path}`);
  assert(!/localhost:\d+|127\.0\.0\.1:\d+/.test(html), `Local URL leaked: ${route.path}`);
}

for (const file of ["index.html", "archive/index.html", "about/index.html", "友情链接/index.html", "rss.xml", "sitemap-index.xml", "robots.txt", "404.html", "pagefind/pagefind.js"]) {
  assert((await stat(join(output, file))).size > 0, `Missing built file: ${file}`);
}
const feed = await readFile(join(output, "rss.xml"), "utf8");
assert.equal((feed.match(/<item>/g) || []).length, report.counts.convertedPosts, "RSS count mismatch");
assert.equal(routes.size, report.counts.convertedPosts + report.counts.convertedPages);
console.log(`Verified ${routes.size} preserved article/page URLs, RSS, search assets, archive, 404 and privacy boundaries.`);
