"""V51.14: release scheduling, owner/editor/reviewer permission and stale guards."""
import sqlite3
import unittest
import uuid
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from fastapi import FastAPI,HTTPException
from app import cms_access,cms_team,cms_schedule,cms_routes

class DB:
    def __init__(self):
        self.conn=sqlite3.connect(":memory:")
        self.conn.row_factory=sqlite3.Row
        self.conn.execute("CREATE TABLE atlas_users(id TEXT PRIMARY KEY,email TEXT,display_name TEXT,created_at TEXT)")
        for statement in cms_routes.SCHEMA:self.conn.execute(statement)
        for statement in cms_access.ROLE_SCHEMA:self.conn.execute(statement)
    def execute(self,sql,args=()):return self.conn.execute(sql,args)
    def one(self,sql,args=()):
        row=self.execute(sql,args).fetchone()
        return dict(row) if row else None
    def all(self,sql,args=()):return [dict(x) for x in self.execute(sql,args).fetchall()]
    def __enter__(self):return self
    def __exit__(self,*args):
        if args and args[0]:self.conn.rollback()
        else:self.conn.commit()

class CMSV514Tests(unittest.TestCase):
    def setUp(self):
        self.db=DB()
        self.now=datetime.now(timezone.utc).replace(microsecond=0)
        self.owner=str(uuid.uuid4())
        self.editor=str(uuid.uuid4())
        self.reviewer=str(uuid.uuid4())
        for uid,name in ((self.owner,"Owner"),(self.editor,"Editor"),(self.reviewer,"Reviewer")):
            self.db.execute("INSERT INTO atlas_users(id,email,display_name,created_at) VALUES(?,?,?,?)",
                (uid,uid+"@example.com",name,self.now.isoformat()))
        self.db.execute("""INSERT INTO atlas_cms_roles(user_id,role,granted_by,updated_at)
             VALUES(?,?,?,?)""",(self.editor,"editor",self.owner,self.now.isoformat()))
        self.db.execute("""INSERT INTO atlas_cms_roles(user_id,role,granted_by,updated_at)
             VALUES(?,?,?,?)""",(self.reviewer,"reviewer",self.owner,self.now.isoformat()))
        self.key="industrial-study"
        self.add_entry()

    def add_entry(self,rev=2,status="review"):
        self.db.execute("""INSERT OR REPLACE INTO atlas_cms_entries
           (kind,slug,draft_json,published_json,status,revision,created_by,updated_by,created_at,updated_at)
           VALUES(?,?,?,? ,?,?,?,?,?,?)""",
           ("article",self.key,'{"id":"industrial-study","title":"New Review"}',
            '{"id":"industrial-study","title":"Old Public"}',status,rev,
            self.owner,self.owner,self.now.isoformat(),self.now.isoformat()))
    def add_schedule(self,rev=2,delta=-1):
        start=(self.now+timedelta(minutes=delta)).isoformat(timespec="seconds")
        self.db.execute("""INSERT OR REPLACE INTO atlas_cms_schedules
            (kind,slug,revision,publish_at,status,created_by,created_at,updated_at,error)
            VALUES(?,?,?,?,'pending',?,?,?,'')""",
            ("article",self.key,rev,start,self.reviewer,self.now.isoformat(),self.now.isoformat()))
    def role_context(self):
        return (
            patch.object(cms_access,"OWNER_IDS",{self.owner}),
            patch.object(cms_access,"ensure_roles"),
            patch.object(cms_access.user_auth,"db",return_value=self.db)
        )

    def test_editor_cannot_publish_and_reviewer_cannot_edit(self):
        p=self.role_context()
        with p[0],p[1],p[2]:
            self.assertTrue(cms_access.can({"user_id":self.owner},"team"))
            self.assertTrue(cms_access.can({"user_id":self.editor},"edit"))
            self.assertFalse(cms_access.can({"user_id":self.editor},"review"))
            self.assertTrue(cms_access.can({"user_id":self.reviewer},"review"))
            self.assertFalse(cms_access.can({"user_id":self.reviewer},"edit"))
            self.assertFalse(cms_access.can({"user_id":str(uuid.uuid4())},"view"))

    def test_publish_requires_review_role_at_api_boundary(self):
        app=FastAPI();cms_routes.register_cms_routes(app)
        end=next(r.endpoint for r in app.routes
           if r.path=="/api/admin/content/{kind}/{slug}/publish")
        with patch.object(cms_routes.user_auth,"required",return_value={"user_id":self.editor}),\
             patch.object(cms_access,"OWNER_IDS",{self.owner}),\
             patch.object(cms_access,"ensure_roles"),\
             patch.object(cms_access.user_auth,"db",return_value=self.db):
            with self.assertRaises(HTTPException) as err:
                end("article",self.key,cms_routes.Change(expected_revision=2),object())
        self.assertEqual(err.exception.status_code,403)

    def test_owner_team_api_only_and_assignment_tracks_audit(self):
        app=FastAPI();cms_team.register_team_routes(app)
        endpoint=next(r.endpoint for r in app.routes if r.path=="/api/admin/team/role" and "PUT" in r.methods)
        with patch.object(cms_team.user_auth,"required",return_value={"user_id":self.owner}),\
             patch.object(cms_access,"OWNER_IDS",{self.owner}),\
             patch.object(cms_access,"ensure_roles"),\
             patch.object(cms_access.user_auth,"db",return_value=self.db),\
             patch.object(cms_team.user_auth,"origin"),\
             patch.object(cms_team.user_auth,"check_csrf"):
            result=endpoint(cms_team.RoleGrant(user_id=self.editor,role="reviewer"),object())
        self.assertTrue(result["ok"])
        self.assertEqual(self.db.one("SELECT role FROM atlas_cms_roles WHERE user_id=?",(self.editor,))["role"],"reviewer")
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM atlas_cms_role_history")["n"],1)

    def test_owner_cannot_be_demoted(self):
        app=FastAPI();cms_team.register_team_routes(app)
        endpoint=next(r.endpoint for r in app.routes if r.path=="/api/admin/team/role" and "PUT" in r.methods)
        with patch.object(cms_team.user_auth,"required",return_value={"user_id":self.owner}),\
             patch.object(cms_access,"OWNER_IDS",{self.owner}),\
             patch.object(cms_access,"ensure_roles"),\
             patch.object(cms_access.user_auth,"db",return_value=self.db),\
             patch.object(cms_team.user_auth,"origin"),\
             patch.object(cms_team.user_auth,"check_csrf"):
            with self.assertRaises(HTTPException) as err:
                endpoint(cms_team.RoleGrant(user_id=self.owner,role="editor"),object())
        self.assertEqual(err.exception.status_code,409)

    def test_schedule_time_requires_zone_and_future(self):
        now=self.now
        with self.assertRaises(HTTPException):
            cms_schedule.parse_publish_time("2026-11-25T10:00:00",now)
        with self.assertRaises(HTTPException):
            cms_schedule.parse_publish_time((now+timedelta(seconds=20)).isoformat(),now)
        value=cms_schedule.parse_publish_time((now+timedelta(days=1)).isoformat(),now)
        self.assertTrue(value.endswith("+00:00"))

    def test_scheduled_publish_preserves_exact_approved_draft(self):
        self.add_schedule()
        with patch.object(cms_schedule.cms_routes,"ensure_cms"),\
             patch.object(cms_schedule.user_auth,"db",return_value=self.db),\
             patch.object(cms_schedule.cms_routes,"verify_links"),\
             patch.object(cms_schedule.cms_routes,"invalidate"):
            count=cms_schedule.publish_due(now=self.now,force=True)
        self.assertEqual(count,1)
        article=self.db.one("SELECT * FROM atlas_cms_entries WHERE kind='article' AND slug=?",(self.key,))
        self.assertEqual(article["status"],"published")
        self.assertEqual(article["revision"],3)
        self.assertEqual(article["published_json"],article["draft_json"])
        self.assertEqual(self.db.one("SELECT status FROM atlas_cms_schedules")["status"],"published")
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM atlas_cms_history")["n"],1)
        with patch.object(cms_schedule.cms_routes,"ensure_cms"),\
             patch.object(cms_schedule.user_auth,"db",return_value=self.db):
            self.assertEqual(cms_schedule.publish_due(now=self.now,force=True),0)

    def test_schedule_stale_revision_never_publishes(self):
        self.add_schedule(rev=1)
        with patch.object(cms_schedule.cms_routes,"ensure_cms"),\
             patch.object(cms_schedule.user_auth,"db",return_value=self.db):
            count=cms_schedule.publish_due(now=self.now,force=True)
        self.assertEqual(count,0)
        self.assertEqual(self.db.one("SELECT status FROM atlas_cms_schedules")["status"],"stale")
        self.assertEqual(self.db.one("SELECT status FROM atlas_cms_entries")["status"],"review")

    def test_schedule_never_publishes_a_draft(self):
        self.add_entry(status="draft")
        self.add_schedule(rev=2)
        with patch.object(cms_schedule.cms_routes,"ensure_cms"),\
             patch.object(cms_schedule.user_auth,"db",return_value=self.db):
            self.assertEqual(cms_schedule.publish_due(now=self.now,force=True),0)
        self.assertEqual(self.db.one("SELECT status FROM atlas_cms_entries")["status"],"draft")

    def test_failed_validation_keeps_public_snapshot(self):
        self.add_schedule()
        with patch.object(cms_schedule.cms_routes,"ensure_cms"),\
             patch.object(cms_schedule.user_auth,"db",return_value=self.db),\
             patch.object(cms_schedule.cms_routes,"verify_links",side_effect=HTTPException(422,"invalid")):
            self.assertEqual(cms_schedule.publish_due(now=self.now,force=True),0)
        row=self.db.one("SELECT status,published_json FROM atlas_cms_entries")
        self.assertEqual(row["status"],"review")
        self.assertIn("Old Public",row["published_json"])
        self.assertEqual(self.db.one("SELECT status FROM atlas_cms_schedules")["status"],"failed")

    def test_cancelled_schedule_does_not_publish(self):
        self.add_schedule()
        self.db.execute("UPDATE atlas_cms_schedules SET status='cancelled'")
        with patch.object(cms_schedule.cms_routes,"ensure_cms"),\
             patch.object(cms_schedule.user_auth,"db",return_value=self.db):
            self.assertEqual(cms_schedule.publish_due(now=self.now,force=True),0)

    def test_editor_cannot_create_scheduled_release(self):
        app=FastAPI();cms_schedule.register_schedule_routes(app)
        endpoint=next(r.endpoint for r in app.routes if r.path=="/api/admin/content/{kind}/{slug}/schedule" and "POST" in r.methods)
        with patch.object(cms_schedule.cms_routes.user_auth,"required",return_value={"user_id":self.editor}),\
             patch.object(cms_access,"OWNER_IDS",{self.owner}),\
             patch.object(cms_access,"ensure_roles"),\
             patch.object(cms_access.user_auth,"db",return_value=self.db):
            with self.assertRaises(HTTPException) as e:
                endpoint("article",self.key,cms_schedule.ScheduleRequest(
                    expected_revision=2,publish_at=(self.now+timedelta(days=1)).isoformat()),object())
        self.assertEqual(e.exception.status_code,403)

if __name__=="__main__":
    unittest.main()
