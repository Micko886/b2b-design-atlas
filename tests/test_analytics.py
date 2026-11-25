"""V51.7 contracts: anonymous event guards and real DB-backed analytics."""
import sqlite3
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException, Response
from app import analytics_routes


class DB:
    def __init__(self):
        self.con=sqlite3.connect(":memory:")
        self.con.row_factory=sqlite3.Row
        for sql in analytics_routes.ANALYTICS_SCHEMA:self.con.execute(sql)
        self.con.execute("CREATE TABLE atlas_users(id TEXT PRIMARY KEY,created_at TEXT)")
        self.con.execute("CREATE TABLE atlas_user_items(user_id TEXT,collection TEXT,kind TEXT,slug TEXT)")
        self.con.execute("CREATE TABLE atlas_user_entities(user_id TEXT,collection TEXT,kind TEXT,slug TEXT)")
    def execute(self,sql,args=()):return self.con.execute(sql,args)
    def all(self,sql,args=()):return [dict(r) for r in self.execute(sql,args).fetchall()]
    def one(self,sql,args=()):
        result=self.execute(sql,args).fetchone()
        return dict(result) if result else None
    def __enter__(self):return self
    def __exit__(self,*args):self.con.commit()


class AnalyticsContracts(unittest.TestCase):
    def test_public_routes_are_strictly_whitelisted(self):
        self.assertEqual(analytics_routes.normalize_path("/websites/fictiv"),"/websites/fictiv")
        self.assertEqual(analytics_routes.normalize_path("/"),"/")
        for path in ("https://example.com","/admin","/account","/websites/../foo",
                     "/insights/x?q=secret","/websites/some%2Fthing"):
            with self.subTest(path=path):
                self.assertIsNone(analytics_routes.normalize_path(path))

    def test_search_never_accepts_email_urls_or_phone_like_terms(self):
        self.assertEqual(analytics_routes.normalize_search("工业设计"),"工业设计")
        self.assertEqual(analytics_routes.normalize_search("  Hero  Design  "),"hero design")
        for search in ("a@b.com","https://abc.com","www.foo.com","1234567890","x"):
            self.assertIsNone(analytics_routes.normalize_search(search))

    def test_aggregation_uses_only_recorded_events_and_existing_accounts(self):
        db=DB()
        db.execute("INSERT INTO atlas_analytics_daily VALUES('2026-11-24','page_view','/insights/study',5)")
        db.execute("INSERT INTO atlas_analytics_daily VALUES('2026-11-25','page_view','/websites/fictiv',2)")
        db.execute("INSERT INTO atlas_analytics_daily VALUES('2026-11-25','search','b2b',3)")
        db.execute("INSERT INTO atlas_users VALUES('u1','2026-11-25T08:00:00')")
        db.execute("INSERT INTO atlas_user_items VALUES('u1','saved','site','fictiv')")
        db.execute("INSERT INTO atlas_user_entities VALUES('u1','saved','article','study')")
        catalog={"sites":{"fictiv":{"name":"Fictiv"}},"modules":{},"patterns":{},
                 "articles":{"study":{"title":"Study"}}}
        with patch.object(analytics_routes.seo_routes,"catalog",return_value=catalog):
            report=analytics_routes.query_report(7,db,now=date(2026,11,25))
        self.assertEqual(report["totals"]["page_views"],7)
        self.assertEqual(report["totals"]["searches"],3)
        self.assertEqual(report["totals"]["active_saves"],2)
        self.assertEqual(report["totals"]["registered_users"],1)
        self.assertEqual(report["totals"]["new_users"],1)
        self.assertEqual(len(report["daily"]),7)
        self.assertEqual(report["top_pages"][0]["label"],"Study")
        self.assertEqual(report["top_searches"][0]["term"],"b2b")
        self.assertEqual(report["top_saved"][0]["label"],"Fictiv")

    def test_daily_upsert_counts_real_events(self):
        db=DB()
        for _ in range(3):
            db.execute("INSERT INTO atlas_analytics_daily(day,kind,bucket,n) VALUES(?,?,?,1) "
                "ON CONFLICT(day,kind,bucket) DO UPDATE SET n=atlas_analytics_daily.n+1",
                ("2026-11-25","page_view","/insights/test"))
        self.assertEqual(db.one("SELECT n FROM atlas_analytics_daily")["n"],3)

    def test_anonymous_collector_has_no_identifier_columns(self):
        db=DB()
        cols=[x["name"] for x in db.all("PRAGMA table_info(atlas_analytics_daily)")]
        self.assertEqual(cols,["day","kind","bucket","n"])

    def test_admin_endpoint_denies_guest_and_unassigned_account(self):
        app=FastAPI()
        analytics_routes.register_analytics_routes(app)
        endpoint=next(r.endpoint for r in app.routes
                      if getattr(r,"path",None)=="/api/admin/analytics")
        with patch.object(analytics_routes.user_auth,"required",
                          side_effect=HTTPException(status_code=401,detail="login")):
            with self.assertRaises(HTTPException) as error:
                endpoint(object(),Response(),7)
        self.assertEqual(error.exception.status_code,401)
        with patch.object(analytics_routes.user_auth,"required",return_value={"user_id":"u"}), \
             patch.object(analytics_routes.admin_routes,"admin_allowed",return_value=False):
            with self.assertRaises(HTTPException) as error:
                endpoint(object(),Response(),7)
        self.assertEqual(error.exception.status_code,403)

    def test_collector_ignores_private_route_and_bad_search(self):
        app=FastAPI()
        analytics_routes.register_analytics_routes(app)
        endpoint=next(r.endpoint for r in app.routes
                      if getattr(r,"path",None)=="/api/analytics/event")
        request=SimpleNamespace(headers={"host":"example.com"},client=SimpleNamespace(host="127.0.0.1"))
        with patch.object(analytics_routes,"permitted",return_value=True):
            result=endpoint(analytics_routes.PublicEvent(type="page_view",path="/account"),request)
            self.assertEqual(result.status_code,204)
            result=endpoint(analytics_routes.PublicEvent(type="search",path="/websites",query="hello@example.com"),request)
            self.assertEqual(result.status_code,204)


if __name__=="__main__":
    unittest.main()
