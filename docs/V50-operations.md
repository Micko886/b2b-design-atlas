# V50 · Admin acceptance, PostgreSQL backup & recovery

## Verified infrastructure (2026-11-25)
- Render Web Service: `srv-dc1tlouc6qcc73brcgd0`, last verified V49 deploy `dep-dc34r7ifngtc73ctsed0` = live.
- PostgreSQL: `dpg-dc2liq3m8hqs73fturcg-a`, PostgreSQL 17, free, `available`. Expiration: **2026-12-24 09:31 UTC**. Verify your actual instance status again in the Render dashboard.
- The database's external IP allowlist is empty. That is an appropriate production restriction; do not open it to `0.0.0.0/0`.
- Accounts, password hashes, session tokens (hashes), collections, annotations, comparisons, CMS entries and CMS history reside in PostgreSQL. Immutable original catalog and screenshots live in repository/deploy artifacts.
- V49 one-time admin-bootstrap secrets were cleared from runtime variables after account creation. Authorization is via `ATLAS_ADMIN_USER_IDS`.

## Exact verification scope
1. Public `GET /api/health` should return HTTP 200; `GET /api/auth/status` must say PostgreSQL; `GET /api/admin/preview` contains no `private` field data.
2. Guest `GET /api/admin/overview` and `GET /api/admin/content` must return HTTP 401. Guest `GET /admin` must redirect to login.
3. Valid admin login sets an HttpOnly secure same-site cookie and issues a CSRF token. Authenticated admin overview and CMS list/export return HTTP 200.
4. Admin mutation without CSRF must fail HTTP 403. Users without a configured administrator UUID must fail HTTP 403.
5. For real CRUD, create an unpublished article draft, read it back, edit it, submit for review, publish **only with explicit production approval**, and verify public HTML and API. Test restore in a nonproduction environment first. Monitor errors after redeploy.
6. Password reset depends on SMTP configuration; placeholder `.local` admin email cannot receive mail.
7. Run `python scripts/smoke-admin.py` from a trusted machine with outbound HTTPS, supplying `ATLAS_SMOKE_ADMIN_EMAIL` and `ATLAS_SMOKE_ADMIN_PASSWORD` only via private environment variables. Use `--write-draft` only when explicitly okay with leaving an unpublished test record.

## Encrypted full backup (not a scheduled job)
**Requirements**: PostgreSQL 17+ client binaries (`pg_dump`/`pg_restore`), `age`, `sha256sum`, and a trusted machine/runner that can connect via an allowed network path. A free Render database may have restrictions; provision an approved access method rather than broadening the allowlist. The connection string and age private identity must never enter Git.

```bash
export ATLAS_BACKUP_DATABASE_URL='postgresql://...'
export ATLAS_BACKUP_AGE_RECIPIENT='age1...'
export ATLAS_BACKUP_DIR='/secure/atlas-backups'
bash scripts/backup-postgres.sh
```

The script creates a versioned encrypted `*.dump.age` and `*.sha256` file; the temporary plaintext dump is deleted. It does **not** automatically upload to an offsite destination or set up recurrence. Arrange offsite copy with restricted access, retention and expiration alerts. Keep the age private key separately from backup files and periodically test a restore.

## Integrity and disposable restore
```bash
export ATLAS_BACKUP_AGE_IDENTITY='/private/path/to/age-identity.txt'
bash scripts/verify-postgres-backup.sh /secure/atlas-backups/atlas-postgres-YYYYMMDDTHHMMSSZ.dump.age
# For an explicitly disposable EMPTY test DB only:
export ATLAS_RESTORE_DATABASE_URL='postgresql://...disposable...'
export ATLAS_RESTORE_CONFIRM='DISPOSABLE_DATABASE_ONLY'
bash scripts/verify-postgres-backup.sh /secure/atlas-backups/atlas-postgres-YYYYMMDDTHHMMSSZ.dump.age restore-to-disposable-db
```

Do not supply the production database as a restore target. For migration: create a new supported PostgreSQL service, validate network/credentials, take a fresh encrypted snapshot, restore into the new empty database, verify table counts and account/CMS behavior, change `ATLAS_USERS_DATABASE_URL` through Render's private environment settings, deploy and check the app, then retain the old database until all tests pass.

## Outstanding production acceptance
At initial V50 assessment no public HTTPS session could be established from the execution environment, and Render's query connector cannot access the allowlisted database. Thus administrator login, live CMS mutation and true backup/restore are **not confirmed** by this repository commit. Do not confuse deploy success with full acceptance.

**Deadline**: Migrate/renew the free PostgreSQL instance **before 2026-12-24**. A script committed to GitHub does not safeguard your data until someone runs it, verifies it, and stores encrypted copies outside the expiring database.
