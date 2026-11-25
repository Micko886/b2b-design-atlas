"""V52.4 – Compact editors and unchanged published-content schemas."""
import unittest
from pathlib import Path
from app import cms_routes

STATIC=Path("/srv/atlas/static")


class UnifiedEditorUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=(STATIC/"assets/cms.js").read_text(encoding="utf-8")
        cls.css=(STATIC/"assets/cms.css").read_text(encoding="utf-8")
        cls.html=(STATIC/"cms.html").read_text(encoding="utf-8")

    def test_four_content_types_use_the_same_editor_shell(self):
        for needle in (
            "root.classList.toggle('cms-easy-mode',true)",
            "root.innerHTML=topbar+siteHeader+tabs",
            "item.kind==='site'?siteEditorForm(values,editable):simpleEditorForm(item.kind,values,editable)",
            "cms-easy-save-note",
            "data-close-editor",
            "data-editor-save",
            "data-editor-submit",
            "data-editor-pane=\"history\""):
            with self.subTest(needle=needle):
                self.assertIn(needle,self.js)
        # No second save bar or machine-generated JSON textarea in the editorial form.
        form=self.js[self.js.index("const form='<div class=\"cms-editor-content"):self.js.index("const schedule=item.schedule||null;")]
        self.assertNotIn("cms-json-advanced",form)
        self.assertNotIn("cms-form-actions",form)
        self.assertNotIn("cms-autosave-strip",form)

    def test_module_uses_real_site_names_and_image_picker(self):
        for needle in (
            "async function loadSiteChoices()",
            "await api('/api/source-library')",
            "if(result.kind==='module')await loadSiteChoices()",
            "state.kind==='module'&&state.siteChoices.length",
            "选择关联的网站案例",
            "['site_id','所属网站','text',true]",
            "['lesson','设计方法','long',true]",
            "easyImagePreview('screenshot_url',values,editable",
            "data-editor-pick-media"):
            with self.subTest(needle=needle):
                self.assertIn(needle,self.js)

    def test_pattern_preview_updates_without_publishing(self):
        for needle in (
            "cms-pattern-preview-card",
            "cms-preview-category",
            "cms-preview-title",
            "cms-preview-description",
            "cms-preview-principle",
            "function syncSimplePreview()",
            "set('#cms-preview-principle','principle'",
            "syncSiteTitle();refreshArticlePreview()"):
            with self.subTest(needle=needle):
                self.assertIn(needle,self.js)
        self.assertIn(".cms-easy-mode .cms-pattern-preview-card",self.css)

    def test_article_keeps_rich_editor_and_private_preview(self):
        for needle in (
            "simpleEditorForm(item.kind,values,editable)",
            "articleStudio(values,editable)",
            "easyImagePreview('cover_image',values,editable",
            "data-v512-preview",
            "function previewMarkup(article)",
            "function refreshArticlePreview()",
            "function articleSection("):
            with self.subTest(needle=needle):
                self.assertIn(needle,self.js)

    def test_blank_optional_reading_time_does_not_block_article_save(self):
        self.assertIn("else if(type==='number')base[name]=value===''?null:Number(value)",self.js)

    def test_draft_and_review_workflow_unchanged(self):
        for needle in (
            "async function persistDraft(automatic=false)",
            "expected_revision:target.revision",
            "async function transition(action)",
            "expected_revision:item.revision",
            "if(state.dirty||autosavePaused)",
            "await offerDraftRecovery(result)"):
            with self.subTest(needle=needle):
                self.assertIn(needle,self.js)

    def test_responsive_and_cache_freshness(self):
        self.assertIn("@media(max-width:880px)",self.css)
        self.assertIn(".cms-easy-mode .cms-easy-fields .cms-field select",self.css)
        self.assertIn("cms.js?v=5310",self.html)
        self.assertIn("cms.css?v=5310",self.html)


class UnchangedContentSchema(unittest.TestCase):
    def test_module_source_payload_remains_valid(self):
        payload={"id":"demo-module","title":"Product overview","site_id":"demo-site",
                 "category":"Product","lesson":"Use a clear hierarchy",
                 "screenshot_url":"/screenshots/sites/demo.webp",
                 "crop_px":[0,0,800,600]}
        result=cms_routes.cleaned("module","demo-module",payload)
        self.assertEqual(result["crop_px"],[0,0,800,600])
        self.assertEqual(result["screenshot_url"],payload["screenshot_url"])

    def test_blank_article_reading_time_is_valid(self):
        payload={"id":"demo-article","title":"Design Notes","subtitle":"Research summary",
                 "category":"research","author":"Atlas","sections":[{"title":"Introduction"}],
                 "reading_minutes":None}
        result=cms_routes.cleaned("article","demo-article",payload)
        self.assertIsNone(result["reading_minutes"])

    def test_pattern_associations_remain_array(self):
        payload={"id":"demo-pattern","title":"Feature comparison","family":"Compare",
                 "question":"How should buyers compare options?",
                 "principle":"Present key dimensions clearly",
                 "modules":["demo-module","other-module"]}
        result=cms_routes.cleaned("pattern","demo-pattern",payload)
        self.assertEqual(result["modules"],payload["modules"])


if __name__=="__main__":
    unittest.main()
