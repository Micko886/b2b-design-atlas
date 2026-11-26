"""V54.2 visual consistency and screenshot fallback contracts."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class Cms542(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=(ROOT/'frontend/cms.js').read_text(encoding='utf-8')
        cls.css=(ROOT/'frontend/cms.css').read_text(encoding='utf-8')
        cls.html=(ROOT/'frontend/cms.html').read_text(encoding='utf-8')

    def test_missing_cover_is_safe(self):
        self.assertIn("thumb.classList.add('cms-thumb-missing')",self.js)
        self.assertIn("thumb.innerHTML=icon(kinds[state.kind].icon)",self.js)

    def test_screenshot_fit_and_review_modal(self):
        self.assertIn('object-fit:contain',self.css)
        self.assertIn('#cms-review-dialog.cms-v530-dialog',self.css)
        self.assertIn('max-height:calc(100dvh - 24px)',self.css)

    def test_assets(self):
        self.assertIn('/assets/cms.js?v=5470',self.html)
        self.assertIn('/assets/cms.css?v=5470',self.html)

if __name__=='__main__':
    unittest.main()
