# V47 · Content Studio / B2B Atlas

## Status and scope
- /admin/content is a protected real content editor (existing B2B Atlas login + explicit UUID authorization).
- /admin/content/preview is a public read-only design preview. It loads published public resources only, never drafts, account records or audit history.
- Existing Websites (85), Sections (175), Patterns (20) and Insights (10) remain in immutable packaged files as a safe baseline.
- Updates and newly created content use the existing PostgreSQL database in additive atlas_cms_entries / atlas_cms_history tables; no changes are written to the Docker filesystem.
- Four public feeds are merged with the latest published snapshots: /api/source-library, /api/module-library, /assets/patterns.json, /assets/articles.json. SEO details and sitemap read the published catalog.
- Drafts and reviews are private. Updating published content preserves the last published snapshot until review/publish. Archiving removes content from the public catalog. Restoring history creates a new draft and does not immediately change public data.
- Writes require an authenticated administrator plus origin/CSRF validation and optimistic version checks.

## Administrator login and activation
There are no shared admin passwords, bypass links, hidden developer credentials or automatic promotions.

1. Log in to an existing B2B Atlas account at /login.
2. Open /account and copy the signed-in account UUID from the 管理员授权 section.
3. The owner sets the Render environment variable ATLAS_ADMIN_USER_IDS to that precise UUID (comma-separated UUIDs are supported). DO NOT grant by unverified email address.
4. Redeploy or restart the existing service; that account can now access /admin/content using its existing email/password. Ordinary logged-in accounts receive 403, guests redirect to login.
5. Never share passwords, session cookies or database secrets. The UUID alone cannot authenticate anyone.

This first implementation has one full administrator role; separate Editor/Reviewer roles are not yet enforced. A full admin can edit, submit and publish.

## Editorial workflow
1. Select content type from the sidebar and search an existing item or create a new one.
2. Edit fields, save draft: status=draft.
3. Submit for review: status=review, not publicly visible.
4. Review and publish: status=published, public site updates.
5. Continue editing: old published snapshot stays public while the new draft is private.
6. Archive: removes the published item from public listings (be careful with existing URLs).
7. Every action creates a revision and audit row; restoring a revision creates a new draft.

Article editing currently uses structured fields and JSON chapter arrays, not a WYSIWYG. Screenshots are referenced via existing local /screenshots paths; no persistent upload/capture worker is included in this version. Users and private favorites cannot be managed through the CMS.

## Data durability and backups
CRITICAL: Render Free PostgreSQL expires 2026-12-24 and offers no managed backups. This V47 release does not upgrade or migrate the existing database. Before operational dependence, select a durable database plan/provider, run encrypted external backup, and test restoration. Do not treat a personal export as a full database backup.

The authorized admin may export CMS records and history through /api/admin/content/export. This file does not include user passwords or personal collections. It is an operational content backup convenience, not a full database backup.

## Regression and acceptance
- PYTHONPATH=backend python backend/test_cms.py
- PYTHONPATH=backend python backend/test_auth.py
- PYTHONPATH=backend python backend/test_seo.py
- PYTHONPATH=backend python backend/test_admin.py
- node --check frontend/app.js && node --check frontend/admin.js && node --check frontend/cms.js
- Browser: desktop/390px theme, preview no writes, 4 resource categories, draft/review/publish actions, version restore and export.
- Never confuse public preview with authenticated editing or suggest a CMS is a substitute for backups.
