"""V52.6 · Real CMS route + SQL integration through draft, review and public snapshots.

Uses exactly the backend endpoint functions and an isolated SQLite database;
never requires or alters the Render PostgreSQL instance.
"""
import base64
import copy
import json
import uuid
import unittest
from contextlib import ExitStack
from unittest.mock import patch
from fastapi import FastAPI, HTTPException
from app import cms_routes
from test_cms_v514 import DB


class CMSReleaseFlowTests(unittest.TestCase):
    def setUp(self):
        self.db=DB()
        self.uid=str(uuid.uuid4())
        self.db.execute("INSERT INTO atlas_users(id,email,display_name,created_at) VALUES(?,?,?,?)",
                        (self.uid,"qa@example.com","QA Editor","2026-11-25"))
        self.base={
            "sites":{"atlas-source":{
                "id":"atlas-source","name":"Original Example",
                "url":"https://example.org","sector":"Industrial",
                "summary":"Original published summary",
                "screenshot_url":"/screenshots/sites/atlas-source.webp"}},
            "modules":{},"patterns":{},"articles":{}
        }
        self.stack=ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(cms_routes.user_auth,"db",return_value=self.db))
        self.stack.enter_context(patch.object(cms_routes,"ensure_cms"))
        self.stack.enter_context(patch.object(cms_routes,"base_maps",return_value=self.base))
        self.stack.enter_context(patch.object(cms_routes,"require_admin",
                                             return_value={"user_id":self.uid}))
        self.stack.enter_context(patch.object(cms_routes,"article_categories",
                                             return_value=[{"id":"research","name":"Research"}]))
        self.stack.enter_context(patch.object(cms_routes.seo_routes,"catalog",
                            side_effect=lambda: cms_routes.merge_catalog(self.base)))
        self.stack.enter_context(patch("app.cms_schedule.publish_due",return_value=0))
        cms_routes.invalidate()
        self.addCleanup(cms_routes.invalidate)
        app=FastAPI()
        cms_routes.register_cms_routes(app)
        self.routes={(route.path,method):route.endpoint for route in app.routes
                     for method in (route.methods or set())}

    def route(self,method,path,*args):
        return self.routes[(path,method)](*args)

    def create(self,kind,slug,payload):
        return self.route("POST","/api/admin/content",
            cms_routes.Create(kind=kind,slug=slug,payload=payload),object())

    def save(self,kind,slug,payload,revision):
        return self.route("PUT","/api/admin/content/{kind}/{slug}",
            kind,slug,cms_routes.Draft(expected_revision=revision,payload=payload),object())

    def change(self,kind,slug,action,revision,reason=None):
        data=(cms_routes.RejectDecision(expected_revision=revision,reason=reason)
              if action=="reject" else cms_routes.Change(expected_revision=revision))
        return self.route("POST","/api/admin/content/{kind}/{slug}/"+action,
                          kind,slug,data,object())

    def detail(self,kind,slug):
        return self.route("GET","/api/admin/content/{kind}/{slug}",kind,slug,object())

    def public(self,kind):
        items=cms_routes.public_payload(kind)
        return items["sites"] if kind=="site" else items["modules"] if kind=="module" else items if kind=="pattern" else items["articles"]

    @staticmethod
    def new_site(slug,summary="New private draft",**extras):
        return dict(id=slug,name="New Atlas Example",url="https://example.org",
                    sector="Industrial",summary=summary,screenshot_url="",**extras)

    def test_existing_source_baseline_remains_visible_and_reviewable(self):
        slug="atlas-source"
        original=copy.deepcopy(self.base["sites"][slug])
        self.assertEqual(self.detail("site",slug)["published"],original)
        draft={**original,"summary":"Changed privately"}
        saved=self.save("site",slug,draft,0)
        self.assertEqual(saved["status"],"draft")
        detail=self.detail("site",slug)
        self.assertEqual(detail["published"],original)
        self.assertEqual(detail["payload"]["summary"],"Changed privately")
        self.assertEqual(next(x for x in self.public("site") if x["id"]==slug)["summary"],
                         original["summary"])
        submitted=self.change("site",slug,"submit",saved["revision"])
        self.assertEqual(submitted["status"],"review")
        self.assertEqual(self.detail("site",slug)["published"],original)
        published=self.change("site",slug,"publish",submitted["revision"])
        self.assertEqual(published["status"],"published")
        self.assertEqual(next(x for x in self.public("site") if x["id"]==slug)["summary"],
                         "Changed privately")
        self.assertEqual(self.detail("site",slug)["published"]["summary"],"Changed privately")
        # Editing an already published item must not expose its new draft.
        pending=self.save("site",slug,{**draft,"summary":"Unreviewed second edit"},published["revision"])
        self.assertEqual(pending["status"],"draft")
        self.assertEqual(next(x for x in self.public("site") if x["id"]==slug)["summary"],
                         "Changed privately")
        self.assertEqual(self.detail("site",slug)["published"]["summary"],"Changed privately")

    def test_archived_original_never_resurrects_as_public_or_review_baseline(self):
        slug="atlas-source"
        original=copy.deepcopy(self.base["sites"][slug])
        first=self.save("site",slug,{**original,"name":"Published update"},0)
        reviewed=self.change("site",slug,"submit",first["revision"])
        published=self.change("site",slug,"publish",reviewed["revision"])
        archived=self.change("site",slug,"archive",published["revision"])
        self.assertEqual(archived["status"],"archived")
        self.assertFalse(any(x["id"]==slug for x in self.public("site")))
        new=self.save("site",slug,{**original,"name":"Private rework"},archived["revision"])
        self.assertEqual(new["status"],"draft")
        self.assertIsNone(self.detail("site",slug)["published"])
        self.assertFalse(any(x["id"]==slug for x in self.public("site")))

    def test_new_site_lifecycle_guards_and_revision_conflicts(self):
        slug="release-flow"
        payload=self.new_site(slug)
        created=self.create("site",slug,payload)
        self.assertEqual(created["revision"],1)
        self.assertFalse(any(x["id"]==slug for x in self.public("site")))
        with self.assertRaises(HTTPException) as err:
            self.change("site",slug,"publish",1)
        self.assertEqual(err.exception.status_code,409)
        with self.assertRaises(HTTPException) as err:
            self.create("site",slug,payload)
        self.assertEqual(err.exception.status_code,409)
        with self.assertRaises(HTTPException) as err:
            self.save("site",slug,{**payload,"summary":"Too old"},0)
        self.assertEqual(err.exception.status_code,409)
        review=self.change("site",slug,"submit",1)
        self.assertEqual(review["status"],"review")
        self.assertFalse(any(x["id"]==slug for x in self.public("site")))
        released=self.change("site",slug,"publish",review["revision"])
        self.assertEqual(released["status"],"published")
        self.assertTrue(any(x["id"]==slug for x in self.public("site")))
        self.assertEqual([x["action"] for x in self.db.all(
            "SELECT action FROM atlas_cms_history WHERE kind=? AND slug=? ORDER BY revision",
            ("site",slug))],["create","submit","publish"])

    def test_media_upload_gallery_release_and_delete_reference_guards(self):
        image=base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMBAeKf3UYAAAAASUVORK5CYII=")
        uploaded=self.route("POST","/api/admin/media",
                           cms_routes.MediaUpload(name="hero.png",mime="image/png",
                            content=base64.b64encode(image).decode("ascii")),object())
        url=uploaded["url"]
        self.assertEqual(self.route("GET","/api/media/{media_id}",uploaded["id"]).body,image)
        slug="multi-image"
        payload=self.new_site(slug,screenshot_url=url,gallery=[{"url":url,"label":"Product page"}])
        # The explicit front cover may also be a gallery image, but gallery entries cannot duplicate each other.
        self.create("site",slug,payload)
        review=self.change("site",slug,"submit",1)
        self.change("site",slug,"publish",review["revision"])
        published=next(x for x in self.public("site") if x["id"]==slug)
        self.assertEqual(published["gallery"][0]["url"],url)
        listing=self.route("GET","/api/admin/media",object())["items"]
        self.assertEqual(listing[0]["usage_count"],1)
        with self.assertRaises(HTTPException) as err:
            self.route("DELETE","/api/admin/media/{media_id}",uploaded["id"],object())
        self.assertEqual(err.exception.status_code,409)
        old=self.detail("site",slug)
        blank={**old["payload"],"gallery":[],"screenshot_url":""}
        updated=self.save("site",slug,blank,old["revision"])
        # Published snapshot continues using the uploaded photo.
        with self.assertRaises(HTTPException):
            self.route("DELETE","/api/admin/media/{media_id}",uploaded["id"],object())
        reviewed=self.change("site",slug,"submit",updated["revision"])
        self.change("site",slug,"publish",reviewed["revision"])
        self.assertTrue(self.route("DELETE","/api/admin/media/{media_id}",uploaded["id"],object())["ok"])

    def test_missing_media_ref_cannot_publish(self):
        slug="orphan-image"
        payload=self.new_site(slug,screenshot_url="/api/media/"+str(uuid.uuid4()))
        self.create("site",slug,payload)
        review=self.change("site",slug,"submit",1)
        with self.assertRaises(HTTPException) as err:
            self.change("site",slug,"publish",review["revision"])
        self.assertEqual(err.exception.status_code,422)
        self.assertEqual(self.detail("site",slug)["status"],"review")
        self.assertFalse(any(x["id"]==slug for x in self.public("site")))

    def test_reviewer_rejection_keeps_previous_public_version(self):
        slug="atlas-source"
        original=copy.deepcopy(self.base["sites"][slug])
        saved=self.save("site",slug,{**original,"summary":"Unacceptable revision"},0)
        reviewed=self.change("site",slug,"submit",saved["revision"])
        rejected=self.change("site",slug,"reject",reviewed["revision"],
                             reason="Please verify the screenshots and links.")
        self.assertEqual(rejected["status"],"draft")
        self.assertEqual(self.detail("site",slug)["published"]["summary"],original["summary"])
        self.assertEqual(next(x for x in self.public("site") if x["id"]==slug)["summary"],original["summary"])
        notes=self.db.all("SELECT reason FROM atlas_cms_review_notes WHERE kind='site' AND slug=?",(slug,))
        self.assertEqual(len(notes),1)
        self.assertIn("verify",notes[0]["reason"])

    def test_all_four_kinds_published_in_dependency_order(self):
        site="dependency-site"
        module="dependency-module"
        pattern="dependency-pattern"
        article="dependency-article"
        entries=[
            ("site",site,self.new_site(site)),
            ("module",module,dict(id=module,title="Reference module",site_id=site,
                                  category="Hero",lesson="Make buyer paths clear",screenshot_url="")),
            ("pattern",pattern,dict(id=pattern,title="Decision clarity",family="Compare",
                                    question="How to decide?",principle="Show essential differences",
                                    modules=[module])),
            ("article",article,dict(id=article,title="Design research",subtitle="Practical findings",
                                    category="research",author="Atlas Editorial",
                                    sections=[{"title":"Introduction","paragraphs":["Buyer priorities shape the design."]}]))
        ]
        for kind,slug,payload in entries:
            self.create(kind,slug,payload)
            self.assertFalse(any(x["id"]==slug for x in self.public(kind)))
            submitted=self.change(kind,slug,"submit",1)
            released=self.change(kind,slug,"publish",submitted["revision"])
            self.assertEqual(released["status"],"published")
            self.assertTrue(any(x["id"]==slug for x in self.public(kind)))
        self.assertIn(site,cms_routes.seo_routes.catalog()["sites"])
        self.assertIn(module,cms_routes.seo_routes.catalog()["modules"])


if __name__=="__main__":
    unittest.main()
