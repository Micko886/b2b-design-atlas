"""V53.8 screen hierarchy static regression gates."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class CmsV538Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=(ROOT/"frontend/cms.js").read_text(encoding="utf-8")
        cls.css=(ROOT/"frontend/cms.css").read_text(encoding="utf-8")
        cls.html=(ROOT/"frontend/cms.html").read_text(encoding="utf-8")

    def test_filters_have_actionable_empty_state(self):
        self.assertIn('data-clear-content-filters',self.js)
        self.assertIn('没有匹配的内容',self.js)
        self.assertIn("state.q='';state.status='';",self.js)

    def test_reviewer_and_published_content_get_contextual_actions(self):
        self.assertIn("s==='review'?'review':",self.js)
        self.assertIn('data-editor-state-link',self.js)
        self.assertIn('previousStageLink.hidden=true',self.js)
        self.assertIn('submitButton.hidden=false',self.js)

    def test_updated_assets_and_layout(self):
        self.assertIn('/assets/cms.js?v=5380',self.html)
        self.assertIn('/assets/cms.css?v=5380',self.html)
        self.assertIn('.cms-empty-results',self.css)
        self.assertIn('.cms-edit-quick-actions [hidden]{display:none!important}',self.css)

if __name__=="__main__":
    unittest.main()
