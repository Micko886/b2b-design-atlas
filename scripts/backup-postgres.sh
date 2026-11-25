#!/usr/bin/env bash
# V50: encrypted, restorable full PostgreSQL backup; run outside the ephemeral Render web service.
set -Eeuo pipefail
umask 077
: "${ATLAS_BACKUP_DATABASE_URL:?Set ATLAS_BACKUP_DATABASE_URL to a PostgreSQL connection URL}"
: "${ATLAS_BACKUP_AGE_RECIPIENT:?Set ATLAS_BACKUP_AGE_RECIPIENT to an age public key}"
: "${ATLAS_BACKUP_DIR:?Set ATLAS_BACKUP_DIR to a secure persistent output directory}"
for program in pg_dump pg_restore age sha256sum; do
  command -v "$program" >/dev/null || { echo "Missing required tool: $program" >&2; exit 2; }
done
server_major="$(pg_dump --version | grep -oE '[0-9]+' | head -1)"
if [[ "$server_major" -lt 17 ]]; then
  echo "PostgreSQL 17+ client utilities required (Render database is PostgreSQL 17)." >&2
  exit 2
fi
mkdir -p -- "$ATLAS_BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
prefix="$ATLAS_BACKUP_DIR/atlas-postgres-$stamp"
tmp="$(mktemp "${TMPDIR:-/tmp}/atlas-pg-XXXXXXXX.dump")"
trap 'rm -f -- "$tmp"' EXIT
# Include ALL database tables: accounts, password hashes, sessions, private collections,
# comparisons, CMS content and audit history. Never save plaintext backup at the destination.
PGDATABASE="$ATLAS_BACKUP_DATABASE_URL" pg_dump --format=custom --compress=6 --no-owner --no-privileges --file="$tmp"
pg_restore --list "$tmp" >/dev/null
age -r "$ATLAS_BACKUP_AGE_RECIPIENT" -o "$prefix.dump.age" "$tmp"
(cd "$ATLAS_BACKUP_DIR" && sha256sum "$(basename "$prefix.dump.age")") > "$prefix.dump.age.sha256"
chmod 600 "$prefix.dump.age" "$prefix.dump.age.sha256"
echo "Encrypted archive: $prefix.dump.age"
echo "SHA256 manifest: $prefix.dump.age.sha256"
echo "Store these files offsite; no scheduled job or remote upload was created."
