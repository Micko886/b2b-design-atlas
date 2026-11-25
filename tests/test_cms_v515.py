"""V51.15 · API workflow integration + static frontend startup checks.

Exercises real CMS/role/schedule route functions against transactional SQLite.
No production data, credentials or fabricated browser claims.
"""
from __future__ import annotations

import re
import unittest
import uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI, HTTPException

from app import cms_routes, cms_access, cms_team, cms_schedule, user_auth
from test_cms_v514 import DB

STATIC=Path("/srv/atlas/static")

class MockRequest:
    headers={"origin":"https://atlas.test","host":"atlas.test","x-csrf-token":"test"}

class CMSWorkflowIntegration(unittest.TestCase):
    def setUp(self):
        self.db=DB()
        self.owner=str(uuid.uuid4())
        self.editor=str(uuid.uuid4())
        self.reviewer=str(uuid.uuid4())
        for uid,role in ((self.owner,None),(self.editor,"editor"),(self.reviewer,"reviewer")):
            self.db.execute("INSERT INTO atlas_users VALUES(?,?,?,?)",
                (uid,uid+"@example.invalid",role or "Owner","2026-11-25"))
            if role:
                self.db.execute("INSERT INTO atlas_cms_roles VALUES(?,?,?,?)",
                    (uid,role,self.owner,"2026-11-25"))
        self.actor={"user_id":self.owner}
        self.app=FastAPI()
        cms_routes.register_cms_routes(self.app)
        cms_team.register_team_routes(self.app)
        cms_schedule.register_schedule_routes(self.app)
        self.patches=[
            patch.object(cms_access,"OWNER_IDS",{self.owner}),
            patch.object(cms_access,"ensure_roles"),
            patch.object(cms_routes,"ensure_cms"),
            patch.object(user_auth,"db",return_value=self.db),
            patch.object(user_auth,"required",side_effect=lambda request:self.actor),
            patch.object(user_auth,"origin"),
            patch.object(user_auth,"check_csrf"),
            patch.object(cms_routes,"invalidate"),
            patch.object(cms_routes,"base_item",return_value=None)
        ]
        for p in self.patches:p.start()
        self.addCleanup(lambda:[p.stop() for p in reversed(self.patches)])
        self.req=MockRequest()
        self.slug="qa-workflow"
        self.payload={"id":self.slug,"name":"Test Manufacturer",
                      "url":"https://example.invalid","sector":"Manufacturing",
                      "summary":"Initial QA description"}

    def route(self,pattern,method):
        return next(x.endpoint for x in self.app.routes
                    if getattr(x,"path",None)==pattern and method in (getattr(x,"methods",set()) or set()))

    def as_actor(self,role):
        self.actor={"user_id":{"owner":self.owner,"editor":self.editor,
                               "reviewer":self.reviewer}[role]}

    def create(self):
        self.as_actor("editor")
        r=self.route("/api/admin/content","POST")(
           cms_routes.Create(kind="site",slug=self.slug,payload=self.payload),self.req)
        self.assertEqual(r["revision"],1)
        return r

    def test_editor_draft_review_reviewer_publish_and_public_snapshot(self):
        self.create()
        save=self.route("/api/admin/content/{kind}/{slug}","PUT")
        changed={**self.payload,"summary":"Updated by editor"}
        saved=save("site",self.slug,cms_routes.Draft(payload=changed,expected_revision=1),self.req)
        self.assertEqual(saved["revision"],2)
        with self.assertRaises(HTTPException) as err:
            save("site",self.slug,cms_routes.Draft(payload=changed,expected_revision=1),self.req)
        self.assertEqual(err.exception.status_code,409)
        submit=self.route("/api/admin/content/{kind}/{slug}/submit","POST")
        self.assertEqual(submit("site",self.slug,cms_routes.Change(expected_revision=2),self.req)["status"],"review")
        publish=self.route("/api/admin/content/{kind}/{slug}/publish","POST")
        with self.assertRaises(HTTPException) as err:
            publish("site",self.slug,cms_routes.Change(expected_revision=3),self.req)
        self.assertEqual(err.exception.status_code,403)
        self.as_actor("reviewer")
        with patch.object(cms_routes,"verify_links"):
            result=publish("site",self.slug,cms_routes.Change(expected_revision=3),self.req)
        self.assertEqual(result["status"],"published")
        row=self.db.one("SELECT * FROM atlas_cms_entries WHERE slug=?",(self.slug,))
        self.assertEqual(row["revision"],4)
        self.assertIn("Updated by editor",row["published_json"])
        self.as_actor("editor")
        newer={**changed,"summary":"Not yet reviewed"}
        saved=save("site",self.slug,cms_routes.Draft(payload=newer,expected_revision=4),self.req)
        self.assertEqual(saved["status"],"draft")
        row=self.db.one("SELECT status,draft_json,published_json FROM atlas_cms_entries WHERE slug=?",(self.slug,))
        self.assertEqual(row["status"],"draft")
        self.assertNotIn("Not yet reviewed",row["published_json"])

    def test_review_return_records_reason_without_changing_public_version(self):
        self.create()
        self.route("/api/admin/content/{kind}/{slug}/submit","POST")(
            "site",self.slug,cms_routes.Change(expected_revision=1),self.req)
        self.as_actor("reviewer")
        rejected=self.route("/api/admin/content/{kind}/{slug}/reject","POST")(
            "site",self.slug,cms_routes.RejectDecision(
                expected_revision=2,reason="Please clarify the visual design evidence"),self.req)
        self.assertEqual(rejected["status"],"draft")
        reason=self.db.one("SELECT reason FROM atlas_cms_review_notes WHERE slug=?",(self.slug,))
        self.assertIn("visual design evidence",reason["reason"])
        self.assertEqual(self.db.one("SELECT published_json FROM atlas_cms_entries WHERE slug=?",(self.slug,))["published_json"],None)

    def test_reviewer_cannot_save_and_editor_cannot_grant_roles(self):
        self.create()
        self.as_actor("reviewer")
        with self.assertRaises(HTTPException) as err:
            self.route("/api/admin/content/{kind}/{slug}","PUT")(
                "site",self.slug,cms_routes.Draft(payload=self.payload,expected_revision=1),self.req)
        self.assertEqual(err.exception.status_code,403)
        self.as_actor("editor")
        with self.assertRaises(HTTPException) as err:
            self.route("/api/admin/team/role","PUT")(
                cms_team.RoleGrant(user_id=self.reviewer,role="editor"),self.req)
        self.assertEqual(err.exception.status_code,403)

    def test_reviewer_scheduling_and_editor_save_invalidates_queue(self):
        self.create()
        self.route("/api/admin/content/{kind}/{slug}/submit","POST")(
            "site",self.slug,cms_routes.Change(expected_revision=1),self.req)
        self.as_actor("reviewer")
        dt=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()
        with patch.object(cms_routes,"verify_links"):
            result=self.route("/api/admin/content/{kind}/{slug}/schedule","POST")(
                "site",self.slug,cms_schedule.ScheduleRequest(expected_revision=2,publish_at=dt),self.req)
        self.assertEqual(result["status"],"pending")
        self.as_actor("editor")
        self.route("/api/admin/content/{kind}/{slug}","PUT")(
            "site",self.slug,cms_routes.Draft(payload=self.payload,expected_revision=2),self.req)
        self.assertEqual(self.db.one("SELECT status FROM atlas_cms_schedules")["status"],"stale")
        with patch.object(cms_routes,"verify_links"):
            self.assertEqual(cms_schedule.publish_due(force=True),0)
        self.assertEqual(self.db.one("SELECT status FROM atlas_cms_entries")["status"],"draft")

    def test_owner_grant_and_revoke_role_takes_effect_immediately(self):
        self.as_actor("owner")
        grant=self.route("/api/admin/team/role","PUT")
        revoke=self.route("/api/admin/team/role/{user_id}","DELETE")
        grant(cms_team.RoleGrant(user_id=self.editor,role="reviewer"),self.req)
        self.assertTrue(cms_access.can({"user_id":self.editor},"review"))
        self.assertFalse(cms_access.can({"user_id":self.editor},"edit"))
        revoke(self.editor,self.req)
        self.assertFalse(cms_access.can({"user_id":self.editor},"view"))
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM atlas_cms_role_history")["n"],2)

    def test_protected_export_forbidden_to_reviewer_and_editor(self):
        export=self.route("/api/admin/content/export","GET")
        for role in ("editor","reviewer"):
            self.as_actor(role)
            with self.subTest(role=role),self.assertRaises(HTTPException) as err:
                export(self.req)
            self.assertEqual(err.exception.status_code,403)

    def test_schedule_api_cannot_be_used_by_editor(self):
        self.create()
        with self.assertRaises(HTTPException) as err:
            self.route("/api/admin/content/{kind}/{slug}/schedule","POST")(
                "site",self.slug,cms_schedule.ScheduleRequest(expected_revision=1,
                publish_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()),self.req)
        self.assertEqual(err.exception.status_code,403)

class CMSFrontendContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=(STATIC/"assets/cms.js").read_text(encoding="utf-8")
        cls.html=(STATIC/"cms.html").read_text(encoding="utf-8")

    def test_sidebar_selector_uses_collection_not_single_node(self):
        self.assertIn("$$('.side-nav a[href=",self.js)
        self.assertNotIn(" $('.side-nav a[href=",self.js)

    def test_every_static_workspace_control_exists(self):
        for name in ("cms-new","cms-export","cms-team-open","cms-schedules-open",
                     "cms-review-shortcut","cms-media-open","cms-tags-open",
                     "cms-team-form","cms-team-revoke","cms-team-grant",
                     "cms-schedule-items","cms-schedule-refresh"):
            with self.subTest(name=name):
                self.assertIn('id="'+name+'"',self.html)

    def test_dynamic_reviewer_controls_use_role_checks(self):
        self.assertIn("const reviewActions=can('review')",self.js)
        self.assertIn("const isPreview=mode==='preview',values=item.payload||{},editable=can('edit')",self.js)
        self.assertIn("if(!can('review')||state.busy||!state.selected)return",self.js)

    def test_editor_role_screen_initializes_before_catalog_render(self):
        role=self.js.index("const role=await api('/api/admin/team/me')")
        set_role=self.js.index("setCmsRole();",role)
        load_catalog=self.js.index("await loadKind();",set_role)
        self.assertLess(role,set_role)
        self.assertLess(set_role,load_catalog)

    def test_autosave_and_revision_lock_remain_wired(self):
        self.assertIn("setTimeout(()=>persistDraft(true),3200)",self.js)
        self.assertIn("expected_revision:target.revision",self.js)
        self.assertIn("autosavePaused=true",self.js)
        self.assertIn("sessionStorage.setItem(recoveryKey()",self.js)

    def test_scheduling_sends_iso_timezone_and_revision(self):
        self.assertIn("publish_at:date.toISOString()",self.js)
        self.assertIn("expected_revision:item.revision",self.js)
        self.assertIn("data-schedule-cancel",self.js)

    def test_preview_has_no_write_bypass(self):
        self.assertIn("mode=document.body.dataset.cmsMode==='admin'?'admin':'preview'",self.js)
        self.assertIn("if(mode!=='admin'||!state.selected)return",self.js)
        self.assertIn("cms_access", (Path("/srv/atlas/app/cms_routes.py")).read_text(encoding="utf-8"))

if __name__=="__main__":
    unittest.main()
