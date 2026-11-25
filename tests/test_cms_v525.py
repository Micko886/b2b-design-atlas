"""V52.5 · Human-friendly CMS index, image status, narrow-screen and browser smoke contracts."""
import re
import unittest
from pathlib import Path

ROOT=Path("/srv/atlas")
STATIC=ROOT/"static"


class CMSV525VisualAndInteractionContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=(STATIC/"cms.html").read_text(encoding="utf-8")
        cls.css=(STATIC/"assets/cms.css").read_text(encoding="utf-8")
        cls.js=(STATIC/"assets/cms.js").read_text(encoding="utf-8")
        cls.playwright=(ROOT/"tests/browser/cms-v525.spec.mjs").read_text(encoding="utf-8")

    def test_content_index_leads_with_records_not_duplicate_dashboard(self):
        self.assertIn("点击一条记录进入编辑页",self.html)
        self.assertIn("选择栏目和内容",self.html)
        self.assertIn('body[data-cms-mode="admin"] .cms-metrics',self.css)
        self.assertIn('body[data-cms-mode="admin"] .cms-workflow-guide',self.css)
        self.assertIn("编辑页，可直接修改文字、图片并保存草稿",self.js)

    def test_errors_remain_visible_even_when_normal_notice_is_hidden(self):
        self.assertIn("function setNotice(text,error=false)",self.js)
        self.assertIn("el.hidden=mode==='admin'&&!error",self.js)
        self.assertIn("setNotice('无法读取后台内容：'+e.message,true)",self.js)
        self.assertIn(".cms-notice-error:not([hidden])",self.css)

    def test_media_library_reports_loaded_and_finished_states(self):
        self.assertIn("媒体库暂无图片 · 可上传",self.js)
        self.assertIn("已加载 '+items.length+' 张图片",self.js)
        self.assertIn("const refreshed=await refreshMedia()",self.js)
        self.assertIn("上传完成：成功 ",self.js)
        self.assertLess(self.js.index("const refreshed=await refreshMedia()"),
                        self.js.index("$('#cms-media-status').textContent='上传完成：成功"))
        self.assertIn("return false",self.js)

    def test_narrow_mobile_layout_clamps_image_and_header(self):
        self.assertIn("@media(max-width:420px)",self.css)
        self.assertIn(".cms-easy-mode .cms-easy-shot{width:100%;min-width:0;max-width:100%",self.css)
        self.assertIn(".masthead-left .masthead-breadcrumb",self.css)
        self.assertIn(".masthead-right #cms-logout",self.css)

    def test_real_browser_smoke_has_key_editor_flows(self):
        for term in ("site editor autosaves and reviewer transitions",
                     "media picker loads, uploads and adds a gallery entry",
                     "320px mobile editor does not overflow",
                     "content index shows records directly",
                     "test('",
                     "page.route('**/*'",
                     "mockCms(page)"):
            with self.subTest(term=term):
                self.assertIn(term,self.playwright)
        for kind in ("site","module","pattern","article"):
            self.assertIn(kind+":{id:'demo-",self.playwright)
        self.assertIn("no production writes",self.playwright)

    def test_asset_versions_and_selector_safety(self):
        self.assertIn("cms.js?v=5300",self.html)
        self.assertIn("cms.css?v=5300",self.html)
        self.assertEqual(re.findall(r"for\s*\([^)]*\bof\s+\$\(",self.js),[])


if __name__=="__main__":
    unittest.main()
