"""V53.5 list-to-editor navigation regression checks."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CmsNavigationV535Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = (ROOT / "frontend" / "cms.js").read_text(encoding="utf-8")
        cls.css = (ROOT / "frontend" / "cms.css").read_text(encoding="utf-8")
        cls.html = (ROOT / "frontend" / "cms.html").read_text(encoding="utf-8")

    def test_editor_entry_starts_at_top_and_focuses_heading(self):
        selected = self.js.split("async function selectItem(", 1)[1].split("// One serializer", 1)[0]
        self.assertIn("contentListScrollY=window.scrollY", selected)
        self.assertIn("window.scrollTo({top:0,behavior:'instant'})", selected)
        self.assertIn("heading.focus({preventScroll:true})", selected)

    def test_return_restores_list_position_and_focus(self):
        close = self.js.split("function closeEditor(", 1)[1].split("function rowImage", 1)[0]
        self.assertIn("window.scrollTo({top:contentListScrollY,behavior:'instant'})", close)
        self.assertIn("listHeading.focus({preventScroll:true})", close)
        self.assertIn("if(state.dirty&&!confirm(", close)

    def test_help_is_available_but_stays_collapsed(self):
        self.assertIn('<details class="cms-workflow-guide"', self.html)
        self.assertNotIn(
            'body[data-cms-mode="admin"] .cms-metrics,\n'
            'body[data-cms-mode="admin"] .cms-workflow-guide{display:none!important}',
            self.css,
        )
        self.assertIn('.cms-workflow-guide[hidden]{display:none!important}', self.css)

    def test_asset_versions(self):
        self.assertIn("/assets/cms.js?v=5490", self.html)
        self.assertIn("/assets/cms.css?v=5490", self.html)


if __name__ == "__main__":
    unittest.main()
