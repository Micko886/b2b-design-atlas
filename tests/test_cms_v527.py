"""V52.7 · Readable reviewer comparisons and unpublished in-browser preview contract."""
import re
import unittest
from pathlib import Path
from app import cms_routes,cms_diff
from fastapi import FastAPI
from test_cms_v514 import DB
from unittest.mock import patch
import json
import uuid

STATIC=Path("/srv/atlas/static")
ROOT=Path("/srv/atlas")


class PrivatePreviewContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=(STATIC/"assets/cms.js").read_text(encoding="utf-8")
        cls.css=(STATIC/"assets/cms.css").read_text(encoding="utf-8")
        cls.html=(STATIC/"cms.html").read_text(encoding="utf-8")
        cls.browser=(ROOT/"tests/browser/cms-v525.spec.mjs").read_text(encoding="utf-8")

    def test_tab_is_accessible_to_all_four_editors_and_never_leaks_to_public_catalog(self):
        for value in ('data-editor-tab="preview"',
                      'data-editor-pane="preview"',
                      'function contentPreviewMarkup(kind,data)',
                      'function refreshContentPreview()',
                      "if(selected==='preview')refreshContentPreview()",
                      "const data=takeFields();",
                      "仅当前浏览器可见"):
            with self.subTest(value=value):
                self.assertIn(value,self.js)
        start=self.js.index("function refreshContentPreview()")
        end=self.js.index("function compareValue(",start)
        self.assertNotIn("await api(",self.js[start:end])
        self.assertNotIn("fetch(",self.js[start:end])
        self.assertIn("refreshContentPreview()",self.js)

    def test_gallery_preview_is_sanitized_and_switchable(self):
        for value in ('function sitePreviewPhotos(data)',
                      "if(validSiteShot(url)&&!seen.has(url))",
                      'data-preview-photo',
                      'data-preview-alt',
                      "button.setAttribute('aria-pressed'",
                      "hero.src=photo.dataset.previewSrc",
                      "function previewSafeHref(uri)"):
            with self.subTest(value=value):
                self.assertIn(value,self.js)
        self.assertIn("const title=h(data.name||data.title",self.js)
        self.assertIn("return '<span>'+h(text.slice(0,300))",self.js)

    def test_review_comparison_has_values_labels_and_first_release_guidance(self):
        for value in ("function inlineReviewComparison(item)",
                      "共 '+fields.length+' 项",
                      "当前公开版本",
                      "待审核版本",
                      "首次发布",
                      "data-editor-tab-link=\"preview\"",
                      "gallery:'页面截图'",
                      "inlineReviewComparison(item)"):
            with self.subTest(value=value):
                self.assertIn(value,self.js)
        self.assertIn(".cms-review-compare-cols",self.css)
        self.assertIn(".cms-review-inline",self.css)

    def test_mobile_and_existing_article_editor_remain_compatible(self):
        self.assertIn("@media(max-width:720px)",self.css)
        self.assertIn(".cms-public-card-sample{grid-template-columns",self.css)
        self.assertIn("if(kind==='article')return '<div class=\"cms-private-article\">'+previewMarkup(data)",self.js)
        self.assertIn("function previewArticleBlock(block)",self.js)
        self.assertIn("cms.js?v=5310",self.html)
        self.assertIn("cms.css?v=5310",self.html)

    def test_real_browser_tests_cover_preview_comparison_and_xss(self):
        for value in ("V52.7 site preview uses unsaved form data without publishing",
                      "V52.7 reviewer sees readable original-versus-proposed changes",
                      "V52.7 preview remains within mobile viewport",
                      "onerror=alert(1)",
                      "expect(records.site.status).toBe('review')"):
            with self.subTest(value=value):
                self.assertIn(value,self.browser)

    def test_review_baseline_for_original_file_stays_unpublished_on_draft(self):
        db=DB()
        uid=str(uuid.uuid4())
        original={"id":"demo-case","name":"Original","url":"https://example.com",
                  "sector":"Industrial","summary":"Public source"}
        draft={**original,"summary":"Private"}
        db.execute("INSERT INTO atlas_users(id,email,display_name,created_at) VALUES(?,?,?,?)",
                  (uid,"qa@demo.test","QA","2026-11-25"))
        db.execute("""INSERT INTO atlas_cms_entries
            (kind,slug,draft_json,published_json,status,revision,created_by,updated_by,created_at,updated_at)
            VALUES(?,?,?,NULL,'review',2,?,?,?,?)""",
            ("site","demo-case",json.dumps(draft),uid,uid,"2026-11-25","2026-11-25"))
        with patch.object(cms_routes,"ensure_cms"),             patch.object(cms_routes.user_auth,"db",return_value=db),             patch.object(cms_routes,"base_item",return_value=original):
            result=cms_routes.cms_item("site","demo-case",{"user_id":uid})
        self.assertEqual(result["published"],original)
        self.assertEqual(result["payload"]["summary"],"Private")

    def test_review_diff_baseline_matches_real_public_snapshot_and_archives(self):
        db=DB()
        uid=str(uuid.uuid4())
        slug="legacy-diff"
        source={"id":slug,"name":"Before","url":"https://example.com",
                "sector":"Industrial","summary":"Public text"}
        draft={**source,"name":"After","summary":"Private review text"}
        db.execute("INSERT INTO atlas_users(id,email,display_name,created_at) VALUES(?,?,?,?)",
                   (uid,"tester@demo.test","Tester","2026-11-25"))
        db.execute("""INSERT INTO atlas_cms_entries
            (kind,slug,draft_json,published_json,status,revision,created_by,updated_by,created_at,updated_at)
            VALUES(?,?,?,NULL,'review',2,?,?,?,?)""",
            ("site",slug,json.dumps(draft),uid,uid,"2026-11-25","2026-11-25"))
        app=FastAPI()
        cms_diff.register_diff_routes(app)
        endpoint=next(x.endpoint for x in app.routes if x.path=="/api/admin/content/{kind}/{slug}/diff")
        with patch.object(cms_routes,"require_admin",return_value={"user_id":uid}),\
             patch.object(cms_routes,"ensure_cms"),\
             patch.object(cms_routes.user_auth,"db",return_value=db),\
             patch.object(cms_routes,"base_item",return_value=source):
            old=endpoint("site",slug,object(),revision=0)
            self.assertEqual(old["baseline_label"],"当前公开版本")
            self.assertIn("summary",old["changed_fields"])
            self.assertTrue(any("Public text" in text
                                for chunk in old["chunks"] for text in chunk["before"]))
            db.execute("""INSERT INTO atlas_cms_history
                         (id,kind,slug,revision,action,actor_id,created_at,snapshot_json)
                         VALUES(?,?,?,?,?,?,?,?)""",
                       (str(uuid.uuid4()),"site",slug,1,"archive",uid,"2026-11-25",json.dumps(source)))
            # The archived original remains hidden even when a new draft is pending.
            db.execute("UPDATE atlas_cms_entries SET status='draft' WHERE kind='site' AND slug=?", (slug,))
            archived=endpoint("site",slug,object(),revision=0)
            self.assertEqual(archived["baseline_label"],"尚无公开版本")
            self.assertEqual(archived["summary"]["before_lines"],0)
            self.assertIsNone(cms_routes.cms_item("site",slug,{"user_id":uid})["published"])


if __name__=="__main__":
    unittest.main()
