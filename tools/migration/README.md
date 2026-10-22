# WordPress Static Migration

This tooling is a one-time, read-only source export and an offline conversion
pipeline. The static site never calls WordPress or its database at build time.
Use Python 3.11+ with timezone data available for `zoneinfo`.

## Privacy Boundary

- `export.php` runs through SSH stdin; database credentials stay on the old server.
- Only published, unprotected posts/pages are selected. The `r18` category and its
  descendants, plus the adult marker tag `h`, are excluded before export.
- Non-adult resources in `source-share` remain eligible.
- No users, comments, database options dump, credentials, or excluded article
  titles/bodies are exported. Small allowlisted site settings are retained.
- Keep the sanitized JSON and network diagnostic report in the ignored
  `.migration-data/` directory. Never commit a database dump or `wp-config.php`.
- Public output contains reviewed Markdown/HTML, safe metadata, legacy routes,
  and a migration issue report. Contact emails are redacted; URL filenames such
  as `image@2x.png` are not mistaken for contact addresses.

## Input Contract

The JSON root has `schema_version: 1`, `site`, `terms`, `posts`, `attachments`,
and `export_summary`.

- `site`: `base_url`, `timezone`, `utc_offset_hours`, `upload_base_url`,
  `cdn_base_url`.
- `terms`: objects containing numeric `id`/`parent`, `taxonomy`, `name`, `slug`.
  Retain blocked category/tag identifiers even when all matching articles have
  been removed, so the converter can independently enforce the policy.
- `posts`: numeric `id`, `type`, `status`, empty `password`, `title`, `content`,
  `excerpt`, local `date`, `date_gmt`, absolute public `link`, `term_ids`, and
  optional `thumbnail_id`.
- `attachments`: numeric `id`, original `url`; optional `alt`, `file`, `mime`.
- `export_summary`: `public_exported`, `comments_exported: 0`,
  `blocked_category_ids`, `blocked_tag_ids`; counts only, no excluded content.

Dates use the valid local/GMT timestamp difference first, the named timezone
second, and an explicit numeric offset last. A stale WordPress `gmt_offset`
therefore does not turn Shanghai timestamps into UTC.

## Convert

Run from the repository root. Output directories must be empty; the converter
never silently overwrites user content. Remove only known generated `wp-ID.md`
files before an intentional regeneration.

```powershell
python tools/migration/convert.py .migration-data/wordpress-public.json `
  --output src/content/posts `
  --pages-output src/content/legacy-pages `
  --report docs/migration-report.json `
  --site-host blog.dalaoweb.top `
  --media-host cdn.dalaoweb.top `
  --media-allowlist tools/migration/verified-media.json
```

Filenames are stable WordPress IDs. Frontmatter `slug` and `originalPath`
preserve the old category hierarchy and numeric permalink. Pages live in their
own collection and do not appear as blog posts. Metadata includes the original
ID/type/timezone/categories, a visible-prose excerpt, and a markup-free
`wordCount`. Comments have no destination collection or UI.

## Media And Legacy Markup

Only the explicitly configured old uploads prefix maps to the existing CDN,
keeping the original path/query. Other hostnames are never guessed. Scripts,
event handlers, styles, unreviewed iframes, and HTML comments are removed;
iframes become ordinary source links. Code examples remain inert.

Gallery, caption, audio/video, collapse, and code shortcodes have small explicit
translations. Plugin-only music players with no exported media URL have a
readable unavailable notice and a report entry. Unknown shortcodes are reported.
Historical external images without successful verification become source links
or source-URL-labelled text, not silently deleted content.

The checked-in `verified-media.json` is an exact-URL allowlist, not blanket trust
for an entire hostname. Refresh it with strict HTTPS checks:

```powershell
python tools/migration/verify_media.py .migration-data/wordpress-public.json `
  --output .migration-data/media-checks.json `
  --allowlist tools/migration/verified-media.json `
  --skip-host cdn.dalaoweb.top --skip-host blog.dalaoweb.top
```

The verifier requests headers, then reads at most one response byte when a GET
fallback is needed. It stores no media files. Historical HTTP URLs are upgraded
only after their exact HTTPS counterpart succeeds. A failed probe can reflect
TLS, DNS, hotlink protection, or a removed file; it is not proof of deletion.

## Offline Acceptance

```powershell
python -m unittest discover -s tools/migration/tests -v
python tools/migration/audit.py
```

The audit checks one-to-one files/routes/IDs, publication flags, source/converted
counts, literal email removal, executable HTML removal, and inline-media hosts.
Its `networkVerified: false` deliberately distinguishes structural acceptance
from live CDN/certificate verification and browser visual QA.
