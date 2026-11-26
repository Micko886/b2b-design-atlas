"""V54 editor tabs: keyboard navigation and labelled panels."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

class EditorTabContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js=(ROOT/"frontend/cms.js").read_text(encoding="utf-8")
        cls.html=(ROOT/"frontend/cms.html").read_text(encoding="utf-8")
        cls.css=(ROOT/"frontend/cms.css").read_text(encoding="utf-8")

    def test_tabs_are_linked_and_support_keyboard_navigation(self):
        self.assertIn("button.setAttribute('aria-controls',paneId)",self.js)
        self.assertIn("panel.setAttribute('aria-labelledby',tabId)",self.js)
        self.assertIn("panel.setAttribute('role','tabpanel')",self.js)
        self.assertIn("event.key==='ArrowRight'",self.js)
        self.assertIn("event.key==='ArrowLeft'",self.js)
        self.assertIn("event.key==='Home'",self.js)
        self.assertIn("event.key==='End'",self.js)

    def test_keyboard_and_mobile_visuals(self):
        self.assertIn('.atlas-v521-editor-tabs>button:focus-visible',self.css)
        self.assertIn('scroll-snap-type:x proximity',self.css)
        self.assertIn('/assets/cms.js?v=5480',self.html)
        self.assertIn('/assets/cms.css?v=5480',self.html)

if __name__=="__main__":
    unittest.main()
