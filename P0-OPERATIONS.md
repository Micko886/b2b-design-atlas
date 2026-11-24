# B2B Atlas P0 · Operations and release gates

## State of the stack (2026-11-24)
- Render Web Service: Free.
- Account storage: Render PostgreSQL instance \`b2b-atlas-users\` (Free); service uses \`ATLAS_USERS_DATABASE_URL\` as a Render-managed secret reference.
- **Database expires 2026-12-24.** Free Postgres has **no managed backups**; its 30-day expiry makes it unsuitable as the long-term home of registered users' data.
- Never publish the full database URL, password hashes, reset tokens, session records or SQL exports to the public GitHub repository.
- The API \`GET /api/me/export\` gives a signed-in user **only their own** profile, saved items, folders, tags, notes and board data. This is a *personal export*, **not** a complete database backup.

## Required before long-term public signup
1. Choose a durable managed Postgres plan/provider with automatic backups and a restore procedure. Confirm cost with the owner before any paid upgrade.
2. Use the official \`pg_dump\` / \`pg_restore\` tools or the provider's secure migration workflow. Perform a full logical export to **encrypted storage outside the Render Free service**, and test restoration into a separate database.
3. Verify migrated data counts for \`atlas_users\`, \`atlas_sessions\` (prefer invalidating old sessions), \`atlas_user_items\`, \`atlas_user_entities\`, \`atlas_user_folders\`, \`atlas_user_folder_items\`, \`atlas_item_annotations\`. Do not leak authentication tables into a user-facing download.
4. Update only the secure \`ATLAS_USERS_DATABASE_URL\` environment value; test registration, login, per-user folders and export on the new database.
5. Set a recurring off-site backup schedule, monitoring for backup failures, and test restore at least once before production designation.

Official references:
- https://render.com/docs/free
- https://render.com/docs/postgresql-backups

## Password recovery
Password recovery routes and UI are implemented, but **email delivery is disabled until a provider is configured**. In Render, set these secrets (never commit values):
- \`ATLAS_SMTP_HOST\` (required)
- \`ATLAS_SMTP_PORT\` (defaults to 587)
- \`ATLAS_SMTP_USER\` (required)
- \`ATLAS_SMTP_PASSWORD\` (required)
- \`ATLAS_SMTP_FROM\` (required, validated sender address)
- \`ATLAS_PUBLIC_ORIGIN\` (optional; defaults to the existing preview domain)

Routes:
- \`POST /api/auth/request-password-reset\` generates a hashed, expiring token and sends a 20-minute recovery link. Requests are rate-limited.
- \`POST /api/auth/reset-password\` consumes that token, updates the PBKDF2 password hash and invalidates existing sessions.
- \`GET /api/auth/status\` reports \`password_reset_available\`, so the UI does not offer a falsely working email flow before configuration.

**Email address verification is not implemented yet.** Do not describe accounts as email-verified until a sending provider and verification workflow are in place.

## SEO and 404
- Direct requests for unknown slugs/paths return HTTP 404 and \`noindex\`.
- Valid public entity paths return HTTP 200 and dedicated SEO title/description, canonical, OpenGraph and article structured data.
- \`/sitemap.xml\` includes published public resources, not private accounts.
- \`/robots.txt\` excludes private account and recovery paths.
- The SPA also updates client-side metadata during navigation.
- Use \`backend/test_seo.py\` plus a real HTTP request to assert true HTTP status; a visually rendered 404 alone is insufficient.

## V43 private library
- Existing V40 site/section saves remain untouched in \`atlas_user_items\`.
- Pattern/article items use \`atlas_user_entities\`; folders, item associations, and annotations are separate additive tables.
- Only authenticated, CSRF-validated users may mutate their personal data.
- Folder deletion removes memberships but **never deletes the underlying saved resource**.
- User-facing export excludes passwords, session hashes and other users' data.
- Avoid treating public data structures such as article IDs as secret access tokens.

## Acceptance checks
Run the GitHub Actions P0 QA workflow (Python API + SEO + JS syntax), then test 390px, 768px and 1440px:
- homepage and four browse pages retain existing design;
- live direct HTTP 404, metadata, sitemap, robots;
- guest save triggers login; existing V40 accounts remain accessible;
- user A and user B cannot inspect each other's folders or notes;
- create, rename, delete folders; add/remove items without deleting saved references;
- save Website / Section / Pattern / Article, add tags/notes and export own JSON;
- password reset must show an unavailable state if SMTP credentials have not been configured.
