#!/usr/bin/env python3
"""V50 read-only HTTP acceptance tests, plus an optional harmless draft-write test.

Install: pip install requests
Credentials: ATLAS_SMOKE_ADMIN_EMAIL and ATLAS_SMOKE_ADMIN_PASSWORD.
Never pass secrets on the command line or commit them to the repository.
"""
import argparse
import os
import sys
import requests

def check(condition, explanation):
    if not condition:
        raise AssertionError(explanation)
    print("PASS:", explanation)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="https://b2b-design-atlas-preview.onrender.com")
    parser.add_argument("--write-draft", action="store_true", help="creates an unpublished test draft; does not delete it")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    client = requests.Session()
    client.headers["Accept"] = "application/json"
    def get(path, session=client):
        return session.get(base + path, timeout=30, allow_redirects=False)
    health = get("/api/health")
    check(health.status_code == 200, "Health endpoint returns 200")
    status = get("/api/auth/status")
    check(status.status_code == 200 and status.json().get("mode") == "postgres", "Auth service backed by PostgreSQL")
    guest = requests.Session()
    guest.get(base + "/api/auth/me", timeout=30)
    unauthorized = get("/api/admin/overview", guest)
    check(unauthorized.status_code == 401, "Guest cannot access private admin analytics")
    check(get("/api/admin/content", guest).status_code == 401, "Guest cannot list private CMS drafts")
    check(get("/admin", guest).status_code in (302, 303), "Guest redirected from admin interface")
    public = get("/api/admin/preview")
    check(public.status_code == 200 and not public.json().get("private"), "Public preview contains no private metrics")
    email = os.getenv("ATLAS_SMOKE_ADMIN_EMAIL", "")
    password = os.getenv("ATLAS_SMOKE_ADMIN_PASSWORD", "")
    if not email or not password:
        print("SKIP: signed-in checks need ATLAS_SMOKE_ADMIN_EMAIL/PASSWORD in environment")
        return 2
    response = client.post(base + "/api/auth/login", json={"email": email, "password": password},
                           headers={"Origin": base}, timeout=30)
    check(response.status_code == 200, "Administrator login succeeds")
    token = response.json().get("csrf_token")
    check(bool(token), "Session returns CSRF token")
    overview = get("/api/admin/overview")
    check(overview.status_code == 200 and overview.json().get("mode") == "admin", "Admin overview authorized")
    listing = get("/api/admin/content?kind=article")
    check(listing.status_code == 200 and isinstance(listing.json().get("items"), list),
          "Admin CMS article inventory authorized")
    export = get("/api/admin/content/export")
    check(export.status_code == 200 and "entries" in export.json(), "CMS JSON export authorized")
    # Mutation must require both CSRF and a valid authenticated admin session.
    forbidden = client.post(base + "/api/admin/content", json={"kind":"article","slug":"v50-csrf-deny",
        "payload":{}}, headers={"Origin":base},timeout=30)
    check(forbidden.status_code == 403, "Missing CSRF blocks admin mutation")
    if args.write_draft:
        import uuid
        slug = "v50-acceptance-" + uuid.uuid4().hex[:12]
        draft = {"id":slug,"title":"V50 验收草稿","subtitle":"Unpublished operational test",
                 "category":"内部测试","author":"Atlas QA",
                 "sections":[{"title":"正文","paragraphs":["仅用于验证存储与权限，不进行发布。"]}]}
        created = client.post(base + "/api/admin/content",
            json={"kind":"article","slug":slug,"payload":draft},
            headers={"Origin":base,"X-CSRF-Token":token},timeout=30)
        check(created.status_code == 201, "Creates unpublished article draft")
        reread = get("/api/admin/content/article/" + slug)
        check(reread.status_code == 200 and reread.json().get("status")=="draft",
              "Unpublished draft persists in PostgreSQL")
        public_articles = get("/assets/articles.json", guest)
        check(public_articles.status_code == 200, "Public article catalog available")
        published = public_articles.json().get("articles", [])
        check(not any(a.get("id") == slug for a in published),
              "Unpublished draft excluded from public article catalog")
        print("NOTE: draft",slug,"intentionally remains unpublished for cleanup by admin.")
    logout = client.post(base + "/api/auth/logout",headers={"Origin":base,"X-CSRF-Token":token},timeout=30)
    check(logout.status_code==200,"Admin session can log out")
    print("Read-only acceptance completed. Restore and production publishing require separate validation.")
    return 0

if __name__ == "__main__":
    try: sys.exit(main())
    except (requests.RequestException, AssertionError, ValueError) as err:
        print("FAIL:",err,file=sys.stderr);sys.exit(1)
