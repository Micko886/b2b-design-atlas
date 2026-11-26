"""V54.2 visual consistency and screenshot fallback contracts."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class Cms542(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Repository tests read frontend/, while the deploy image places these files
        # under static/assets and static/ respectively.
        is_source=(ROOT/'frontend/cms.js').is_file()
        asset_dir=ROOT/'frontend' if is_source else ROOT/'static/assets'
        html_path=ROOT/'frontend/cms.html' if is_source else ROOT/'static/cms.html'
        cls.js=(asset_dir/'cms.js').read_text(encoding='utf-8')
        cls.css=(asset_dir/'cms.css').read_text(encoding='utf-8')
        cls.html=html_path.read_text(encoding='utf-8')

    def test_missing_cover_is_safe(self):
        self.assertIn("thumb.classList.add('cms-thumb-missing')",self.js)
        self.assertIn("thumb.innerHTML=icon(kinds[state.kind].icon)",self.js)

    def test_screenshot_fit_and_review_modal(self):
        self.assertIn('object-fit:contain',self.css)
        self.assertIn('#cms-review-dialog.cms-v530-dialog',self.css)
        self.assertIn('max-height:calc(100dvh - 24px)',self.css)

    def test_assets(self):
        self.assertIn('/assets/cms.js?v=5530',self.html)
        self.assertIn('/assets/cms.css?v=5530',self.html)

    def test_bulk_selection_is_action_and_role_aware(self):
        self.assertIn("const bulkActionRules=",self.js)
        self.assertIn("function bulkEligibility(",self.js)
        self.assertIn("visibleEligible=listFiltered().filter(x=>bulkEligibility(x).ok)",self.js)
        self.assertIn("items.some(x=>!bulkEligibility(x,action).ok)",self.js)
        self.assertIn("state.selectedSlugs.size>=20",self.js)
        self.assertIn('id="cms-bulk-clear"',self.html)
        self.assertIn('id="cms-bulk-help"',self.html)
        self.assertIn('选择当前符合条件的内容（最多 20 条）',self.html)

if __name__=='__main__':
    unittest.main()
