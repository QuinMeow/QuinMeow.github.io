import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { PAGE_SIZE } from "../src/constants/constants.ts";

const root = fileURLToPath(new URL("../", import.meta.url));
const output = join(root, process.env.JOURNAL_BUILD_DIR || "dist");
const source = join(root, "src/content/posts");
const posts = (await Promise.all((await readdir(source)).filter((name) => name.endsWith(".md")).map(async (name) => {
    const text = await readFile(join(source, name), "utf8");
    const frontmatter = text.match(/^---\r?\n([\s\S]*?)\r?\n---/)?.[1];
    assert(frontmatter, `Missing frontmatter: ${name}`);
    const field = (key) => {
        const value = frontmatter.match(new RegExp(`^${key}: (.+)$`, "m"))?.[1];
        return value === undefined ? undefined : JSON.parse(value);
    };
    return {
        id: field("wpId"),
        route: decodeURIComponent(field("originalPath")),
        published: new Date(field("published")),
        draft: field("draft"),
    };
}))).filter((post) => !post.draft).sort((a, b) => b.published - a.published);

const readPage = (number) => readFile(join(output, number === 1 ? "" : String(number), "index.html"), "utf8");
const pathname = (href) => decodeURIComponent(new URL(href, "https://journal.invalid").pathname);

function articles(html) {
    return [...html.matchAll(/<article\b[^>]*>[\s\S]*?<\/article>/g)].map(([body]) => {
        const href = body.match(/<h2\b[^>]*>\s*<a\b[^>]*href="([^"]+)"/)?.[1];
        assert(href, "Every listed article needs a linked headline");
        return { route: pathname(href), body };
    });
}

function region(html, headingId) {
    const body = html.match(new RegExp(`<section\\b[^>]*aria-labelledby="${headingId}"[^>]*>([\\s\\S]*?)<\\/section>`))?.[1];
    assert(body, `Missing accessible article region: ${headingId}`);
    return articles(body);
}

test("homepage lists every allocated post exactly once as an article", async () => {
    const entries = articles(await readPage(1));
    const expected = posts.slice(0, PAGE_SIZE).map((post) => post.route);
    assert.equal(entries.length, expected.length);
    assert.equal(new Set(entries.map((entry) => entry.route)).size, entries.length);
    assert.deepEqual(entries.map((entry) => entry.route).sort(), expected.sort());
});

test("featured and latest articles keep real headline and image destinations", async () => {
    const html = await readPage(1);
    const feature = region(html, "photo-heading")[0];
    const selected = posts.find((post) => post.id === 1896);
    assert(selected, "The selected historical photography article must exist");
    assert.equal(feature.route, selected.route);
    const latest = region(html, "latest-heading");
    const expectedLatest = posts.slice(0, PAGE_SIZE).filter((post) => post.route !== feature.route).slice(0, 2);
    assert.deepEqual(latest.map((entry) => entry.route), expectedLatest.map((post) => post.route));
    for (const entry of [feature, ...latest]) {
        const imageLinks = [...entry.body.matchAll(/<a\b[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/g)]
            .filter(([, , body]) => /<img\b/.test(body));
        assert(imageLinks.length > 0, `Expected the selected cover image: ${entry.route}`);
        for (const [, href] of imageLinks) assert.equal(pathname(href), entry.route);
    }
});

test("wp-1860 retains its Shanghai publication day", async () => {
    const post = posts.find((entry) => entry.id === 1860);
    assert(post);
    const entry = articles(await readPage(1)).find((entry) => entry.route === post.route);
    assert(entry, "The historical date regression fixture should be on page one");
    assert.equal(entry.body.match(/<time\b[^>]*datetime="([^"]+)"/)?.[1], "2021-11-08");
    assert.match(entry.body, /2021\.11\.08/);
});

test("all later pagination pages retain their complete chronological allocation", async () => {
    const allRoutes = articles(await readPage(1)).map((entry) => entry.route);
    const pageCount = Math.ceil(posts.length / PAGE_SIZE);
    for (let number = 2; number <= pageCount; number++) {
        const actual = articles(await readPage(number)).map((entry) => entry.route);
        const expected = posts.slice((number - 1) * PAGE_SIZE, number * PAGE_SIZE).map((post) => post.route);
        assert.deepEqual(actual, expected, `Incorrect allocated article set/order on page ${number}`);
        allRoutes.push(...actual);
    }
    assert.equal(allRoutes.length, posts.length);
    assert.equal(new Set(allRoutes).size, posts.length, "No post may be duplicated or omitted across pagination");
});
