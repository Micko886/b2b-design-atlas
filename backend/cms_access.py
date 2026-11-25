"""Granular CMS roles. Owners are only explicit ATLAS_ADMIN_USER_IDS.

Additional editor/reviewer grants must be issued by an owner and stored in
PostgreSQL. Roles are assigned by immutable user ID, never unverified email.
"""
from __future__ import annotations
import os
import re
import threading
from app import user_auth

OWNER_IDS={
    value.strip().lower()
    for value in os.getenv("ATLAS_ADMIN_USER_IDS","").split(",")
    if re.fullmatch(r"[0-9a-fA-F-]{36}",value.strip())
}
ROLE_LOCK=threading.Lock()
ROLE_READY=False
ROLE_SCHEMA=[
    """CREATE TABLE IF NOT EXISTS atlas_cms_roles (
      user_id TEXT PRIMARY KEY REFERENCES atlas_users(id) ON DELETE CASCADE,
      role TEXT NOT NULL CHECK(role IN ('editor','reviewer')),
      granted_by TEXT NOT NULL,updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS atlas_cms_role_history (
      id TEXT PRIMARY KEY,user_id TEXT NOT NULL,action TEXT NOT NULL,
      role TEXT NOT NULL,actor_id TEXT NOT NULL,created_at TEXT NOT NULL
    )"""
]
CAPABILITIES={
    "owner":{"view","edit","review","team","export","media","taxonomy"},
    "editor":{"view","edit","media","taxonomy"},
    "reviewer":{"view","review"},
}
def ensure_roles():
    global ROLE_READY
    if ROLE_READY:return
    user_auth.ensure_ready()
    with ROLE_LOCK:
        if ROLE_READY:return
        with user_auth.db() as db:
            for statement in ROLE_SCHEMA:db.execute(statement)
        ROLE_READY=True

def role_for(session):
    if not session:return None
    user_id=str(session.get("user_id","")).lower()
    if user_id in OWNER_IDS:return "owner"
    if not re.fullmatch(r"[0-9a-fA-F-]{36}",user_id):return None
    try:
        ensure_roles()
        with user_auth.db() as db:
            assigned=db.one("SELECT role FROM atlas_cms_roles WHERE user_id=?",(user_id,))
        return assigned["role"] if assigned and assigned["role"] in ("editor","reviewer") else None
    except Exception:
        # No fallback to email or permissive legacy roles.
        return None

def can(session,action):
    return action in CAPABILITIES.get(role_for(session),set())

def require(session,action):
    if not can(session,action):
        user_auth.error(403,"当前后台角色无此操作权限。")
    return session

def describe(session):
    role=role_for(session)
    return {"role":role,"capabilities":sorted(CAPABILITIES.get(role,set()))}
