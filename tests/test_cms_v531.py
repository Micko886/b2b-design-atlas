"""V53.1 article editing productivity and local image SEO safety regression."""
import re
import unittest
from pathlib import Path

STATIC=Path("/srv/atlas/static")
ROOT=Path("/srv/atlas")


class ArticleEditorV531(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=(STATIC/"assets/cms.js").read_text(encoding="utf-8")
        cls.css=(STATIC/"assets/cms.css").read_text(encoding="utf-8")
        cls.html=(STATIC/"cms.html").read_text(encoding="utf-8")
        cls.browser=(ROOT/"tests/browser/cms-v525.spec.mjs").read_text(encoding="utf-8")

    def test_one_serializer_handles_save_history_and_image_audit(self):
        self.assertIn("function readArticleSections()",self.js)
        self.assertIn("base.sections=readArticleSections()",self.js)
        self.assertIn("JSON.stringify(readArticleSections())",self.js)
        self.assertIn("const sections=readArticleSections(),issues=[]",self.js)
        self.assertIn("if(!base.sections.length)throw Error",self.js)

    def test_undo_history_is_scoped_to_article_and_has_bounded_size(self):
        for v in (
            "const articleStructureHistory={key:'',undo:[],redo:[]}",
            "function resetArticleStructureHistory()",
            "function ensureArticleStructureHistory()",
            "function captureArticleStructure()",
            "function restoreArticleStructure(direction)",
            "articleStructureHistory.undo.length>20",
            "articleStructureHistory.redo.length=0",
            "if(!can('edit')||state.selected?.kind!=='article'||state.busy)return false",
            "$('#cms-v51-sections').innerHTML=sections.map((section,i)=>articleSection(section,i,true)).join('')",
            "resetArticleStructureHistory();",
        ):
            with self.subTest(value=v):
                self.assertIn(v,self.js)
        self.assertIn("data-article-undo",self.js)
        self.assertIn("data-article-redo",self.js)

    def test_undo_snapshots_before_structural_actions(self):
        for v in (
            "if(!captureArticleStructure())return;\n   const rect=el.getBoundingClientRect();",
            "if(convert){if(captureArticleStructure())convertLegacyChapter(",
            "if(addBlock){if(!captureArticleStructure())return;",
            "if(target&&captureArticleStructure()){",
            "if(e.target.closest('[data-v51-add]')){if(!captureArticleStructure())return;",
            "if(!captureArticleStructure())return;\n     el.remove();",
        ):
            with self.subTest(value=v):
                self.assertIn(v,self.js)

    def test_image_alt_check_is_live_and_focusable(self):
        for v in (
            "function refreshArticleHealth()",
            "function focusArticleHealth(button)",
            "图片缺少替代文字 ALT",
            "图片块尚未选择图片",
            "旧版配图没有独立 ALT 字段",
            "建议补充图注或来源",
            "data-article-health-action",
            "cms-article-health-status",
            "cms-article-stat",
            "if(state.selected?.kind==='article')refreshArticleHealth();",
        ):
            with self.subTest(value=v):
                self.assertIn(v,self.js)
        self.assertIn("status.dataset.health=required?'warning':'ok'",self.js)
        self.assertNotIn("fetch(",self.js[self.js.index("function refreshArticleHealth()"):self.js.index("function focusArticleHealth(")])

    def test_private_preview_and_server_seo_audit_preserved(self):
        self.assertIn("function previewMarkup(article)",self.js)
        self.assertIn("function refreshArticlePreview()",self.js)
        self.assertIn("async function runSeoAudit()",self.js)
        self.assertIn("api('/api/admin/seo/check'",self.js)
        self.assertIn("仅记录最近 20 次结构操作",self.js)

    def test_accessibility_and_mobile_layout(self):
        self.assertIn(".cms-v531-editor-bar",self.css)
        self.assertIn(".cms-v531-media-health",self.css)
        self.assertIn("@media(max-width:680px)",self.css)
        self.assertIn("role=\"status\"",self.js)
        for t in ("V53.1 article structural undo redo restores chapters and blocks safely",
                  "V53.1 article image SEO inspector detects missing ALT",
                  "V53.1 legacy article conversion can be undone",
                  "V53.1 article toolbar and image audit fit mobile"):
            self.assertIn(t,self.browser)

    def test_asset_version_bump(self):
        self.assertRegex(self.html,r"cms\.js\?v=\d{4,}")
        self.assertRegex(self.html,r"cms\.css\?v=\d{4,}")


if __name__=="__main__":
    unittest.main()
