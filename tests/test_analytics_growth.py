"""V51.8–V51.12 contracts for real, unattributed and campaign-specific analytics."""
import sqlite3
import unittest
import uuid
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI,HTTPException,Response
from app import analytics_growth as growth

class DB:
    def __init__(self):
        self.conn=sqlite3.connect(":memory:")
        self.conn.row_factory=sqlite3.Row
        for sql in growth.SCHEMA:self.conn.execute(sql)
    def execute(self,sql,args=()):return self.conn.execute(sql,args)
    def all(self,sql,args=()):return [dict(r) for r in self.execute(sql,args).fetchall()]
    def one(self,sql,args=()):
        row=self.execute(sql,args).fetchone()
        return dict(row) if row else None
    def __enter__(self):return self
    def __exit__(self,typ,exc,tb):
        if typ:self.conn.rollback()
        else:self.conn.commit()

class GrowthTests(unittest.TestCase):
    def setUp(self):
        self.db=DB()
        self.now=datetime.now(timezone.utc).replace(microsecond=0)
        self.sid=str(uuid.uuid4())

    def event(self,kind="page_view",**kwargs):
        return growth.GrowthEvent(event=kind,session=kwargs.pop("session",self.sid),
                                  path=kwargs.pop("path","/websites/fictiv"),**kwargs)

    def test_attribution_organic_and_utm(self):
        meta=growth.classify_source(self.event(referrer="https://www.google.com/search?q=secret"),"atlas.example")
        self.assertEqual(meta["channel"],"organic")
        self.assertEqual(meta["referrer"],"google.com")
        self.assertEqual(meta["source"],"google.com")
        campaign=growth.classify_source(self.event(utm_source="linkedin",utm_medium="paid",utm_campaign="B2B_2026"),"atlas.example")
        self.assertEqual(campaign["channel"],"paid")
        self.assertEqual(campaign["campaign"],"b2b_2026")
        self.assertEqual(growth.referrer_host("https://example.com/private?email=user@example.com"),"example.com")
        self.assertEqual(growth.referrer_host("https://127.0.0.1/details"),"")

    def test_session_dedup_and_channel_is_immutable(self):
        self.assertTrue(growth.ingest(self.db,self.event(utm_source="linkedin",utm_medium="social"),"atlas.example",self.now))
        self.assertTrue(growth.ingest(self.db,self.event(path="/insights/study",utm_source="google",utm_medium="organic"),"atlas.example",self.now))
        self.assertTrue(growth.ingest(self.db,self.event("search"),"atlas.example",self.now))
        self.assertTrue(growth.ingest(self.db,self.event("scroll",depth=50),"atlas.example",self.now))
        sid=growth.hash_sid(self.sid)
        self.assertNotEqual(sid,self.sid)
        session=self.db.one("SELECT * FROM atlas_growth_sessions")
        self.assertEqual(session["channel"],"social")
        self.assertEqual(session["landing"],"/websites/fictiv")
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM atlas_growth_daily")["n"],1)
        report=growth.report(7,self.db,now=self.now)
        self.assertEqual(report["totals"]["sessions"],1)
        self.assertEqual(report["totals"]["views"],2)
        self.assertEqual(report["totals"]["searches"],1)
        self.assertEqual(report["totals"]["engaged_sessions"],1)
        self.assertEqual(report["scroll_depth"][1]["sessions"],1)
        self.assertEqual(report["channels"][0]["key"],"social")

    def test_sessions_are_created_only_by_pageviews(self):
        self.assertFalse(growth.ingest(self.db,self.event("external_click"),"atlas.example",self.now))
        self.assertFalse(growth.ingest(self.db,self.event("scroll",depth=25),"atlas.example",self.now))
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM atlas_growth_sessions")["n"],0)

    def test_content_metrics_track_real_actions(self):
        growth.ingest(self.db,self.event(),"atlas.example",self.now)
        growth.ingest(self.db,self.event("content_click",target="/insights/study"),"atlas.example",self.now)
        growth.ingest(self.db,self.event("preview"),"atlas.example",self.now)
        growth.ingest(self.db,self.event("external_click"),"atlas.example",self.now)
        self.assertFalse(growth.ingest(self.db,self.event("content_click",target="https://other.test"),"atlas.example",self.now))
        report=growth.report(7,self.db,now=self.now)
        self.assertEqual(report["totals"]["content_clicks"],1)
        self.assertEqual(report["totals"]["external_clicks"],1)
        self.assertEqual(report["content"][0]["path"],"/websites/fictiv")
        self.assertEqual(next(x for x in report["content"] if x["path"]=="/insights/study")["content_clicks"],1)

    def test_credited_conversions_are_only_once_per_session(self):
        growth.ingest(self.db,self.event(),"atlas.example",self.now)
        with patch.object(growth,"ensure_growth"),patch.object(growth.user_auth,"db",return_value=self.db):
            self.assertTrue(growth.record_conversion(self.sid,"registration"))
            self.assertFalse(growth.record_conversion(self.sid,"registration"))
            self.assertTrue(growth.record_conversion(self.sid,"save"))
            self.assertFalse(growth.record_conversion(self.sid,"save"))
        report=growth.report(7,self.db,now=self.now)
        self.assertEqual(report["totals"]["registrations"],1)
        self.assertEqual(report["totals"]["first_saves"],1)
        self.assertEqual(report["totals"]["signup_to_save"],1)

    def test_save_without_signup_does_not_fake_signup_to_save(self):
        growth.ingest(self.db,self.event(),"atlas.example",self.now)
        with patch.object(growth,"ensure_growth"),patch.object(growth.user_auth,"db",return_value=self.db):
            self.assertTrue(growth.record_conversion(self.sid,"save"))
        self.assertEqual(growth.report(7,self.db,now=self.now)["totals"]["signup_to_save"],0)

    def test_invalid_session_cannot_be_attributed(self):
        self.assertFalse(growth.record_conversion("not-a-uuid","registration"))
        self.assertFalse(growth.ingest(self.db,self.event(session="bad"),"atlas.example",self.now))

    def test_expired_session_cannot_receive_new_actions(self):
        growth.ingest(self.db,self.event(),"atlas.example",self.now)
        self.assertFalse(growth.ingest(self.db,self.event("search"),"atlas.example",self.now+timedelta(minutes=46)))

    def test_channel_filter_is_not_fictional(self):
        growth.ingest(self.db,self.event(utm_source="google",utm_medium="organic"),"atlas.example",self.now)
        second=str(uuid.uuid4())
        growth.ingest(self.db,self.event(session=second),"atlas.example",self.now)
        report=growth.report(7,self.db,channel="organic",now=self.now)
        self.assertEqual(report["totals"]["sessions"],1)
        self.assertEqual(report["channels"][0]["key"],"organic")

    def test_persisted_schema_has_no_pii_columns(self):
        for table in ("atlas_growth_sessions","atlas_growth_daily","atlas_growth_content"):
            fields={r["name"] for r in self.db.all("PRAGMA table_info("+table+")")}
            self.assertFalse(fields & {"ip","email","user_id","cookie","user_agent","referrer_url"})

    def test_admin_endpoint_rejects_unauthorized(self):
        app=FastAPI()
        growth.register_growth_routes(app)
        endpoint=next(r.endpoint for r in app.routes if getattr(r,"path","")=="/api/admin/growth")
        with patch.object(growth.user_auth,"required",side_effect=HTTPException(status_code=401,detail="login")):
            with self.assertRaises(HTTPException) as e:
                endpoint(object(),Response(),30,"all")
        self.assertEqual(e.exception.status_code,401)
        with patch.object(growth.user_auth,"required",return_value={"user_id":"u"}),\
             patch.object(growth.admin_routes,"admin_allowed",return_value=False):
            with self.assertRaises(HTTPException) as e:
                endpoint(object(),Response(),30,"all")
        self.assertEqual(e.exception.status_code,403)

if __name__=="__main__":
    unittest.main()
