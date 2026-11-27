"""V54.4: real auth/session/CSRF/CMS role lifecycle on a disposable local SQLite database.

No fixture uses Render PostgreSQL, an existing account, an email address belonging
to a person, or the public preview's mutation endpoints.
"""
import os
import tempfile
import unittest
import uuid
from contextlib import ExitStack
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, HTTPException, Request, Response
from app import admin_routes, cms_access, cms_routes, seo_routes, user_auth


class AuthenticatedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack()
        self.addCleanup(self.stack.close)
        self.tmp=self.stack.enter_context(tempfile.TemporaryDirectory(prefix="atlas-auth-flow-"))
        self.stack.enter_context(patch.dict(os.environ,{"ATLAS_BOOTSTRAP_ADMIN_PASSWORD":""}))
        self.stack.enter_context(patch.object(user_auth,"PG_URL",""))
        self.stack.enter_context(patch.object(user_auth,"SQLITE_DEMO",True))
        self.stack.enter_context(patch.object(user_auth,"SQLITE_FILE",str(Path(self.tmp)/"auth.sqlite3")))
        self.stack.enter_context(patch.object(user_auth,"READY",False))
        self.stack.enter_context(patch.object(cms_access,"ROLE_READY",False))
        self.stack.enter_context(patch.object(cms_routes,"CMS_READY",False))
        self.owners=set()
        self.stack.enter_context(patch.object(cms_access,"OWNER_IDS",self.owners))
        self.stack.enter_context(patch.object(admin_routes,"ADMIN_IDS",self.owners))
        self.base={"sites":{},"modules":{},"patterns":{},"articles":{}}
        self.stack.enter_context(patch.object(cms_routes,"base_maps",return_value=self.base))
        self.stack.enter_context(patch.object(cms_routes.seo_routes,"catalog",
                                              side_effect=lambda:cms_routes.merge_catalog(self.base)))
        self.stack.enter_context(patch("app.cms_schedule.publish_due",return_value=0))
        cms_routes.invalidate()
        self.addCleanup(cms_routes.invalidate)
        app=FastAPI()
        # The auth module mounts an APIRouter. Capture its child endpoints
        # explicitly: this also works with lightweight FastAPI route wrappers.
        with patch.object(app,"include_router",wraps=app.include_router) as mount:
            user_auth.register_auth_routes(app)
        auth_router=mount.call_args.args[0]
        cms_routes.register_cms_routes(app)
        admin_routes.register_admin_routes(app)
        all_routes=[(route.path,route) for route in app.routes
                    if getattr(route,"methods",None)]
        all_routes.extend((route.path,route)
                          for route in auth_router.routes
                          if getattr(route,"methods",None))
        self.endpoints={(url,method):route.endpoint for url,route in all_routes
                        for method in route.methods}

    def call(self,method,path,*args):
        return self.endpoints[(path,method)](*args)

    def request(self,method="GET",token=None,csrf=None,origin="https://atlas.test"):
        headers=[(b"host",b"atlas.test")]
        if origin is not None:headers.append((b"origin",origin.encode()))
        if token is not None:
            headers.append((b"cookie",("atlas_session="+token).encode()))
        if csrf is not None:
            headers.append((b"x-csrf-token",csrf.encode()))
        return Request({"type":"http","method":method,"path":"/","scheme":"https",
                        "headers":headers,"query_string":b"",
                        "client":("127.0.0.1",10101),"server":("atlas.test",443)})

    def register(self,account):
        response=Response()
        email=account+"@example.test"
        result=self.call("POST","/api/auth/register",
                         user_auth.Register(email=email,display_name="Atlas "+account,
                                            password="Test-Password-234!"),
                         self.request("POST"),response)
        cookie=SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        token=cookie[user_auth.COOKIE].value
        self.assertGreaterEqual(len(token),32)
        self.assertIn("httponly",response.headers["set-cookie"].lower())
        self.assertIn("secure",response.headers["set-cookie"].lower())
        return {"id":result["user"]["id"],"email":email,"token":token,"csrf":result["csrf_token"]}

    def authed(self,account,method="GET",csrf=True,origin="https://atlas.test"):
        return self.request(method,account["token"],
                            account["csrf"] if csrf else None,origin)

    def grant(self,account,role,actor):
        cms_access.ensure_roles()
        with user_auth.db() as db:
            db.execute("""INSERT INTO atlas_cms_roles(user_id,role,granted_by,updated_at)
                          VALUES(?,?,?,?)""",(account["id"],role,actor["id"],user_auth.now()))

    @staticmethod
    def draft(slug,summary):
        return {"id":slug,"name":"QA Reference","url":"https://example.org",
                "sector":"Industrial","summary":summary,"screenshot_url":""}

    def test_loopback_http_is_only_allowed_for_disposable_sqlite(self):
        local=self.request("POST",origin="http://localhost:8765")
        local.scope["headers"]=[(b"host",b"localhost:8765"),
                                (b"origin",b"http://localhost:8765")]
        user_auth.origin(local)
        with patch.object(user_auth,"SQLITE_DEMO",False):
            with self.assertRaises(HTTPException) as denied:
                user_auth.origin(local)
            self.assertEqual(denied.exception.status_code,403)
        with patch.object(user_auth,"PG_URL","postgresql://example.invalid/test"):
            with self.assertRaises(HTTPException) as denied:
                user_auth.origin(local)
            self.assertEqual(denied.exception.status_code,403)
        with self.assertRaises(HTTPException) as denied:
            user_auth.origin(self.request("POST",origin="http://attacker.example"))
        self.assertEqual(denied.exception.status_code,403)

    def test_session_cookie_login_logout_and_csrf_guards(self):
        owner=self.register("owner")
        self.owners.add(owner["id"])
        identity=self.call("GET","/api/auth/me",self.authed(owner),Response())
        self.assertTrue(identity["authenticated"])
        self.assertEqual(identity["user"]["id"],owner["id"])
        self.assertNotIn("password_hash",identity["user"])
        with self.assertRaises(HTTPException) as missing:
            self.call("POST","/api/auth/logout",self.authed(owner,"POST",csrf=False),Response())
        self.assertEqual(missing.exception.status_code,403)
        with self.assertRaises(HTTPException) as wrong_origin:
            self.call("POST","/api/auth/logout",
                      self.authed(owner,"POST",origin="https://attacker.example"),Response())
        self.assertEqual(wrong_origin.exception.status_code,403)
        self.assertTrue(self.call("POST","/api/auth/logout",self.authed(owner,"POST"),Response())["ok"])
        self.assertFalse(self.call("GET","/api/auth/me",self.authed(owner),Response())["authenticated"])
        with self.assertRaises(HTTPException) as invalid:
            self.call("POST","/api/auth/login",user_auth.Login(
                email=owner["email"],password="invalid"),self.request("POST"),Response())
        self.assertEqual(invalid.exception.status_code,401)
        login=self.call("POST","/api/auth/login",user_auth.Login(
            email=owner["email"],password="Test-Password-234!"),self.request("POST"),Response())
        self.assertEqual(login["user"]["id"],owner["id"])
        self.assertTrue(login["authenticated"])

    def test_roles_protect_actual_draft_review_publish_and_public_snapshot(self):
        owner=self.register("owner")
        editor=self.register("editor")
        reviewer=self.register("reviewer")
        ordinary=self.register("ordinary")
        self.owners.add(owner["id"])
        self.grant(editor,"editor",owner)
        self.grant(reviewer,"reviewer",owner)
        slug="verified-qa-case"
        payload=self.draft(slug,"Only a private draft")
        create=cms_routes.Create(kind="site",slug=slug,payload=payload)
        with self.assertRaises(HTTPException) as guest:
            self.call("POST","/api/admin/content",create,self.request("POST"))
        self.assertEqual(guest.exception.status_code,401)
        with self.assertRaises(HTTPException) as ordinary_denied:
            self.call("POST","/api/admin/content",create,self.authed(ordinary,"POST"))
        self.assertEqual(ordinary_denied.exception.status_code,403)
        with self.assertRaises(HTTPException) as missing_csrf:
            self.call("POST","/api/admin/content",create,self.authed(editor,"POST",csrf=False))
        self.assertEqual(missing_csrf.exception.status_code,403)
        with self.assertRaises(HTTPException) as reviewer_denied:
            self.call("POST","/api/admin/content",create,self.authed(reviewer,"POST"))
        self.assertEqual(reviewer_denied.exception.status_code,403)
        created=self.call("POST","/api/admin/content",create,self.authed(editor,"POST"))
        self.assertEqual(created["status"],"draft")
        self.assertNotIn(slug,[x["id"] for x in cms_routes.public_payload("site")["sites"]])
        submitted=self.call("POST","/api/admin/content/{kind}/{slug}/submit",
                            "site",slug,cms_routes.Change(expected_revision=1),
                            self.authed(editor,"POST"))
        self.assertEqual(submitted["status"],"review")
        with self.assertRaises(HTTPException) as edit_publish:
            self.call("POST","/api/admin/content/{kind}/{slug}/publish",
                      "site",slug,cms_routes.Change(expected_revision=submitted["revision"]),
                      self.authed(editor,"POST"))
        self.assertEqual(edit_publish.exception.status_code,403)
        with self.assertRaises(HTTPException) as stale:
            self.call("POST","/api/admin/content/{kind}/{slug}/publish",
                      "site",slug,cms_routes.Change(expected_revision=1),
                      self.authed(reviewer,"POST"))
        self.assertEqual(stale.exception.status_code,409)
        self.assertNotIn(slug,[x["id"] for x in cms_routes.public_payload("site")["sites"]])
        published=self.call("POST","/api/admin/content/{kind}/{slug}/publish",
                            "site",slug,cms_routes.Change(expected_revision=submitted["revision"]),
                            self.authed(reviewer,"POST"))
        self.assertEqual(published["status"],"published")
        public=next(x for x in cms_routes.public_payload("site")["sites"] if x["id"]==slug)
        self.assertEqual(public["summary"],"Only a private draft")
        with self.assertRaises(HTTPException) as reviewer_edit:
            self.call("PUT","/api/admin/content/{kind}/{slug}",
                      "site",slug,cms_routes.Draft(
                          expected_revision=published["revision"],
                          payload=self.draft(slug,"Never from reviewer")),
                      self.authed(reviewer,"PUT"))
        self.assertEqual(reviewer_edit.exception.status_code,403)
        updated=self.call("PUT","/api/admin/content/{kind}/{slug}",
                          "site",slug,cms_routes.Draft(
                              expected_revision=published["revision"],
                              payload=self.draft(slug,"Unreviewed changes")),
                          self.authed(editor,"PUT"))
        self.assertEqual(updated["status"],"draft")
        public=next(x for x in cms_routes.public_payload("site")["sites"] if x["id"]==slug)
        self.assertEqual(public["summary"],"Only a private draft")

    def test_all_four_seo_content_types_publish_only_after_approval(self):
        """HTTP SEO output follows actual CMS snapshots, not any unreviewed draft.

        This workflow uses the same disposable SQLite fixture as auth tests.
        No production users, PostgreSQL rows, or preview pages are modified.
        """
        owner=self.register("seo-owner")
        editor=self.register("seo-editor")
        reviewer=self.register("seo-reviewer")
        self.owners.add(owner["id"])
        self.grant(editor,"editor",owner)
        self.grant(reviewer,"reviewer",owner)
        categories=cms_routes.article_categories()
        self.assertTrue(categories,"At least one published article category is required")
        source_kind=[
            ("site","qa-seo-site","websites",{
                "name":"Research Source", "url":"https://example.org",
                "sector":"Manufacturing", "summary":"Original industry observation",
                "screenshot_url":"/screenshots/sites/vast.webp"}),
            ("module","qa-seo-module","sections",{
                "title":"Evidence Hero", "site_id":"qa-seo-site","category":"Hero",
                "lesson":"Show verifiable product context",
                "screenshot_url":"/screenshots/modules/qa-seo-module.webp"}),
            ("pattern","qa-seo-pattern","patterns",{
                "title":"Proof-first design", "family":"Navigation",
                "question":"How do buyers evaluate a product?",
                "principle":"Show sources near claims",
                "modules":["qa-seo-module"]}),
            ("article","qa-seo-article","insights",{
                "title":"How to evaluate B2B designs",
                "subtitle":"Original editorial introduction",
                "category":categories[0]["id"],"author":"B2B Atlas 编辑部",
                "cover_site":"qa-seo-site",
                "sections":[{"title":"Research findings",
                             "blocks":[{"type":"paragraph",
                                        "text":"Evidence-backed case analysis with original context."}]}],
                "references":[["website","qa-seo-site"],
                              ["module","qa-seo-module"],["pattern","qa-seo-pattern"]]
            })
        ]
        from fastapi import FastAPI
        seo_app=FastAPI()
        seo_routes.register_seo_routes(seo_app)
        sitemap=next(route.endpoint for route in seo_app.routes
                     if getattr(route,"path","")=="/sitemap.xml")
        def html(route):
            return seo_routes.seo_document(route).body.decode("utf-8")
        def sitemap_text():
            return sitemap().body.decode("utf-8")
        for kind,slug,route,data in source_kind:
            with self.subTest(kind=kind):
                original_title="Approved "+kind+" research"
                original_desc="Approved "+kind+" SEO summary based on published evidence."
                payload={**data,"id":slug,"seo_title":original_title,
                         "seo_description":original_desc,
                         "seo_keywords":"B2B, documented research",
                         "seo_image":"/screenshots/sites/vast.webp"}
                path=route+"/"+slug
                created=self.call("POST","/api/admin/content",
                                  cms_routes.Create(kind=kind,slug=slug,payload=payload),
                                  self.authed(editor,"POST"))
                self.assertEqual(created["status"],"draft")
                self.assertEqual(seo_routes.seo_document(path).status_code,404)
                self.assertNotIn(path,sitemap_text())
                self.assertNotIn(original_desc,html(route))
                submitted=self.call("POST","/api/admin/content/{kind}/{slug}/submit",
                                    kind,slug,cms_routes.Change(expected_revision=created["revision"]),
                                    self.authed(editor,"POST"))
                self.assertEqual(submitted["status"],"review")
                self.assertEqual(seo_routes.seo_document(path).status_code,404)
                published=self.call("POST","/api/admin/content/{kind}/{slug}/publish",
                                    kind,slug,cms_routes.Change(expected_revision=submitted["revision"]),
                                    self.authed(reviewer,"POST"))
                self.assertEqual(published["status"],"published")
                response=seo_routes.seo_document(path)
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.headers["X-Robots-Tag"],"index, follow")
                body=response.body.decode("utf-8")
                self.assertIn(original_title,body)
                self.assertIn(original_desc,body)
                self.assertIn('name="description"',body)
                self.assertIn('rel="canonical"',body)
                self.assertIn('application/ld+json',body)
                self.assertIn('"keywords": "B2B, documented research"',body)
                self.assertIn("https://b2b-design-atlas-preview.onrender.com/screenshots/sites/vast.webp",body)
                self.assertIn(path,sitemap_text())
                pending={**payload,"seo_title":"UNREVIEWED "+original_title,
                         "seo_description":"UNREVIEWED "+original_desc}
                updated=self.call("PUT","/api/admin/content/{kind}/{slug}",
                                  kind,slug,cms_routes.Draft(
                                      expected_revision=published["revision"],
                                      payload=pending),self.authed(editor,"PUT"))
                self.assertEqual(updated["status"],"draft")
                body=html(path)
                self.assertIn(original_title,body)
                self.assertIn(original_desc,body)
                self.assertNotIn("UNREVIEWED",body)
                self.assertIn(path,sitemap_text())
        # The private draft of one record never changes its published snapshot.
        kind,slug,route,_=source_kind[-1]
        archived=self.call("POST","/api/admin/content/{kind}/{slug}/archive",
                           kind,slug,cms_routes.Change(expected_revision=4),
                           self.authed(reviewer,"POST"))
        self.assertEqual(archived["status"],"archived")
        self.assertEqual(seo_routes.seo_document(route+"/"+slug).status_code,404)
        self.assertNotIn(route+"/"+slug,sitemap_text())

    def test_favorites_are_isolated_and_require_valid_csrf(self):
        user_a=self.register("collector-a")
        user_b=self.register("collector-b")
        item=user_auth.Item(collection="saved",key="site:verified-reference")
        with self.assertRaises(HTTPException) as guest:
            self.call("POST","/api/me/library",item,self.request("POST"))
        self.assertEqual(guest.exception.status_code,401)
        with self.assertRaises(HTTPException) as csrf:
            self.call("POST","/api/me/library",item,self.authed(user_a,"POST",csrf=False))
        self.assertEqual(csrf.exception.status_code,403)
        self.assertTrue(self.call("POST","/api/me/library",item,self.authed(user_a,"POST"))["ok"])
        a=self.call("GET","/api/me/library",self.authed(user_a),Response())
        b=self.call("GET","/api/me/library",self.authed(user_b),Response())
        self.assertIn("site:verified-reference",a["saved"])
        self.assertNotIn("site:verified-reference",b["saved"])
        self.call("DELETE","/api/me/library/{collection}/{kind}/{slug}",
                  "saved","site","verified-reference",self.authed(user_a,"DELETE"))
        self.assertNotIn("site:verified-reference",
                         self.call("GET","/api/me/library",self.authed(user_a),Response())["saved"])


if __name__=="__main__":
    unittest.main()
