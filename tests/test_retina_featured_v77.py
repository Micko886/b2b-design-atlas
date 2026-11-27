"""V77: four true Retina homepage screenshots, not model-generated assets.

The browser screenshot acquisition happens in a standalone GitHub Actions
capture workflow. These Docker regressions use only Pillow and static strings,
never Playwright or UI browser automation.
"""
import json
import unittest
from pathlib import Path

from PIL import Image
from app import seo_routes

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "screenshots"
FOUR = ("vast", "figure-robotics", "fictiv", "skydio")


class RetinaFeaturedV77(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((CAPTURE/"quality-v77"/"report.json").read_text(encoding="utf-8"))
        cls.by_site = {r["site"]:r for r in cls.report["results"]}

    def test_all_four_sources_were_recaptured_as_real_browser_evidence(self):
        self.assertEqual(set(self.by_site),set(FOUR))
        self.assertIn("real Chromium browser",self.report["source"])
        for site in FOUR:
            with self.subTest(site=site):
                result=self.by_site[site]
                self.assertEqual(result["status"],"captured")
                self.assertTrue(result["source"].startswith("https://"))
                self.assertEqual(result["detail"],"2880x1840")
                self.assertEqual(result["card"],"800x488")
                self.assertTrue(result.get("captured_at"))

    def test_detail_screenshots_are_genuine_double_density_not_upscaled_css(self):
        for site in FOUR:
            with self.subTest(site=site):
                path=CAPTURE/"sites"/(site+".webp")
                self.assertTrue(path.is_file())
                self.assertLess(path.stat().st_size,1_500_000)
                with Image.open(path) as im:
                    self.assertEqual(im.format,"WEBP")
                    self.assertEqual(im.size,(2880,1840))

    def test_retina_card_has_exact_display_ratio_and_reasonable_file_size(self):
        for site in FOUR:
            with self.subTest(site=site):
                path=CAPTURE/"featured"/(site+"-800.webp")
                self.assertTrue(path.is_file())
                self.assertLess(path.stat().st_size,220_000)
                with Image.open(path) as im:
                    self.assertEqual(im.format,"WEBP")
                    self.assertEqual(im.size,(800,488))

    def test_only_four_originals_get_derivative_previews(self):
        generated={p.name for p in (CAPTURE/"featured").glob("*.webp")}
        self.assertEqual(generated,{site+"-800.webp" for site in FOUR})

    def test_cms_image_overrides_are_not_swapped_for_static_previews(self):
        app=(ROOT/"static"/"assets"/"app.js").read_text(encoding="utf-8")
        self.assertIn("function featuredCardImage(s)",app)
        self.assertIn("retinaFeaturedSites.has(s.id)",app)
        self.assertIn("s.screenshot_url==='/screenshots/sites/'+s.id+'.webp'",app)
        self.assertIn("return s?.screenshot_url;",app)
        self.assertIn("img(isSite?featuredCardImage(x):entityImage(x))",app)
        self.assertIn("img(featuredCardImage(s))",app)
        self.assertIn("featured.slice(0,3)",app)
        html=(ROOT/"static"/"index.html").read_text(encoding="utf-8")
        self.assertIn("/assets/app.js?v=retina-v77-1",html)

    def test_public_canonical_og_still_uses_high_resolution_source(self):
        catalog=seo_routes.base_catalog()
        for site in FOUR:
            with self.subTest(site=site):
                item=catalog["sites"][site]
                self.assertEqual(item["screenshot_url"],"/screenshots/sites/"+site+".webp")
                record=seo_routes.seo_record("/websites/"+site,catalog)
                self.assertTrue(record["indexed"])
                self.assertEqual(record["image"],"/screenshots/sites/"+site+".webp")
                self.assertEqual(
                    seo_routes.image_dimensions(record["image"]),
                    (2880,1840))


if __name__=="__main__":
    unittest.main()
