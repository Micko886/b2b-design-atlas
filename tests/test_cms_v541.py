"""V54.1 visual hierarchy and progressive batch controls contracts."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class Cms541Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=(ROOT/"frontend/cms.js").read_text(encoding="utf-8")
        cls.css=(ROOT/"frontend/cms.css").read_text(encoding="utf-8")
        cls.html=(ROOT/"frontend/cms.html").read_text(encoding="utf-8")

    def test_batch_controls_are_hidden_until_selection(self):
        self.assertIn("bar.dataset.hasSelection=chosen?'true':'false'",self.js)
        self.assertIn("$('#cms-bulk-action').hidden=!chosen",self.js)
        self.assertIn("$('#cms-bulk-run').hidden=!chosen",self.js)
        self.assertIn('cms-v51-bulk [hidden]{display:none!important}',self.css)

    def test_source_only_records_have_no_batch_selector(self):
        self.assertIn("mode==='admin'&&item.status!=='source'",self.js)

    def test_review_queue_summary_and_consistent_editor(self):
        self.assertIn('status.innerHTML=',self.js)
        self.assertIn('<strong>待审核 ',self.js)
        self.assertIn('<h3>基本信息</h3>',self.js)

    def test_versioned_assets(self):
        self.assertIn('/assets/cms.js?v=5480',self.html)
        self.assertIn('/assets/cms.css?v=5480',self.html)

if __name__=='__main__':
    unittest.main()
