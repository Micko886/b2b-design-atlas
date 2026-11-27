"""V72 persistent, explicit SEO audit history with published-only issue identity."""
import copy
import json
import unittest
import uuid
from unittest.mock import patch
from fastapi import FastAPI,HTTPException
from app import cms_quality,cms_routes,seo_history,seo_routes,user_auth
from test_cms_v514 import DB

class SeoHistoryV72(unittest.TestCase):
    def setUp(self):
        self.db=DB()
        self.uid=str(uuid.uuid4())
        self.db.execute("INSERT INTO atlas_users(id,email,display_name,created_at) VALUES(?,?,?,?)",
                        (self.uid,"seo-history@example.invalid","SEO QA","2026-11-27"))
        self.published={"sites":{
          "quality":{"name":"Industrial manufacturer evidence page",
                     "summary":"An original, published industrial B2B company website with sourcing information.",
                     "url":"https://supplier.example.org"},
          "missing":{"name":"Missing public source","summary":"A site missing its verifiable original link.",
                     "draft_json":"SECRET_DRAFT_SHOULD_NEVER_BE_PERSISTED"}
        },"modules":{},"patterns":{},"articles":{}}
        app=FastAPI();cms_quality.register_quality_routes(app)
        self.routes={(route.path,verb):route.endpoint
                     for route in app.routes for verb in (route.methods or ())}
        self.patches=[
            patch.object(cms_routes,"ensure_cms"),
            patch.object(user_auth,"db",return_value=self.db),
            patch.object(cms_routes,"require_admin",return_value={"user_id":self.uid}),
            patch.object(seo_routes,"catalog",side_effect=lambda:copy.deepcopy(self.published))
        ]
        for p in self.patches:p.start()
        self.addCleanup(lambda:[p.stop() for p in reversed(self.patches)])
        self.request=object()

    def call(self,method,path,*args):
        return self.routes[(path,method)](*args)

    def test_store_is_opt_in_and_list_uses_immutable_published_snapshots(self):
        self.assertEqual(self.call("GET","/api/admin/seo/history",self.request)["snapshots"],[])
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM atlas_cms_seo_snapshots")["n"],0)
        saved=self.call("POST","/api/admin/seo/history",self.request)
        self.assertEqual(saved["summary"]["total"],2)
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM atlas_cms_seo_snapshots")["n"],1)
        row=self.db.one("SELECT * FROM atlas_cms_seo_snapshots")
        self.assertNotIn("SECRET_DRAFT_SHOULD_NEVER_BE_PERSISTED",row["snapshot_json"])
        self.assertNotIn("draft_json",row["snapshot_json"])
        self.assertNotIn(self.uid,row["snapshot_json"])
        self.assertEqual(len(json.loads(row["snapshot_json"])["records"]),2)
        self.assertIsNone(self.call("GET","/api/admin/seo/history",self.request)["latest_comparison"])

    def test_changes_to_public_version_are_resolved_only_after_next_explicit_save(self):
        old=self.call("POST","/api/admin/seo/history",self.request)
        self.published["sites"]["missing"]["url"]="https://another-supplier.example.org"
        # Reading the report never changes the persisted baseline.
        old_record=self.db.one("SELECT snapshot_json FROM atlas_cms_seo_snapshots WHERE id=?",(old["id"],))
        self.assertIn('"code":"source"',old_record["snapshot_json"])
        new=self.call("POST","/api/admin/seo/history",self.request)
        history=self.call("GET","/api/admin/seo/history",self.request)
        change=history["latest_comparison"]["changes"]
        self.assertEqual(history["snapshots"][0]["id"],new["id"])
        self.assertEqual(history["snapshots"][1]["id"],old["id"])
        self.assertEqual(change["resolved_count"],1)
        self.assertEqual(change["unpublished_issue_count"],0)
        self.assertTrue(any(x["slug"]=="missing" and x["code"]=="source"
                            for x in change["resolved"]))
        self.assertEqual(self.call("GET","/api/admin/seo/history/compare",
                                  self.request,old["id"],new["id"])["changes"]["resolved_count"],1)

    def test_archived_public_records_count_as_unpublished_not_resolved(self):
        before=self.call("POST","/api/admin/seo/history",self.request)
        self.published["sites"].pop("missing")
        after=self.call("POST","/api/admin/seo/history",self.request)
        outcome=seo_history.compare_ids(before["id"],after["id"])["changes"]
        self.assertEqual(outcome["unpublished_record_count"],1)
        self.assertGreaterEqual(outcome["unpublished_issue_count"],1)
        self.assertFalse(any(x["slug"]=="missing" for x in outcome["resolved"]))

    def test_exact_kind_slug_issue_code_compares_identity_not_aggregate_counts(self):
        def item(kind,slug,code):
            return {"kind":kind,"slug":slug,"code":code,
                    "title":slug,"label":code,"priority":"normal"}
        a={"records":["site:one","site:two"],
           "issues":[item("site","one","source"),item("site","two","source")]}
        b={"records":["site:one","site:two"],
           "issues":[item("site","one","source"),item("site","two","description")]}
        change=seo_history.compare_snapshots(a,b)
        self.assertEqual((change["resolved_count"],change["introduced_count"],
                          change["persisting_count"]), (1,1,1))
        self.assertEqual(change["unpublished_issue_count"],0)

    def test_detailed_counts_include_all_items_not_first_hundred(self):
        for index in range(128):
            self.published["sites"][f"needs-{index:03d}"]={
                "name":f"Industrial entry {index}","summary":"Missing URL"}
        result=self.call("POST","/api/admin/seo/history",self.request)
        self.assertEqual(result["summary"]["total"],130)
        details=self.db.one("SELECT snapshot_json FROM atlas_cms_seo_snapshots WHERE id=?",
                            (result["id"],))
        snap=json.loads(details["snapshot_json"])
        self.assertEqual(len(snap["records"]),130)
        self.assertGreaterEqual(len(snap["issues"]),129)

    def test_permissions_and_id_validation(self):
        with patch.object(cms_routes,"require_admin",side_effect=HTTPException(403)):
            with patch.object(seo_routes,"catalog") as public:
                with self.assertRaises(HTTPException):
                    self.call("POST","/api/admin/seo/history",self.request)
                with self.assertRaises(HTTPException):
                    self.call("GET","/api/admin/seo/history",self.request)
                public.assert_not_called()
        with patch.object(cms_routes,"require_admin",return_value={"user_id":self.uid}) as guard:
            self.call("POST","/api/admin/seo/history",self.request)
            guard.assert_called_once_with(self.request,mutate=True,permission="edit")
        with self.assertRaises(HTTPException) as error:
            seo_history.compare_ids("../no","another")
        self.assertEqual(error.exception.status_code,422)
        saved=self.call("GET","/api/admin/seo/history",self.request)["snapshots"][0]
        with self.assertRaises(HTTPException) as error:
            seo_history.compare_ids(saved["id"],saved["id"])
        self.assertEqual(error.exception.status_code,422)
        with self.assertRaises(HTTPException) as error:
            seo_history.compare_ids(str(uuid.uuid4()),saved["id"])
        self.assertEqual(error.exception.status_code,404)

    def test_existing_seo_panel_renders_history_without_new_nav(self):
        html=(seo_routes.STATIC/"cms.html").read_text(encoding="utf-8")
        script=(seo_routes.STATIC/"assets"/"cms.js").read_text(encoding="utf-8")
        self.assertIn('id="cms-audit-history"',html)
        self.assertIn('id="cms-audit-save-history"',html)
        self.assertIn('id="cms-audit-history-compare"',html)
        self.assertIn("function compareSeoHistorySelection()",script)
        self.assertIn("await refreshSeoHistory()",script)
        self.assertIn("if(!can('edit'))return;",script)
        self.assertIn("/assets/cms.js?v=7301",html)
        self.assertIn("/assets/cms.css?v=7301",html)

if __name__=="__main__":
    unittest.main()
