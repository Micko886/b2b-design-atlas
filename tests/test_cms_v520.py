"""V51.20 editorial blocks, SEO, media usage, diff and frontend contracts."""
import inspect
import json
import sqlite3
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI,HTTPException

from app import cms_routes,cms_diff,cms_quality,seo_routes,analytics_routes,analytics_growth
from test_cms_v514 import DB

STATIC=Path("/srv/atlas/static")

def draft(slug="study"):
    return {"id":slug,"title":"B2B Industrial Website Design Analysis",
            "subtitle":"A research report about layout, trust and conversion patterns in industrial websites.",
            "author":"Atlas Studio","category":"design","reading_minutes":5,
            "tags":["Industrial UX"],"sections":[{"title":"Trust and navigation",
              "blocks":[{"type":"paragraph","text":"This report examines navigation, trust signals and conversion behavior for industrial websites."},
                        {"type":"heading","text":"A useful pattern"},
                        {"type":"list","items":["Clear navigation","Case study evidence"]},
                        {"type":"table","rows":[["Pattern","Use"],["Navigation","Find product"]] }]}]}

class ArticleBlockTests(unittest.TestCase):
    def test_new_blocks_validate_without_legacy_paragraphs(self):
        content=cms_routes.cleaned("article","study",draft())
        self.assertEqual(content["sections"][0]["blocks"][0]["type"],"paragraph")
        self.assertEqual(content["sections"][0]["blocks"][3]["type"],"table")

    def test_disallow_injected_html_image_url(self):
        invalid=draft()
        invalid["sections"][0]["blocks"].append({"type":"image","src":"javascript:alert(1)"})
        with self.assertRaises(HTTPException) as err:
            cms_routes.cleaned("article","study",invalid)
        self.assertEqual(err.exception.status_code,422)

    def test_reject_oversized_list_and_invalid_links(self):
        invalid=draft()
        invalid["sections"][0]["blocks"].append({"type":"list","items":["long"]*61})
        with self.assertRaises(HTTPException):
            cms_routes.cleaned("article","study",invalid)
        invalid["sections"][0]["blocks"][-1]={"type":"link","text":"Open","url":"data:text/html,bad"}
        with self.assertRaises(HTTPException):
            cms_routes.cleaned("article","study",invalid)

    def test_seo_metadata_has_length_limits(self):
        invalid=draft();invalid["seo_description"]="x"*301
        with self.assertRaises(HTTPException):
            cms_routes.cleaned("article","study",invalid)

    def test_legacy_sections_still_validate(self):
        item=draft()
        item["sections"]=[{"title":"Legacy","paragraphs":["A legacy paragraph."],"bullets":["Checklist"],"callout":"Tip"}]
        self.assertEqual(cms_routes.cleaned("article","study",item)["sections"][0]["paragraphs"][0],"A legacy paragraph.")

class DiffAndSeoTests(unittest.TestCase):
    def test_diff_detects_block_changes_and_history(self):
        old=draft();new=draft()
        new["sections"][0]["blocks"][0]["text"]="Updated and corrected research text"
        new["sections"][0]["blocks"].append({"type":"quote","text":"A design observation"})
        output=cms_diff.compare_payloads("article",old,new)
        self.assertIn("sections",output["changed_fields"])
        self.assertTrue(any(c["tag"]!="equal" for c in output["chunks"]))
        self.assertGreater(output["summary"]["added"],0)

    def test_seo_report_uses_real_fields_and_image_alt(self):
        item=draft()
        item["seo_title"]="Industry Design Study"
        item["seo_description"]="This industrial B2B study examines navigation systems, trust-building sections and conversion design choices across real enterprise sites."
        item["sections"][0]["blocks"].append({"type":"image","src":"/api/media/"+str(uuid.uuid4()),"alt":"","caption":""})
        result=cms_quality.quality_report("study",item)
        self.assertEqual(result["canonical_path"],"/insights/study")
        self.assertTrue(any(x["code"]=="alt" and x["status"]=="warning" for x in result["checks"]))
        self.assertTrue(0<=result["score"]<=100)
        self.assertFalse("rank" in result)

    def test_public_seo_uses_published_title_description(self):
        item=draft()
        item["seo_title"]="Custom SEO Title"
        item["seo_description"]="A custom snippet for research readers."
        with patch.object(seo_routes,"catalog",return_value={"sites":{},"modules":{},"patterns":{},"articles":{"study":item}}):
            record=seo_routes.seo_record("/insights/study")
        self.assertEqual(record["title"],"Custom SEO Title")
        self.assertEqual(record["description"],"A custom snippet for research readers.")

    def test_diff_and_seo_routes_have_no_dynamic_route_collision(self):
        app=FastAPI()
        cms_routes.register_cms_routes(app)
        cms_diff.register_diff_routes(app)
        cms_quality.register_quality_routes(app)
        paths=[(r.path,method) for r in app.routes for method in (getattr(r,"methods",[]) or [])]
        self.assertIn(("/api/admin/content/{kind}/{slug}/diff","GET"),paths)
        self.assertIn(("/api/admin/seo/article/{slug}","GET"),paths)
        self.assertIn(("/api/admin/seo/check","POST"),paths)

    def test_seo_preview_is_not_public(self):
        app=FastAPI();cms_quality.register_quality_routes(app)
        route=next(r.endpoint for r in app.routes if r.path=="/api/admin/seo/check")
        with patch.object(cms_quality.cms_routes,"require_admin",side_effect=HTTPException(403,"denied")):
            with self.assertRaises(HTTPException) as error:
                route(cms_quality.SeoPreview(slug="study",payload=draft()),object())
        self.assertEqual(error.exception.status_code,403)

