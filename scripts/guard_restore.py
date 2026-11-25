#!/usr/bin/env python3
"""Protect pg_restore from accidental production targets.

Only an explicitly named disposable database may receive restoration. A matching
source URL is always rejected. Does not connect or print credentials.
"""
import os
import re
import sys
from urllib.parse import urlsplit, unquote

def identity(raw):
    if not raw:
        raise ValueError("database connection URL is missing")
    url = urlsplit(raw)
    if url.scheme not in ("postgresql", "postgres") or not url.hostname:
        raise ValueError("only PostgreSQL connection URLs are supported")
    db = unquote(url.path.lstrip("/"))
    if not db or "/" in db:
        raise ValueError("database name is required")
    return (url.hostname.lower(), url.port or 5432, db)

def validate_restore_target(target, source=None):
    host, port, name = identity(target)
    if not re.fullmatch(r"(?:atlas_restore|disposable_atlas)_[a-z0-9_]{1,45}", name):
        raise ValueError("restore target must be explicitly named atlas_restore_* or disposable_atlas_*")
    if source and identity(source) == (host, port, name):
        raise ValueError("restore target matches source production database")
    return True

if __name__ == "__main__":
    try:
        validate_restore_target(os.getenv("ATLAS_RESTORE_DATABASE_URL"),
                                os.getenv("ATLAS_BACKUP_DATABASE_URL"))
    except (ValueError, TypeError) as exc:
        print("Restore denied: " + str(exc), file=sys.stderr)
        sys.exit(2)
    print("Disposable restore target name verified")
