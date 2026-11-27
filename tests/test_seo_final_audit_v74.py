"""V74: published-only final editorial graph and quality audit; no browser automation."""
import copy
import unittest
from unittest.mock import patch
from fastapi import FastAPI, Request, HTTPException
from app import cms_routes,cms_quality,seo_final_audit,seo_routes


class FinalEditorialAuditV74(unittest.TestCase):
    def setUp(self):
        self.published={
            "sites":{
                "factory":{"name":"Industrial manufacturer website","url":"https://factory.example.org",
                           "summary":"Original evidence describing production systems, trust and technical requirements. "*3},
                "other":{"name":"A separate industrial manufacturer","url":"https://other.example.org",
                         "summary":"Independent industrial case observation. "*3}},
            "modules":{
                "hero":{"title":"Specification-led product header","site_id":"factory",
                        "url":"https://factory.example.org/catalog",
                        "lesson":"Detailed product specifications and engineering trust evidence. "*3}},
            "patterns":{
                "proof":{"title":"Proof before conversion","question":"Where should specifications appear?",
                         "principle":"Show original sources and specification references in context. "*3,
                         "when":"High-consideration industrial procurement workflows. "*2,
                         "modules":["hero","deleted-module"]}},
            "articles":{
                "study":{"title":"Manufacturing purchasing research",
                         "subtitle":"An independently researched buyer journey across industrial website examples.",
                         "published_at":"2026-11-26",
                         "references":[["website","factory"],["module","hero"],["pattern","proof"]],
                         "sections":[{"title":"Evidence",
                                      "blocks":[{"type":"paragraph",
                                                 "text":"Verified industrial procurement context and design evidence. "*9}]}]}}
        }
        self.original=copy.deepcopy(self.published)

    def test_graph_contains_only_explicit_published_references(self):
        maps=seo_final_audit.published_maps(self.published)
        incoming,outgoing,broken=seo_final_audit.editorial_graph(maps)
        self.assertIn(("module","hero"),outgoing[("pattern","proof")])
        self.assertIn(("site","factory"),outgoing[("module","hero")])
        self.assertIn(("site","factory"),outgoing[("article","study")])
        self.assertEqual(len(incoming[("site","factory")]),2)
        self.assertIn("module:deleted-module",broken[("pattern","proof")])
        self.assertNotIn(("site","other"),incoming)
        self.assertEqual(self.original,self.published)

    def test_invalid_relations_reported_without_discarding_valid_ones(self):
        report=seo_final_audit.analyze(self.published,kind_filter="pattern")
        self.assertEqual(report["total"],5)
        issue=next(x for x in report["items"] if x["slug"]=="proof")
        self.assertIn("broken_refs",{item["code"] for item in issue["issues"]})
        self.assertEqual(issue["priority"],"high")
        self.assertEqual(issue["outgoing_count"],1)
        self.assertEqual(self.original,self.published)

    def test_missing_contextual_links_are_not_misnamed_crawl_orphans(self):
        report=seo_final_audit.analyze(self.published,kind_filter="site")
        row=next(x for x in report["items"] if x["slug"]=="other")
        self.assertIn("contextual_links",{item["code"] for item in row["issues"]})
        self.assertIn("公开目录",next(item["advice"] for item in row["issues"]
                                   if item["code"]=="contextual_links"))
        self.assertNotIn("orphan",str(row))
        factory=next(x for x in report["items"] if x["slug"]=="factory")
        self.assertNotIn("contextual_links",{item["code"] for item in factory["issues"]})

    def test_thin_module_and_site_are_editable_advisories(self):
        self.published["sites"]["other"]["summary"]="Short"
        self.published["modules"]["hero"]["lesson"]="Thin"
        result=seo_final_audit.analyze(self.published)
        rows={(x["kind"],x["slug"]):x for x in result["items"]}
        for key in (("site","other"),("module","hero")):
            self.assertIn("depth",{item["code"] for item in rows[key]["issues"]})
        self.assertGreaterEqual(result["thin_records"],2)

    def test_large_catalog_counts_are_not_limited_by_page(self):
        for i in range(135):
            self.published["sites"][f"factory-{i:03d}"]={
                "name":f"Manufacturer {i}",
                "summary":"A","url":"https://factory.example.org"}
        report=seo_final_audit.analyze(self.published,limit=12)
        self.assertEqual(report["total"],140)
        self.assertEqual(len(report["items"]),12)
        self.assertGreaterEqual(report["thin_records"],135)
        self.assertTrue(report["has_more"])
        entire=[]
        for offset in range(0,report["matched"],12):
            page=seo_final_audit.analyze(self.published,offset=offset,limit=12)
            entire.extend((x["kind"],x["slug"]) for x in page["items"])
        self.assertEqual(len(entire),report["matched"])
        self.assertEqual(len(set(entire)),report["matched"])
        self.assertEqual(self.original["sites"]["factory"],self.published["sites"]["factory"])

    def test_invalid_slug_and_draft_only_record_cannot_enter_graph(self):
        self.published["sites"]["bad?path"]={"name":"Invalid"}
        self.published["sites"]["draft-only"]={"name":"Draft of a hidden site"}
        public=copy.deepcopy(self.published)
        del public["sites"]["draft-only"] # Model catalog() excludes it before audit.
        report=seo_final_audit.analyze(public)
        self.assertEqual(report["total"],5)
        self.assertFalse(any(x["slug"] in ("bad?path","draft-only") for x in report["items"]))

    def test_pagination_and_column_validation(self):
        for kw in ({"kind_filter":"unknown"},{"offset":-1},{"limit":0},{"limit":900}):
            with self.subTest(kw=kw):
                with self.assertRaises(HTTPException) as err:
                    seo_final_audit.analyze(self.published,**kw)
                self.assertEqual(err.exception.status_code,422)

    def test_route_rejects_guest_before_reading_any_catalog(self):
        app=FastAPI();seo_final_audit.register_final_routes(app)
        endpoint=next(x.endpoint for x in app.routes if x.path=="/api/admin/seo/final-audit")
        req=Request({"type":"http","path":"/api/admin/seo/final-audit","method":"GET","headers":[],"query_string":b""})
        with patch.object(cms_routes,"require_admin",side_effect=HTTPException(403)):
            with patch.object(seo_routes,"catalog") as read_catalog:
                with self.assertRaises(HTTPException):endpoint(req)
                read_catalog.assert_not_called()
        with patch.object(cms_routes,"require_admin",return_value={"user_id":"test"}) as required:
            with patch.object(seo_routes,"catalog",return_value=self.published):
                checked=endpoint(req,"article",0,12)
        required.assert_called_once_with(req,permission="view")
        self.assertTrue(checked["items"])
        self.assertEqual(checked["kind"],"article")

    def test_panel_stays_under_existing_seo_audit_with_real_editor_navigation(self):
        html=(seo_routes.STATIC/"cms.html").read_text(encoding="utf-8")
        js=(seo_routes.STATIC/"assets"/"cms.js").read_text(encoding="utf-8")
        self.assertIn('id="cms-final-panel"',html)
        self.assertIn('id="cms-final-list"',html)
        self.assertIn('id="cms-final-more"',html)
        self.assertIn('id="cms-final-kind"',html)
        self.assertIn("function renderSeoFinalItems(",js)
        self.assertIn("async function openSeoFinalFinding(kind,slug)",js)
        self.assertIn("if(!await changeKind(kind))return;",js)
        self.assertIn("seoAuditTarget={kind,slug,issues:issue.issues.map(",js)
        self.assertIn("refreshSeoFinalAudit()",js)
        self.assertIn("/assets/cms.js?v=7401",html)
        self.assertIn("/assets/cms.css?v=7401",html)


if __name__=="__main__":unittest.main()
