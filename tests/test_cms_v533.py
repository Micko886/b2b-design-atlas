"""V53.3 case editor contract: simple by default without losing gallery data."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "cms.js"
HTML = ROOT / "frontend" / "cms.html"


class SiteEditorV533Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = JS.read_text(encoding="utf-8")
        cls.html = HTML.read_text(encoding="utf-8")

    def test_cover_remains_primary_and_advanced_gallery_is_optional(self):
        site_form = self.js.split("function siteEditorForm(values,editable){", 1)[1].split(
            "// V52.4", 1
        )[0]
        self.assertIn("上传或更换图片", site_form)
        self.assertIn("添加更多页面截图", site_form)
        self.assertIn("默认只展示一张案例封面", site_form)
        self.assertIn('<details class="cms-easy-advanced cms-easy-gallery">', site_form)
        self.assertIn("data-field=\"gallery\"", site_form)
        self.assertIn("</div></section></details>", site_form)
        self.assertIn("更多设置", site_form)
        self.assertLess(site_form.index("上传或更换图片"), site_form.index("添加更多页面截图"))

    def test_gallery_still_serializes_and_has_editor_actions(self):
        self.assertIn("function galleryValue()", self.js)
        self.assertIn("function syncGalleryLabels()", self.js)
        self.assertIn("data-gallery-add", self.js)
        self.assertIn("data-gallery-cover", self.js)
        self.assertIn("data-gallery-remove", self.js)

    def test_assets_use_new_version(self):
        self.assertIn("/assets/cms.js?v=5420", self.html)
        self.assertIn("/assets/cms.css?v=5420", self.html)


if __name__ == "__main__":
    unittest.main()
