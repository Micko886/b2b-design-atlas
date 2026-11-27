"""V73: published-only canonical/robots/sitemap/schema and verified-tag readiness."""
import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI, Request, HTTPException
from app import cms_routes, seo_readiness, seo_routes


class LaunchPreflightV73(unittest.TestCase):
    def setUp(self):
        self.collection={
            "sites":{"factory":{"name":"Industrial manufacturer",
                      "summary":"Research source for engineering buyers",
                      "url":"https://manufacturer.example.org"}},
            "modules":{"hero":{"title":"Specification and proof module",
                        "site_id":"factory","lesson":"Explain product evidence"}},
            "patterns":{"proof":{"title":"Evidence driven design",
                         "question":"Why show engineering data?",
                         "modules":["hero"]}},
            "articles":{"research":{"title":"Industrial B2B research",
                         "subtitle":"Verifiable article about manufacturing design",
                         "references":[["website","factory"]],
                         "published_at":"2026-11-25",
                         "sections":[{"title":"Sources",
                                      "blocks":[{"type":"paragraph",
                                                 "text":"Research source and traceability."}]}]}}
        }
        self.env=patch.dict(os.environ,{
            "ATLAS_PUBLIC_ORIGIN":"",
            "ATLAS_GOOGLE_SITE_VERIFICATION":"",
            "ATLAS_BING_SITE_VERIFICATION":""})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.origin=patch.object(seo_routes,"ORIGIN",
                                 "https://b2b-design-atlas-preview.onrender.com")
        self.origin.start()
        self.addCleanup(self.origin.stop)

    def test_valid_origin_requires_https_no_credential_or_path(self):
        self.assertTrue(seo_readiness.valid_origin("https://example.org"))
        for value in ("http://example.org","https://example.org/path",
                      "https://user:pass@example.org","https://example.org?x=y",
                      "https://example.org#header","https://example.org:1234",
                      "javascript:alert(1)"):
            with self.subTest(value=value):
                self.assertFalse(seo_readiness.valid_origin(value))

    def test_published_pages_canonical_schema_robots_and_sitemap_all_align(self):
        report=seo_readiness.build_report(self.collection)
        self.assertTrue(report["technical_passed"],report["examples"])
        self.assertEqual(report["issue_count"],0,report["examples"])
        self.assertEqual(report["launch_status"],"domain_pending")
        self.assertGreaterEqual(report["inspected_urls"],10)
        self.assertTrue(next(x for x in report["checks"] if x["code"]=="robots")["status"]=="pass")
        self.assertTrue(next(x for x in report["checks"] if x["code"]=="sitemap")["status"]=="pass")
        self.assertTrue(next(x for x in report["checks"] if x["code"]=="metadata")["status"]=="pass")
        self.assertTrue(next(x for x in report["checks"] if x["code"]=="discovery")["status"]=="pass")
        self.assertTrue(report["external_verification_pending"])

    def test_final_domain_configuration_is_not_misrepresented_as_verified(self):
        with patch.object(seo_routes,"ORIGIN","https://design.example.org"):
            with patch.dict(os.environ,{"ATLAS_PUBLIC_ORIGIN":"https://design.example.org",
                 "ATLAS_GOOGLE_SITE_VERIFICATION":"googleproofTEST987654321",
                 "ATLAS_BING_SITE_VERIFICATION":"bingproofTEST987654321"}):
                report=seo_readiness.build_report(self.collection)
                with patch.object(seo_routes,"catalog",return_value=self.collection):
                    html=seo_routes.seo_document("websites/factory").body.decode()
                    private=seo_routes.seo_document("account").body.decode()
        self.assertEqual(report["launch_status"],"external_review")
        self.assertTrue(report["technical_passed"])
        self.assertTrue(report["external_verification_pending"])
        self.assertIn('name="google-site-verification" content="googleproofTEST987654321"',html)
        self.assertIn('name="msvalidate.01" content="bingproofTEST987654321"',html)
        self.assertIn('rel="canonical" href="https://design.example.org/websites/factory"',html)
        self.assertNotIn('google-site-verification',private)
        self.assertNotIn('msvalidate.01',private)
        self.assertFalse(any(x["status"]=="pending" for x in report["checks"]))

    def test_bad_verification_code_is_rejected_without_html_injection(self):
        with patch.dict(os.environ,{
            "ATLAS_GOOGLE_SITE_VERIFICATION":'"><script>alert(1)</script>',
            "ATLAS_BING_SITE_VERIFICATION":"ok"}):
            states=seo_routes.verification_state()
            self.assertEqual(states,{"google":"invalid","bing":"invalid"})
            self.assertEqual(seo_routes.verification_meta_tags(),"")
            report=seo_readiness.build_report(self.collection)
        self.assertEqual(next(x for x in report["checks"] if x["code"]=="verify_google")["status"],"fail")
        self.assertIn("pending",report["counts"])

    def test_duplicate_and_unpublished_urls_are_reported(self):
        entries=list(seo_routes.sitemap_items(self.collection))
        with patch.object(seo_routes,"sitemap_items",
                          side_effect=lambda _:iter(entries+[("/insights/removed",None),
                                                              ("/account",None),
                                                              ("/websites/factory",None)])):
            report=seo_readiness.build_report(self.collection)
        self.assertFalse(report["technical_passed"])
        self.assertEqual(report["launch_status"],"blocked")
        self.assertGreater(report["issue_count"],0)
        codes={item["code"] for item in report["examples"]}
        self.assertTrue({"not_indexable","private_sitemap","duplicate_sitemap"}.issubset(codes))

    def test_ai_navigation_must_not_reference_non_public_research(self):
        original=seo_routes.llms_document(self.collection)
        with patch.object(seo_routes,"llms_document",
                          return_value=original+"\n- [Private](https://example.org/admin)\n"):
            report=seo_readiness.build_report(self.collection)
        self.assertEqual(next(x for x in report["checks"] if x["code"]=="discovery")["status"],"fail")
        self.assertTrue(any(x["code"]=="discovery_link" for x in report["examples"]))

    def test_public_robots_and_xml_use_the_same_audited_sources(self):
        app=FastAPI();seo_routes.register_seo_routes(app)
        routes={x.path:x.endpoint for x in app.routes if hasattr(x,"path")}
        with patch.object(seo_routes,"catalog",return_value=self.collection):
            self.assertEqual(routes["/robots.txt"]().body.decode(),seo_routes.robots_document())
            self.assertEqual(routes["/sitemap.xml"]().body.decode(),
                             seo_routes.sitemap_xml(self.collection))

    def test_readiness_api_is_admin_view_only_before_catalog_read(self):
        app=FastAPI()
        seo_readiness.register_readiness_routes(app)
        endpoint=next(x.endpoint for x in app.routes
                      if getattr(x,"path","")=="/api/admin/seo/readiness")
        request=Request({"type":"http","method":"GET","path":"/api/admin/seo/readiness",
                         "query_string":b"","headers":[]})
        with patch.object(cms_routes,"require_admin",side_effect=HTTPException(401)):
            with patch.object(seo_routes,"catalog") as catalog:
                with self.assertRaises(HTTPException):endpoint(request)
                catalog.assert_not_called()
        with patch.object(cms_routes,"require_admin",return_value={"user_id":"editor"}) as auth:
            with patch.object(seo_routes,"catalog",return_value=self.collection):
                report=endpoint(request)
        auth.assert_called_once_with(request,permission="view")
        self.assertTrue(report["technical_passed"])

    def test_existing_cms_panel_only_and_renewed_cache_version(self):
        html=(seo_routes.STATIC/"cms.html").read_text(encoding="utf-8")
        script=(seo_routes.STATIC/"assets"/"cms.js").read_text(encoding="utf-8")
        self.assertIn('id="cms-seo-readiness"',html)
        self.assertIn('id="cms-seo-readiness-refresh"',html)
        self.assertIn("function renderSeoReadiness(data)",script)
        self.assertIn("await Promise.all([refreshSeoHistory(),refreshSeoReadiness()])",script)
        self.assertIn("/assets/cms.js?v=7401",html)
        self.assertIn("/assets/cms.css?v=7401",html)


if __name__=="__main__":
    unittest.main()
