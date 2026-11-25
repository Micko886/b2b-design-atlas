"""V46 regression: admin ACL, public-only preview, live content metrics, real DB aggregates.
Run: PYTHONPATH=backend python backend/test_admin.py
"""
import json
import os
import sys
import tempfile
import types
from pathlib import Path

os.environ["ATLAS_ALLOW_EPHEMERAL_AUTH"]="1"
temp=tempfile.TemporaryDirectory()
root=Path(temp.name)
os.environ["ATLAS_USERS_DB_PATH"]=str(root/"users.sqlite3")
os.environ.pop("ATLAS_USERS_DATABASE_URL",None)
os.environ.pop("ATLAS_ADMIN_USER_IDS",None)

import user_auth
import seo_routes
package=types.ModuleType("app")
package.__path__=[]
package.user_auth=user_auth
package.seo_routes=seo_routes
sys.modules["app"]=package
sys.modules["app.user_auth"]=user_auth
sys.modules["app.seo_routes"]=seo_routes
import admin_routes
from fastapi import FastAPI
from fastapi.testclient import TestClient

(root/"app").mkdir(exist_ok=True)
(root/"static"/"assets").mkdir(parents=True)
(root/"screenshots"/"sites").mkdir(parents=True)
(root/"screenshots"/"sites"/"vast.webp").write_bytes(b"webp-for-existence-test")
(root/"static"/"admin.html").write_text('<html><body data-admin-mode="__ADMIN_MODE__"><h1>Control Room</h1></body></html>',encoding="utf8")
(root/"app"/"source_index.json").write_text(json.dumps({"sites":[
 {"id":"vast","name":"Vast","sector":"Aerospace"},
 {"id":"fictiv","name":"Fictiv","sector":"Manufacturing"},
 {"id":"lumafield","name":"Lumafield","sector":"Manufacturing"}
]}),encoding="utf8")
(root/"app"/"module_catalog.json").write_text(json.dumps([{"id":"hero-1"},{"id":"hero-2"}]),encoding="utf8")
(root/"static"/"assets"/"patterns.json").write_text(json.dumps([{"id":"object-first-hero"}]),encoding="utf8")
(root/"static"/"assets"/"articles.json").write_text(json.dumps({"articles":[{"id":"design-research","title":"Research","category":"cases","date":"2026-11-24"}]}),encoding="utf8")
(root/"static"/"assets"/"research.json").write_text(json.dumps({"vast":{"checked":"2026-11-24"},"fictiv":{"style":["Technical"]}}),encoding="utf8")

seo_routes.BASE=root
seo_routes.STATIC=root/"static"
seo_routes.catalog.cache_clear()
admin_routes.ROOT=root
admin_routes.STATIC=root/"static"
admin_routes.ADMIN_IDS.clear()
app=FastAPI()
user_auth.register_auth_routes(app)
admin_routes.register_admin_routes(app)
guest=TestClient(app,base_url="https://testserver")
non_admin=TestClient(app,base_url="https://testserver")
admin=TestClient(app,base_url="https://testserver")

def check(response,expected):
 assert response.status_code==expected,(response.status_code,response.text[:900])
 return response.json()

data=check(guest.get("/api/admin/preview"),200)
assert data["mode"]=="preview"
assert data["private"] is None and data["email_reset_enabled"] is None
assert "administrator" not in data
assert data["counts"]=={"websites":3,"sections":2,"patterns":1,"insights":1}
assert data["review"]=={"reviewed":1,"pending":2,"shots_ready":1,"shots_missing":2}
assert data["sectors"][0]=={"name":"Manufacturing","count":2}
assert len(data["queue"])==2
assert data["recent_articles"][0]["url"]=="/insights/design-research"
assert guest.get("/api/admin/preview").headers["cache-control"]=="no-store"
assert guest.get("/api/admin/overview").status_code==401
redirect=guest.get("/admin",follow_redirects=False)
assert redirect.status_code==302
assert redirect.headers["location"].startswith("/login?")
assert "noindex" in redirect.headers["x-robots-tag"]
preview=guest.get("/admin/preview")
assert preview.status_code==200
assert 'data-admin-mode="preview"' in preview.text
assert "no-store"==preview.headers["cache-control"]
assert "frame-ancestors 'none'" in preview.headers["content-security-policy"]

ordinary=check(non_admin.post("/api/auth/register",json={
 "email":"reader@qa.example","display_name":"Reader","password":"very-secure-test-password"
}),201)
assert non_admin.get("/admin").status_code==403
assert non_admin.get("/api/admin/overview").status_code==403

owner=check(admin.post("/api/auth/register",json={
 "email":"owner@qa.example","display_name":"Owner","password":"very-secure-test-password"
}),201)
# Authorize by authenticated immutable user ID, not by unverified email.
admin_routes.ADMIN_IDS.add(owner["user"]["id"])
assert non_admin.get("/api/admin/overview").status_code==403
assert guest.get("/api/admin/overview").status_code==401
check(admin.post("/api/me/library",json={"collection":"saved","key":"site:vast"},
                 headers={"X-CSRF-Token":owner["csrf_token"]}),201)
result=check(admin.get("/api/admin/overview"),200)
assert result["mode"]=="admin"
assert result["private"]["totals"]["users"]==2
assert result["private"]["totals"]["saves"]==1
assert len(result["private"]["activity"])==30
assert result["administrator"]["email"]=="owner@qa.example"
assert result["counts"]["websites"]==3
assert "no-store"==admin.get("/api/admin/overview").headers["cache-control"]
assert 'data-admin-mode="admin"' in admin.get("/admin").text

# Preview stays devoid of private data after accounts / saves are created.
latest=check(guest.get("/api/admin/preview"),200)
assert "owner@qa.example" not in json.dumps(latest)
assert latest["private"] is None
assert latest["counts"]["websites"]==3
print("ADMIN_V46_QA_PASS: protected admin, no user PII in preview, actual directory metrics, theme page and DB aggregates")
temp.cleanup()
