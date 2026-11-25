#!/usr/bin/env bash
# V50: verify encrypted backup and optionally restore into a separate disposable DB.
set -Eeuo pipefail
umask 077
archive="${1:?Usage: verify-postgres-backup.sh FILE.dump.age [restore-to-disposable-db]}"
manifest="$archive.sha256"
[[ -r "$archive" && -r "$manifest" ]] || { echo "Backup or checksum missing" >&2; exit 2; }
for program in age pg_restore sha256sum; do
  command -v "$program" >/dev/null || { echo "Missing $program" >&2; exit 2; }
done
(cd "$(dirname "$archive")" && sha256sum --check "$(basename "$manifest")")
: "${ATLAS_BACKUP_AGE_IDENTITY:?Set ATLAS_BACKUP_AGE_IDENTITY to your private age identity FILE}"
tmp="$(mktemp "${TMPDIR:-/tmp}/atlas-restore-XXXXXXXX.dump")"
trap 'rm -f -- "$tmp"' EXIT
age -d -i "$ATLAS_BACKUP_AGE_IDENTITY" -o "$tmp" "$archive"
pg_restore --list "$tmp" >/dev/null
echo "Backup checksum and PostgreSQL archive structure verified."
if [[ "${2:-}" == "restore-to-disposable-db" ]]; then
  : "${ATLAS_RESTORE_DATABASE_URL:?Set ATLAS_RESTORE_DATABASE_URL to a NEW EMPTY disposable database}"
  [[ "${ATLAS_RESTORE_CONFIRM:-}" == "DISPOSABLE_DATABASE_ONLY" ]] || {
    echo "Refusing restore. Set ATLAS_RESTORE_CONFIRM=DISPOSABLE_DATABASE_ONLY." >&2; exit 2;
  }
  # Do not use a production target. This command writes to the supplied database.
  PGDATABASE="$ATLAS_RESTORE_DATABASE_URL" pg_restore --exit-on-error --single-transaction --no-owner --no-privileges "$tmp"
  echo "Disposable restore complete. Validate counts and app flows before production migration."
fi
