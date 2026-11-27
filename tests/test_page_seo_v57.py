"""V57 public homepage/collection SEO lifecycle on isolated SQLite.

Exercises real auth roles, CSRF, reviewed snapshots and crawler HTML.
Never writes to production accounts, Render Postgres or the public site.
"""
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI,HTTPException,Request,Response
from app import cms_access,cms_routes,seo_pages,seo_routes,user_auth


class ReviewedPageSeoTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack()
        self.addCleanup(self.stack.close)
        self.tmp=self.stack.enter_context(tempfile.TemporaryDirectory(prefix="page-seo-v57-"))
        self.stack.enter_context(patch.dict(os.environ,{"ATLAS_BOOTSTRAP_ADMIN_PASSWORD":""}))
        for module,name,value in (
            (user_auth,"PG_URL",""),(user_auth,"SQLITE_DEMO",True),
            (user_auth,"SQLITE_FILE",str(Path(self.tmp)/"page-seo.sqlite3")),
            (user_auth,"READY",False),(cms_access,"ROLE_READY",False),
            (cms_routes,"CMS_READY",False),(seo_pages,"PAGE_READY",False),
        ):
            self.stack.enter_context(patch.object(module,name,value))
        owners=set()
        self.stack.enter_context(patch.object(cms_access,"OWNER_IDS",owners))
        self.owners=owners
        self.stack.enter_context(patch.object(seo_routes,"catalog",return_value={
            "sites":{},"modules":{},"patterns":{},"articles":{}}))
        self.stack.enter_context(patch("app.cms_schedule.publish_due",return_value=0))
        static=Path(self.tmp)
        (static/"index.html").write_text(
            '<html><head><title>Atlas</title><meta name="description" content="default"></head>'
            '<body><main id="app"><div class="shell loading">正在加载设计资源…</div></main></body></html>',
            encoding="utf-8")
        self.stack.enter_context(patch.object(seo_routes,"STATIC",static))
        app=FastAPI()
        with patch.object(app,"include_router",wraps=app.include_router) as mount:
            user_auth.register_auth_routes(app)
        auth_router=mount.call_args.args[0]
        cms_routes.register_cms_routes(app)
        seo_pages.register_page_seo_routes(app)
        routes=[r for r in app.routes if getattr(r,"methods",None)]+[
            r for r in auth_router.routes if getattr(r,"methods",None)]
        self.endpoints={(r.path,method):r.endpoint for r in routes for method in r.methods}

    def req(self,method="GET",user=None,csrf=True):
        headers=[(b"host",b"atlas.test"),(b"origin",b"https://atlas.test")]
        if user:
            headers.append((b"cookie",("atlas_session="+user["token"]).encode()))
            if csrf:headers.append((b"x-csrf-token",user["csrf"].encode()))
        return Request({"type":"http","method":method,"path":"/","scheme":"https",
                        "headers":headers,"query_string":b"",
                        "client":("127.0.0.1",10300),"server":("atlas.test",443)})

    def call(self,method,path,*args):
        return self.endpoints[(path,method)](*args)

    def account(self,name,role=None):
        res=Response()
        registered=self.call("POST","/api/auth/register",
            user_auth.Register(email=name+"@example.test",display_name="Atlas "+name,
                               password="Test-Password-234!"),self.req("POST"),res)
        cookie=SimpleCookie()
        cookie.load(res.headers["set-cookie"])
        result={"id":registered["user"]["id"],"token":cookie[user_auth.COOKIE].value,
                "csrf":registered["csrf_token"]}
        if role=="owner":self.owners.add(result["id"])
        elif role in ("editor","reviewer"):
            cms_access.ensure_roles()
            with user_auth.db() as db:
                db.execute("INSERT INTO atlas_cms_roles(user_id,role,granted_by,updated_at) VALUES(?,?,?,?)",
                           (result["id"],role,self.owner["id"],user_auth.now()))
        return result

    def test_five_pages_require_review_and_server_client_see_only_published(self):
        self.owner=self.account("owner","owner")
        editor=self.account("editor","editor")
        reviewer=self.account("reviewer","reviewer")
        get="/api/admin/seo/pages"
        save="/api/admin/seo/pages/{page}"
        action=lambda a:"/api/admin/seo/pages/{page}/"+a
        default=self.call("GET",get,self.req(user=editor))
        self.assertEqual(len(default["pages"]),5)
        self.assertEqual({x["status"] for x in default["pages"]},{"default"})
        for page in seo_pages.PAGE_KEYS:
            with self.subTest(page=page):
                seo_title="Custom "+page+" research guide"
                seo_description="This "+page+" page describes curated visual research sources and useful design references."
                payload={"seo_title":seo_title,"seo_description":seo_description,
                         "seo_image":"/screenshots/sites/vast.webp"}
                uri=("/"+page) if page!="home" else ""
                first=self.call("PUT",save,page,seo_pages.PageDraft(expected_revision=0,payload=payload),
                                self.req("PUT",editor))
                self.assertEqual(first["status"],"draft")
                html=seo_routes.seo_document(uri).body.decode("utf-8")
                self.assertNotIn(seo_title,html)
                self.assertNotIn(seo_description,html)
                waiting=self.call("POST",action("submit"),page,
                                  seo_pages.PageChange(expected_revision=first["revision"]),
                                  self.req("POST",editor))
                self.assertEqual(waiting["status"],"review")
                self.assertNotIn(seo_title,seo_routes.seo_document(uri).body.decode("utf-8"))
                with self.assertRaises(HTTPException) as forbidden:
                    self.call("POST",action("publish"),page,
                        seo_pages.PageChange(expected_revision=waiting["revision"]),
                        self.req("POST",editor))
                self.assertEqual(forbidden.exception.status_code,403)
                approved=self.call("POST",action("publish"),page,
                    seo_pages.PageChange(expected_revision=waiting["revision"]),
                    self.req("POST",reviewer))
                self.assertEqual(approved["status"],"published")
                html=seo_routes.seo_document(uri).body.decode("utf-8")
                self.assertIn(seo_title,html)
                self.assertIn(seo_description,html)
                self.assertIn('property="og:image"',html)
                self.assertIn('id="atlas-page-seo-data"',html)
                self.assertIn('"seo_title": "'+seo_title+'"',html)
                revised={**payload,"seo_title":"PRIVATE NEW "+seo_title}
                again=self.call("PUT",save,page,seo_pages.PageDraft(
                    expected_revision=approved["revision"],payload=revised),self.req("PUT",editor))
                self.assertEqual(again["status"],"draft")
                self.assertIn(seo_title,seo_routes.seo_document(uri).body.decode("utf-8"))
                self.assertNotIn("PRIVATE NEW",seo_routes.seo_document(uri).body.decode("utf-8"))
                with self.assertRaises(HTTPException) as stale:
                    self.call("PUT",save,page,seo_pages.PageDraft(
                        expected_revision=approved["revision"],payload=payload),
                        self.req("PUT",editor))
                self.assertEqual(stale.exception.status_code,409)

    def test_protected_permissions_csrf_and_invalid_images(self):
        self.owner=self.account("seo-owner","owner")
        editor=self.account("seo-editor","editor")
        reviewer=self.account("seo-reviewer","reviewer")
        update="/api/admin/seo/pages/{page}"
        payload={"seo_title":"Homepage","seo_description":"Research materials"}
        request=seo_pages.PageDraft(expected_revision=0,payload=payload)
        with self.assertRaises(HTTPException) as guest:
            self.call("PUT",update,"home",request,self.req("PUT"))
        self.assertEqual(guest.exception.status_code,401)
        with self.assertRaises(HTTPException) as csrf:
            self.call("PUT",update,"home",request,self.req("PUT",editor,csrf=False))
        self.assertEqual(csrf.exception.status_code,403)
        with self.assertRaises(HTTPException) as denied:
            self.call("PUT",update,"home",request,self.req("PUT",reviewer))
        self.assertEqual(denied.exception.status_code,403)
        for invalid in ["https://not-local.example/share.svg","javascript:alert(1)",
                        "/screenshots/../../private.svg"]:
            with self.subTest(invalid=invalid):
                with self.assertRaises(HTTPException) as bad:
                    self.call("PUT",update,"home",
                        seo_pages.PageDraft(expected_revision=0,payload={
                            **payload,"seo_image":invalid}),self.req("PUT",editor))
                self.assertEqual(bad.exception.status_code,422)
        self.assertEqual(self.call("GET","/api/admin/seo/pages",self.req(user=editor))["pages"][0]["status"],"default")
        self.assertEqual(seo_pages.published_pages(),{})

    def test_review_rejection_preserves_last_live_copy(self):
        self.owner=self.account("page-owner","owner")
        editor=self.account("page-editor","editor")
        reviewer=self.account("page-reviewer","reviewer")
        base="/api/admin/seo/pages/{page}"
        first=self.call("PUT",base,"home",seo_pages.PageDraft(expected_revision=0,payload={
            "seo_title":"Original approved home","seo_description":"First description"}),
            self.req("PUT",editor))
        submitted=self.call("POST",base+"/submit","home",
            seo_pages.PageChange(expected_revision=first["revision"]),self.req("POST",editor))
        published=self.call("POST",base+"/publish","home",
            seo_pages.PageChange(expected_revision=submitted["revision"]),self.req("POST",reviewer))
        draft=self.call("PUT",base,"home",seo_pages.PageDraft(
            expected_revision=published["revision"],payload={
                "seo_title":"Rejected next home","seo_description":"Pending description"}),
            self.req("PUT",editor))
        review=self.call("POST",base+"/submit","home",
            seo_pages.PageChange(expected_revision=draft["revision"]),self.req("POST",editor))
        rejected=self.call("POST",base+"/reject","home",
            seo_pages.PageChange(expected_revision=review["revision"]),self.req("POST",reviewer))
        self.assertEqual(rejected["status"],"draft")
        self.assertEqual(seo_pages.published_pages()["home"]["seo_title"],"Original approved home")
        self.assertNotIn("Rejected next home",seo_routes.seo_document("").body.decode("utf-8"))

    def test_static_frontend_contract_and_hydration(self):
        source=Path(__file__).resolve().parents[1]
        # Files are mounted under /srv/atlas/static in the Docker build.
        static=source/"static"
        # This test's patched STATIC holds the isolated SEO HTML only;
        # verify the actual deployed source files from Docker.
        page=(static/"cms.html").read_text(encoding="utf-8")
        cms=(static/"assets"/"cms.js").read_text(encoding="utf-8")
        spa=(static/"assets"/"app.js").read_text(encoding="utf-8")
        self.assertIn('id="cms-page-seo-dialog"',page)
        self.assertIn('id="cms-page-seo-open"',page)
        self.assertIn("/api/admin/seo/pages",cms)
        self.assertIn("pageSeoOverrides",spa)
        self.assertIn("atlas-page-seo-data",spa)


if __name__=="__main__":
    unittest.main()
