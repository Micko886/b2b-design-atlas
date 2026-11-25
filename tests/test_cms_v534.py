"""V53.4 regression checks for CMS boot and simpler navigation."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CmsShellV534Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = (ROOT / "frontend" / "cms.js").read_text(encoding="utf-8")
        cls.html = (ROOT / "frontend" / "cms.html").read_text(encoding="utf-8")
        cls.css = (ROOT / "frontend" / "cms.css").read_text(encoding="utf-8")

    def test_dom_helpers_have_unique_names(self):
        self.assertIn("const $=(q,root=document)=>root.querySelector(q), $$=(q,root=document)=>Array.from(root.querySelectorAll(q));", self.js)
        self.assertNotIn("const $=(q,root=document)=>root.querySelector(q), $=(q,root=document)", self.js)

    def test_editor_guide_is_optional_without_losing_steps(self):
        self.assertIn('<details class="cms-workflow-guide"', self.html)
        self.assertIn('<summary>如何编辑和发布内容？', self.html)
        self.assertIn("4. 审核并发布", self.html)
        self.assertIn(".cms-workflow-steps", self.css)

    def test_sidebar_has_no_duplicate_analytics_link(self):
        self.assertNotIn('href="/admin#traffic"', self.html)
        for item in ("工作台", "内容管理", "媒体资源", "审核发布", "运营中心", "系统设置"):
            self.assertIn(item, self.html)

    def test_versioned_assets(self):
        self.assertIn('/assets/cms.js?v=5360', self.html)
        self.assertIn('/assets/cms.css?v=5350', self.html)


if __name__ == "__main__":
    unittest.main()
