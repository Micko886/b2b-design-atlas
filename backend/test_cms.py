"""V47 CMS regression: public isolation, CSRF, versioning, four content types.
Uses ephemeral local SQLite and never touches live account data.
Run: PYTHONPATH=backend python backend/test_cms.py
"""
import os
import json
import tempfile
import sys
import types
from pathlib import Path

os.environ["ATLAS_ALLOW_EPHEMERAL_AUTH"]="1"
os.environ.pop("ATLAS_USERS_DATABASE_URL",None)
tmp=tempfile.TemporaryDirectory()
root=Path(tmp.name)
os.environ["ATLAS_USERS_DB_PATH"]=str(root/"users.sqlite3")

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
package.admin_routes=admin_routes
sys.modules["app.admin_routes"]=admin_routes
import cms_routes
package.cms_routes=cms_routes
sys.modules["app.cms_routes"]=cms_routes

from fastapi import FastAPI
from fastapi.testclient import TestClient
app=FastAPI()
root.joinpath("app").mkdir()
root.joinpath("static","assets").mkdir(parents=True)
root.joinpath("static","admin.html").write_text('<html data-admin-mode="__ADMIN_MODE__"></html>')
root.joinpath("static","cms.html").write_text('<html data-cms-mode="__CMS_MODE__"></html>')
root.joinpath("static","index.html").write_text('<html><head><title>Default</title><meta name="description" content="Default"></head></html>')
root.joinpath("app","source_index.json").write_text(json.dumps({"checked_at":"test","sites":[
 {"id":"vast","name":"Vast","url":"https://www.vastspace.com/","sector":"Aerospace","summary":"Orbital systems","focus":"Space"}],"notes":["source note"]}))
root.joinpath("app","module_catalog.json").write_text(json.dumps([{
 "id":"vast-hero","title":"Vast Hero","site_id":"vast","category":"Hero","lesson":"Big engineering photography"}]))
root.joinpath("static","assets","patterns.json").write_text(json.dumps([{
 "id":"object-first-hero","title":"Object First Hero","family":"Visual","question":"How?",
 "principle":"Objects lead the visual hierarchy","modules":["vast-hero"]}]))
root.joinpath("static","assets","articles.json").write_text(json.dumps({
 "categories":[{"id":"methods","name":"Methods"}],"articles":[{
  "id":"study","title":"Study","subtitle":"Example research","category":"methods","author":"Atlas",
  "sections":[{"title":"Chapter","paragraphs":["Content"]}]}]}))

seo_routes.BASE=root
seo_routes.STATIC=root/"static"
seo_routes.catalog.cache_clear()
cms_routes.CMS_READY=False
cms_routes.invalidate()
admin_routes.ROOT=root
admin_routes.STATIC=root/"static"
admin_routes.ADMIN_IDS.clear()
user_auth.register_auth_routes(app)
admin_routes.register_admin_routes(app)
cms_routes.register_cms_routes(app)

guest=TestClient(app,base_url="https://testserver")
writer=TestClient(app,base_url="https://testserver")
stranger=TestClient(app,base_url="https://testserver")

def check(res,code):
    assert res.status_code==code,(res.status_code,res.text[:450])
    return res.json()

assert guest.get("/api/admin/content").status_code==401
assert guest.get("/admin/content",follow_redirects=False).status_code==302
assert guest.get("/admin/content/preview").status_code==200
assert "preview" in guest.get("/admin/content/preview").text
assert guest.get("/api/source-library").status_code==200
assert len(check(guest.get("/api/source-library"),200)["sites"])==1

own=check(writer.post("/api/auth/register",json={"email":"owner@qa.invalid","display_name":"Editor",
    "password":"very-long-test-password"}),201)
csrf=own["csrf_token"]
head={"X-CSRF-Token":csrf}
check(stranger.post("/api/auth/register",json={"email":"ordinary@qa.invalid","display_name":"Viewer",
    "password":"very-long-test-password"}),201)
admin_routes.ADMIN_IDS.add(own["user"]["id"])
assert stranger.get("/api/admin/content").status_code==403
assert stranger.get("/admin/content").status_code==403
assert writer.post("/api/admin/content",json={},headers=head).status_code==422
assert writer.post("/api/admin/content",json={"kind":"site","slug":"new-site","payload":{}},headers={}).status_code==403
assert writer.get("/admin/content").status_code==200

payload={"id":"new-site","name":"Atlas Test Site","sector":"Manufacturing",
         "url":"https://example.org/","summary":"Clear industrial architecture",
         "design_strengths":["Legible technical content"]}
created=check(writer.post("/api/admin/content",headers=head,json={
 "kind":"site","slug":"new-site","payload":payload}),201)
assert created["revision"]==1
assert "new-site" not in [x["id"] for x in check(guest.get("/api/source-library"),200)["sites"]]
assert "new-site" not in seo_routes.catalog()["sites"]
assert writer.get("/api/admin/content?kind=site").status_code==200
assert any(x["slug"]=="new-site" and x["status"]=="draft"
           for x in check(writer.get("/api/admin/content?kind=site"),200)["items"])
