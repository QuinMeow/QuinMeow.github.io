# Build Security Boundary

Review date: 2026-10-22. This site emits static HTML/CSS/JavaScript only. It has
no PHP process, WordPress database, Astro server, comment endpoint or cloud key.
Legacy article scripts, event handlers and unreviewed embeds are not executed.

## Dependencies

The Fuwari source template pinned Astro 5.13.10. This migration updates to the
supported Astro 7 toolchain, native content collections and compatible Svelte.
Swup and its obsolete build dependency chain were removed; ordinary browser
navigation retains the theme without a client-side transition framework.

Two narrowly scoped compatibility overrides update transitive KaTeX and CSS
selector-parser dependencies. Inline/display mathematics, typography selectors,
nested CSS and the complete site build are checked against these replacements.
They are not blanket version overrides.

## Explicit Remaining Exception

Full dependency auditing reports one unpatched high-severity advisory:
`GHSA-vfj7-8cjw-p6xm` (`braces` 3.0.3). Its reviewed paths are within the
Tailwind 3 build/watch glob tooling. The affected parser is not included in the
published browser bundles, and no visitor-controlled glob patterns are handled.
Only trusted repository build patterns are used. This is a residual build-time
risk, not a claim that the dependency is fixed or that all dependencies are clean.

`scripts/check-audit.mjs` accepts only the exact reviewed advisory, version,
dependency paths and unpatched state. New advisories, new paths, a newly available
patch, malformed output or audit network failures fail CI. Reassess this exception
when a patch or a separately tested Tailwind migration is available.

## Hosting And Media

GitHub Actions receives only `contents: read` for build and Pages/OIDC permission
for deployment. No ECS/OSS/CDN credentials are stored in this repository.
GitHub Pages HTTPS and the media CDN certificate are independent. Renewing the
CDN certificate does not require reinstalling the ECS or changing its origin.

Before moving this site to another host, update `SITE_URL`, rebuild and verify the
generated paths, canonical URLs, RSS, media and search before changing DNS.
