# V46 — B2B Atlas Control Room (运营总览)

An independently styled operations overview:

- /admin/preview — public read-only **design preview** powered exclusively by public Websites, Sections, Patterns, Insights and research metadata. It contains no account, session, email, favorites, user activity or personal data. The route is noindex, and it has no write actions.
- /admin — admin-only read-only dashboard. Guests redirect to login; authenticated accounts without admin authorization get HTTP 403.
- /api/admin/preview — public aggregate catalog data, with no account database access.
- /api/admin/overview — strictly protected aggregates from PostgreSQL accounts/collections plus the public catalog.

## Activate administrator access

1. Log into the intended B2B Atlas account; read the authenticated /api/auth/me response and copy its user.id UUID.
2. In the existing Render Web Service environment variables, set ATLAS_ADMIN_USER_IDS to that UUID (or a comma-separated list). Never commit IDs that identify private users, passwords, cookies, or database secrets to the repository.
3. Restart/redeploy the existing Web Service so the environment variable is loaded.
4. Access /admin. Confirm the admin receives HTTP 200 and the current aggregated account statistics. A different signed-in non-admin should receive 403, and a guest should be redirected to login.

**Why use UUIDs rather than an email allowlist?** Email registration does not yet verify inbox ownership. Allowlisting an email could allow an attacker to register a claimed address first. The admin ID must be explicitly granted server-side, and all protected API calls recheck the authenticated session.

## UI and behavior

- Independent responsive dashboard, separate from public-site header/footer.
- Complete light and dark themes with persistent user choice (localStorage key atlas-admin-theme).
- Public content KPIs, resource mix donut, industry distribution, research completion and screenshot-file availability.
- Authentic, searchable research backlog; source links and mobile drawer navigation.
- Public research article index; working refresh and download of a JSON report.
- Protected mode adds real aggregate totals for registered users, saved references, board entries, and a 7/14/30-day daily-new-saves chart generated from existing timestamps.
- Preview intentionally hides user/account totals and renders a privacy explanation instead.

## Limits and remaining operational work

- V46 is a **read-only overview**, not a CMS, editor, publishing console, screenshot capture tool or approval system.
- A research item is marked pending when the catalog has no checked research profile. This is not an automatically verified editorial workflow.
- No fabricated website traffic, conversion metrics, or arbitrary growth percentages.
- Existing Free PostgreSQL expiration and lack of managed backups remain unresolved. Plan off-site backups and migration before long-term operation.
- Password recovery via email remains disabled until SMTP is configured. This release does not upgrade paid resources.

## Testing

- Run: PYTHONPATH=backend python backend/test_admin.py
- Run: node --check frontend/admin.js
- Verify live preview at 1440px, 768px and 390px; test both themes, persistence, queue search, working download and drawer navigation.
- Verify API preview cannot access private records; validate guest redirect, normal-user 403 and admin-only statistics after setting ATLAS_ADMIN_USER_IDS.