assert writer.post("/api/admin/content/site/new-site/publish",headers=head,json={"expected_revision":1}).status_code==409
submit=check(writer.post("/api/admin/content/site/new-site/submit",headers=head,json={"expected_revision":1}),200)
assert submit=={"ok":True,"status":"review","revision":2}
assert "new-site" not in seo_routes.catalog()["sites"]
published=check(writer.post("/api/admin/content/site/new-site/publish",headers=head,json={"expected_revision":2}),200)
assert published["revision"]==3 and published["status"]=="published"
assert seo_routes.catalog()["sites"]["new-site"]["name"]=="Atlas Test Site"
assert len(check(guest.get("/api/source-library"),200)["sites"])==2
assert seo_routes.seo_record("/websites/new-site")["title"].startswith("Atlas Test Site")
assert len(check(guest.get("/api/admin/preview"),200)["counts"])==4
assert check(guest.get("/api/admin/preview"),200)["counts"]["websites"]==2
assert "draft_json" not in guest.get("/api/admin/preview").text
assert guest.get("/api/admin/overview").status_code==401

edited=dict(payload,name="Atlas Test Site v2")
check(writer.put("/api/admin/content/site/new-site",headers=head,json={
 "payload":edited,"expected_revision":3}),200)
assert seo_routes.catalog()["sites"]["new-site"]["name"]=="Atlas Test Site","New draft leaked to public"
assert writer.put("/api/admin/content/site/new-site",headers=head,json={
 "payload":edited,"expected_revision":3}).status_code==409
detail=check(writer.get("/api/admin/content/site/new-site"),200)
assert detail["status"]=="draft" and detail["revision"]==4 and detail["published"]["name"]=="Atlas Test Site"
assert len(detail["history"])==4
check(writer.post("/api/admin/content/site/new-site/submit",headers=head,json={"expected_revision":4}),200)
check(writer.post("/api/admin/content/site/new-site/publish",headers=head,json={"expected_revision":5}),200)
assert seo_routes.catalog()["sites"]["new-site"]["name"]=="Atlas Test Site v2"
restored=check(writer.post("/api/admin/content/site/new-site/restore",headers=head,
    json={"expected_revision":6,"revision":1}),200)
assert restored["revision"]==7
assert seo_routes.catalog()["sites"]["new-site"]["name"]=="Atlas Test Site v2", "Restored draft leaked to live"
detail=check(writer.get("/api/admin/content/site/new-site"),200)
assert detail["payload"]["name"]=="Atlas Test Site"

# Modify a legacy source item: save must preserve baseline until review/publish.
old={"id":"vast","name":"Vast Updated","url":"https://www.vastspace.com/",
      "sector":"Aerospace","summary":"New publish copy"}
check(writer.put("/api/admin/content/site/vast",headers=head,
    json={"expected_revision":0,"payload":old}),200)
assert seo_routes.catalog()["sites"]["vast"]["name"]=="Vast"
check(writer.post("/api/admin/content/site/vast/submit",headers=head,json={"expected_revision":1}),200)
check(writer.post("/api/admin/content/site/vast/publish",headers=head,json={"expected_revision":2}),200)
assert seo_routes.catalog()["sites"]["vast"]["name"]=="Vast Updated"

# All four resource types publish to their real public APIs.
entries=[
 ("module","new-module",{"id":"new-module","title":"New Module","site_id":"vast",
    "category":"Hero","lesson":"Controlled snapshot"}),
 ("pattern","new-pattern",{"id":"new-pattern","title":"New Pattern","family":"UX",
    "question":"What is the tradeoff?","principle":"One decision at a time","modules":["vast-hero"]}),
 ("article","new-article",{"id":"new-article","title":"New Article","subtitle":"Find a pattern",
    "category":"methods","author":"B2B Atlas","sections":[{"title":"Chapter","paragraphs":["Read me"]}]})
]
for kind,slug,p in entries:
    check(writer.post("/api/admin/content",headers=head,json={"kind":kind,"slug":slug,"payload":p}),201)
    check(writer.post(f"/api/admin/content/{kind}/{slug}/submit",headers=head,json={"expected_revision":1}),200)
    check(writer.post(f"/api/admin/content/{kind}/{slug}/publish",headers=head,json={"expected_revision":2}),200)
assert "new-module" in [x["id"] for x in check(guest.get("/api/module-library"),200)["modules"]]
assert "new-pattern" in [x["id"] for x in check(guest.get("/assets/patterns.json"),200)]
assert "new-article" in [x["id"] for x in check(guest.get("/assets/articles.json"),200)["articles"]]
assert seo_routes.seo_record("/insights/new-article")["title"]=="New Article"

before=check(writer.get("/api/admin/content/export"),200)
assert len(before["entries"])>=5 and len(before["history"])>=17
assert "password_hash" not in json.dumps(before)
check(writer.post("/api/admin/content/site/vast/archive",headers=head,
    json={"expected_revision":3}),200)
assert "vast" not in seo_routes.catalog()["sites"]
assert "vast" not in [x["id"] for x in check(guest.get("/api/source-library"),200)["sites"]]
assert guest.get("/api/admin/content/export").status_code==401
print("CMS_V47_QA_PASS: durable drafts, review/publish, 4 live feeds, legacy overlay, rollback, archive, admin ACL, CSRF")
tmp.cleanup()
