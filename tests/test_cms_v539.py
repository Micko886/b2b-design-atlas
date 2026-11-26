"""V53.9 review comparison and restore UX contracts."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class HistoryUX(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=(ROOT/"frontend/cms.js").read_text(encoding="utf-8")
        cls.html=(ROOT/"frontend/cms.html").read_text(encoding="utf-8")

    def test_compare_and_restore_are_separate_actions(self):
        self.assertIn('data-review-diff=',self.js)
        self.assertIn('恢复为新草稿',self.js)
        self.assertIn('cms-history-current',self.js)
        self.assertIn("if(mode!=='admin'||!can('edit')",self.js)

    def test_restore_uses_expected_revision_and_guards_current(self):
        self.assertIn('targetRevision>=state.selected.revision',self.js)
        self.assertIn('expected_revision:target.revision,revision:targetRevision',self.js)

    def test_diff_is_read_only_and_avoids_stale_updates(self):
        self.assertIn('requestId!==activeDiffRequest',self.js)
        self.assertIn('比较内容版本',self.html)
        self.assertIn('cms-diff-right-title',self.html)

    def test_assets_are_current(self):
        self.assertIn('/assets/cms.js?v=5400',self.html)
        self.assertIn('/assets/cms.css?v=5400',self.html)

if __name__=='__main__':
    unittest.main()
