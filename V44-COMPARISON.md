# V44 · Website comparison

## Product scope
- Select 2–4 real websites from the Websites gallery or a website detail page.
- Keep the in-progress selection in local browser storage and a shareable `/compare?sites=...` URL.
- Render an evidence-led comparison matrix: business positioning, visual language, screenshot-extracted colors, observed CSS colors when available, information architecture, trust evidence, conversion path, linked design patterns, and source completeness.
- Use the existing 85-site catalogue and 175 real page modules. Five websites currently have full research profiles; other sites show their captured catalogue fields and associated modules. Missing analysis is explicitly marked rather than inferred.
- Export a Markdown comparison report.
- Save, rename, reopen, and delete private comparison snapshots from the user's research board.

## Private API and storage
New additive table: `atlas_user_comparisons`
- `id`, `user_id`, `name`, `site_ids_json`, `created_at`, `updated_at`
- Foreign key cascades on account deletion; index by user and update time.
- `GET /api/me/comparisons`
- `POST /api/me/comparisons`
- `PATCH /api/me/comparisons/{id}`
- `DELETE /api/me/comparisons/{id}`
- Requires authenticated session and CSRF for mutations.
- Enforces 2–4 unique lowercase site IDs, max 40 saved comparisons per account, and request rate limiting.
- The normal library response and personal export include only the current account's comparison snapshots.

## SEO
- `/compare` is served by the existing private SPA route, marked `noindex, follow`, and excluded from robots crawling and the public sitemap.
- Saved comparison identifiers never enter public sitemap records.

## QA completed on feature branch
- GitHub Actions: Python compile, account/collection/comparison API tests, HTTP SEO/404 tests, and Node JavaScript syntax check — all passed.
- Browser-injected branch build against the live public catalogue: selected Vast, Fictiv and Commonwealth Fusion Systems; rendered eight comparison dimensions; confirmed the unresearched trust/conversion state is labelled as missing.
- Desktop 1440px and mobile 390px: no horizontal overflow; mobile comparison cards and cells stack vertically.
- Authenticated UI flow tested with a mocked test identity and mocked API: create a comparison, save it, reopen it from the research board, and verify the CSRF header is sent. No real user's account was used.
- No production database rows were written during QA.

## Not included / operational caution
- This feature branch does not change the production database plan or migrate account data.
- Render's current Free Postgres instance is scheduled to expire on 2026-12-24 and has no managed backups. A durable database and tested off-site backup are still required before treating the account system as long-term production storage.
- The database currently has an empty external IP allowlist; the hosted Render query connector cannot connect. Do not solve this by opening the database to `0.0.0.0/0`. Use a controlled local/SSH migration path or the provider's internal network.
- Email delivery and email verification remain unconfigured/unimplemented.
