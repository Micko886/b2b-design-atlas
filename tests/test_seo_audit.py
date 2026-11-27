"""V56: SEO/GEO published-content audit; no production DB or network calls."""
from __future__ import annotations
import copy
import json
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException, Request
from app import cms_quality, seo_routes


class PublishedContentAuditTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {
            "sites": {
                "good": {"id": "good", "name": "Documented manufacturer",
                         "summary": "A detailed, verifiable description of this manufacturing website and its product positioning.",
                         "url": "https://example.org", "screenshot_url": "/screenshots/sites/vast.webp"},
                "no-source": {"id": "no-source", "name": "Short", "summary": "Too short",
                              "screenshot_url": ""}},
            "modules": {
                "hero": {"id": "hero", "title": "Manufacturing product hero",
                         "lesson": "A helpful explanation of why specific proof points improve product understanding.",
                         "site_id": "good", "url": "https://example.org/products",
                         "screenshot_url": "/screenshots/modules/hero.webp"}},
            "patterns": {
                "proof": {"id": "proof", "title": "Evidence-first visual storytelling",
                          "question": "When a buyer cannot assess the product, how can clear proof reduce uncertainty?",
                          "principle": "Put specific evidence near each major claim.",
                          "when": "In complex industrial purchasing journeys",
                          "modules": ["hero"]}},
            "articles": {
                "guide": {"id": "guide", "title": "Evaluation guide",
                          "subtitle": "This research explains how to evaluate references, screenshots and evidence in B2B interfaces.",
                          "published_at": "2026-11-25",
                          "cover_site": "good",
                          "references": [["website", "good"]],
                          "sections": [{"title": "Screenshots", "blocks": [
                              {"type": "paragraph", "text": "Verifiable research text."},
                              {"type": "image", "src": "/api/media/12345678-1234-1234-1234-123456789abc", "alt": ""}]}]}}
        }

    def test_full_scan_is_read_only_and_excludes_unpublished_items(self):
        before=copy.deepcopy(self.catalog)
        with patch.object(cms_quality.cms_routes.seo_routes, "catalog", return_value=self.catalog):
            result=cms_quality.audit_published("site",self.catalog)
        self.assertEqual(result["total"],2)
        self.assertEqual(result["flagged"],1)
        self.assertEqual(result["items"][0]["slug"],"no-source")
        self.assertEqual(result["items"][0]["issue_count"],4)
        self.assertEqual(before,self.catalog)

    def test_source_and_relationship_checks_are_contextual(self):
        report=cms_quality.audit_published("module",self.catalog)
        self.assertEqual(report["flagged"],0)
        self.catalog["patterns"]["proof"]["modules"]=[]
        report=cms_quality.audit_published("module",self.catalog)
        self.assertIn("links",[x["code"] for x in report["items"][0]["issues"]])
        report=cms_quality.audit_published("pattern",self.catalog)
        self.assertIn("links",[x["code"] for x in report["items"][0]["issues"]])

    def test_article_image_alt_only_checks_real_content_images(self):
        article=cms_quality.audit_resource("article","guide",self.catalog["articles"]["guide"],self.catalog)
        self.assertIn("alt",[x["code"] for x in article["issues"]])
        self.catalog["articles"]["guide"]["sections"][0]["blocks"][1]["alt"]="Product specification diagram"
        article=cms_quality.audit_resource("article","guide",self.catalog["articles"]["guide"],self.catalog)
        self.assertNotIn("alt",[x["code"] for x in article["issues"]])

    def test_audit_limit_and_order_are_deterministic(self):
        for i in range(4):
            self.catalog["sites"]["extra-"+str(i)]={"name":"Short","summary":"Brief"}
        result=cms_quality.audit_published("site",self.catalog,limit=2)
        self.assertEqual(result["total"],6)
        self.assertEqual(len(result["items"]),2)
        self.assertEqual(result["remaining"],result["flagged"]-2)
        self.assertEqual([x["slug"] for x in result["items"]],["extra-0","extra-1"])

    def test_broken_article_citations_are_flagged_separately(self):
        item=self.catalog["articles"]["guide"]
        item["references"]=[["pattern","no-such-pattern"],["website","good"]]
        report=cms_quality.audit_resource("article","guide",item,self.catalog)
        codes=[x["code"] for x in report["issues"]]
        self.assertIn("broken_refs",codes)
        self.assertNotIn("sources",codes)
        item["references"]=[["pattern","no-such-pattern"]]
        codes=[x["code"] for x in cms_quality.audit_resource("article","guide",item,self.catalog)["issues"]]
        self.assertIn("broken_refs",codes)
        self.assertIn("sources",codes)

    def test_original_articles_have_unique_search_metadata(self):
        article_file=seo_routes.STATIC/"assets"/"articles.json"
        source=json.loads(article_file.read_text(encoding="utf-8"))
        articles=source["articles"]
        self.assertGreaterEqual(len(articles),10)
        descriptions=[]
        base=seo_routes.base_catalog()
        for item in articles:
            with self.subTest(article=item["id"]):
                desc=item["seo_description"]
                self.assertGreaterEqual(len(desc),50)
                self.assertLessEqual(len(desc),170)
                public=seo_routes.seo_record("insights/"+item["id"],base)
                self.assertEqual(public["description"],desc)
                descriptions.append(desc)
        self.assertEqual(len(set(descriptions)),len(descriptions))

    def test_priority_ranking_separates_missing_sources_from_minor_improvements(self):
        report=cms_quality.audit_published("site",self.catalog)
        self.assertEqual(report["high"],1)
        self.assertEqual(report["items"][0]["priority"],"high")
        self.assertTrue(any(issue["priority"]=="high" for issue in report["items"][0]["issues"]))
        self.catalog["sites"]["good"]["summary"]="Short but valid"
        report=cms_quality.audit_published("site",self.catalog)
        self.assertEqual(report["flagged"],2)
        self.assertEqual(report["high"],1)
        self.assertEqual(report["items"][0]["slug"],"no-source")
        minor=next(x for x in report["items"] if x["slug"]=="good")
        self.assertEqual(minor["priority"],"normal")
        self.assertTrue(all(issue["priority"]=="normal" for issue in minor["issues"]))

    def test_api_requires_admin_view_permission_before_reading_catalog(self):
        app=FastAPI()
        cms_quality.register_quality_routes(app)
        endpoint=next(r.endpoint for r in app.routes if getattr(r,"path","")=="/api/admin/seo/audit")
        request=Request({"type":"http","method":"GET","path":"/api/admin/seo/audit",
                         "headers":[],"query_string":b""})
        with patch.object(cms_quality.cms_routes,"require_admin",
                          side_effect=HTTPException(401,"Not authenticated")):
            with self.assertRaises(HTTPException) as cm:
                endpoint(request,kind="site")
            self.assertEqual(cm.exception.status_code,401)
        with patch.object(cms_quality.cms_routes,"require_admin",return_value={"user_id":"test"}) as guard:
            with patch.object(cms_quality.cms_routes.seo_routes,"catalog",return_value=self.catalog):
                result=endpoint(request,kind="article")
        guard.assert_called_once_with(request,permission="view")
        self.assertEqual(result["total"],1)
        self.assertEqual(result["items"][0]["kind"],"article")

    def test_ui_is_in_existing_admin_without_new_navigation(self):
        from pathlib import Path
        html=(seo_routes.STATIC/"cms.html").read_text(encoding="utf-8")
        js=(seo_routes.STATIC/"assets"/"cms.js").read_text(encoding="utf-8")
        self.assertIn('id="cms-audit-panel"',html)
        self.assertIn('id="cms-audit-open"',html)
        self.assertIn("/api/admin/seo/audit?kind=",js)
        self.assertIn("data-seo-audit-edit",js)
        self.assertIn("data-seo-audit-focus",js)
        self.assertIn('id="cms-audit-priority"',html)
        self.assertIn("优先处理",html)
        self.assertIn("seoAuditData?.kind===item.kind",js)


if __name__=="__main__":
    unittest.main()