class MediaUsageTests(unittest.TestCase):
    def test_cms_media_usage_counts_draft_and_published_once(self):
        db=DB()
        mid=str(uuid.uuid4())
        db.execute("""INSERT INTO atlas_cms_media
           (id,file_name,mime_type,content_b64,byte_size,sha256,uploaded_by,created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
           (mid,"photo.webp","image/webp","UklGRg==",6,"sha","u","2026-11-25"))
        document=draft()
        document["sections"][0]["blocks"].append({"type":"image","src":"/api/media/"+mid,"alt":"Navigation UI","caption":"Original"})
        encoded=json.dumps(document)
        db.execute("""INSERT INTO atlas_cms_entries(kind,slug,draft_json,published_json,status,revision,created_by,updated_by,created_at,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
           ("article","study",encoded,encoded,"published",2,"u","u","2026-11-25","2026-11-25"))
        app=FastAPI();cms_routes.register_cms_routes(app)
        fn=next(r.endpoint for r in app.routes if r.path=="/api/admin/media" and "GET" in r.methods)
        with patch.object(cms_routes,"require_admin"),patch.object(cms_routes,"ensure_cms"),\
             patch.object(cms_routes.user_auth,"db",return_value=db):
            result=fn(object())
        row=next(x for x in result["items"] if x["id"]==mid)
        self.assertEqual(row["usage_count"],1)
        self.assertEqual(row["used_by"][0]["slug"],"study")

class DashboardRequestTests(unittest.TestCase):
    def test_analytics_days_param_accepts_query_string_coercion(self):
        for module,reg,path in [
            (analytics_routes,analytics_routes.register_analytics_routes,"/api/admin/analytics"),
            (analytics_growth,analytics_growth.register_growth_routes,"/api/admin/growth")
        ]:
            app=FastAPI();reg(app)
            endpoint=next(r.endpoint for r in app.routes if r.path==path)
            annotation=inspect.signature(endpoint).parameters["days"].annotation
            self.assertIn(annotation,(int,"int"))
            with patch.object(module.user_auth,"required",return_value={"user_id":"test"}),\
                 patch.object(module.admin_routes,"admin_allowed",return_value=True):
                with self.assertRaises(HTTPException) as err:
                    if module is analytics_growth:endpoint(object(),object(),15,"all")
                    else:endpoint(object(),object(),15)
            self.assertEqual(err.exception.status_code,422)

class EditorialFrontendContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cms=(STATIC/"assets/cms.js").read_text(encoding="utf-8")
        cls.app=(STATIC/"assets/app.js").read_text(encoding="utf-8")
        cls.html=(STATIC/"cms.html").read_text(encoding="utf-8")
        cls.index=(STATIC/"index.html").read_text(encoding="utf-8")
    def test_block_save_and_public_render_are_wired(self):
        for needle in ("function articleBlock(","function convertLegacyChapter(","data-blocks-mode",
                       "function reindexBlocks(","installBlockDrag()","previewArticleBlock"):
            self.assertIn(needle,self.cms)
        self.assertIn("function renderInsightBlock(",self.app)
        self.assertIn("Array.isArray(s.blocks)",self.app)
    def test_calendar_has_real_week_month_and_drag_reschedule(self):
        for needle in ("cms-calendar-grid","cms-calendar-week","cms-calendar-month","cms-calendar-status"):
            self.assertIn('id="'+needle+'"',self.html)
        for needle in ("function paintCalendar()","function installCalendarDrag()","function shiftCalendar(",
                       "expected_revision:item.revision,publish_at:adjusted.toISOString()"):
            self.assertIn(needle,self.cms)
    def test_diff_media_seo_controls_are_connected(self):
        for needle in ('id="cms-diff-dialog"','id="cms-crop-canvas"','id="cms-crop-ratio"','id="cms-crop-save"'):
            self.assertIn(needle,self.html)
        for needle in ("function openReviewDiff(","function openCrop(","function saveCrop(",
                       "function runSeoAudit(","function seoStudio("):
            self.assertIn(needle,self.cms)
    def test_asset_cache_versions_include_new_public_bundle(self):
        self.assertIn("app.js?v=52.3.1",self.index)
        self.assertIn("app.css?v=51.20",self.index)
        self.assertIn("cms.js?v=5230",self.html)
        self.assertIn("cms.css?v=5230",self.html)

if __name__=="__main__":
    unittest.main()
