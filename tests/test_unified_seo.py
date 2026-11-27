"""Unified CMS SEO metadata: all four editors, public outputs, and safety."""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from app import cms_routes, seo_routes


PHOTO = "/api/media/12345678-1234-1234-1234-123456789abc"


class UnifiedSeoTests(unittest.TestCase):
    def setUp(self):
        self.base = {
            "sites": {"acme": {"id": "acme", "name": "Acme", "url": "https://example.org",
                                "sector": "Industrial", "summary": "Original industrial description",
                                "screenshot_url": "/screenshots/sites/acme.webp"}},
            "modules": {"hero": {"id": "hero", "title": "Hero",
                                  "site_id": "acme", "category": "Hero",
                                  "lesson": "Original module lesson",
                                  "screenshot_url": "/screenshots/modules/hero.webp"}},
            "patterns": {"method": {"id": "method", "title": "Method",
                                    "family": "UX", "question": "Original question",
                                    "principle": "Original principle", "modules": ["hero"]}},
            "articles": {"guide": {"id": "guide", "title": "Guide", "subtitle": "Original introduction",
                                   "category": "methods", "author": "Editorial",
                                   "sections": [{"title": "Chapter", "paragraphs": ["One paragraph"]}],
                                   "tags": ["Original topic"], "cover_site": "acme"}}
        }
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        template = Path(tmp.name) / "index.html"
        template.write_text(
            '<html lang="zh-CN"><head><title>Initial</title>'
            '<meta name="description" content="Initial"></head><body>'
            '<main id="app"><div class="shell loading">正在加载设计资源…</div></main>'
            '</body></html>', encoding="utf-8")
        static_patch = patch.object(seo_routes, "STATIC", Path(tmp.name))
        catalog_patch = patch.object(seo_routes, "catalog", return_value=self.base)
        static_patch.start()
        catalog_patch.start()
        self.addCleanup(static_patch.stop)
        self.addCleanup(catalog_patch.stop)

    def test_all_content_types_accept_optional_tdk(self):
        for kind,slug,key in [
            ("site","acme","sites"), ("module","hero","modules"),
            ("pattern","method","patterns"), ("article","guide","articles")
        ]:
            with self.subTest(kind=kind):
                item = dict(self.base[key][slug], seo_title="Custom headline",
                            seo_description="Custom description",
                            seo_keywords="Product, B2B", seo_image=PHOTO)
                cleaned = cms_routes.cleaned(kind, slug, item)
                self.assertEqual(cleaned["seo_title"], "Custom headline")
                self.assertEqual(cleaned["seo_keywords"], "Product, B2B")
                self.assertEqual(cleaned["seo_image"], PHOTO)

    def test_invalid_seo_inputs_are_rejected_for_every_kind(self):
        for kind,slug,key in [
            ("site","acme","sites"), ("module","hero","modules"),
            ("pattern","method","patterns"), ("article","guide","articles")
        ]:
            for field,value in [
                ("seo_title", "x" * 101),
                ("seo_description", "x" * 301),
                ("seo_keywords", "x" * 241),
                ("seo_title", ["not a string"]),
                ("seo_image", "https://attacker.example/evil.svg"),
                ("seo_image", "javascript:alert(1)"),
                ("seo_image", "/screenshots/../../not-an-image")
            ]:
                with self.subTest(kind=kind,field=field):
                    item = {**self.base[key][slug], field:value}
                    with self.assertRaises(HTTPException) as ctx:
                        cms_routes.cleaned(kind,slug,item)
                    self.assertEqual(ctx.exception.status_code,422)

    def test_server_renders_custom_tdk_and_social_images_for_four_types(self):
        paths = [("websites","sites","acme"),("sections","modules","hero"),
                 ("patterns","patterns","method"),("insights","articles","guide")]
        for kind,key,slug in paths:
            with self.subTest(kind=kind):
                self.base[key][slug].update({
                    "seo_title": "Custom TDK title "+slug,
                    "seo_description": "Unique description "+slug,
                    "seo_keywords": "Industrial, UX",
                    "seo_image": PHOTO})
                response = seo_routes.seo_document(kind+"/"+slug)
                page = response.body.decode("utf-8")
                self.assertEqual(response.status_code,200)
                self.assertIn("Custom TDK title "+slug, page)
                self.assertIn("Unique description "+slug, page)
                self.assertIn("https://b2b-design-atlas-preview.onrender.com"+PHOTO,page)
                schema_match=re.search(r'<script id="atlas-seo-schema" type="application/ld\+json">(.*?)</script>',page)
                self.assertIsNotNone(schema_match)
                schema=json.loads(schema_match.group(1))
                node=schema["@graph"][0]
                self.assertEqual(node["keywords"],"Industrial, UX")

    def test_missing_overrides_keep_original_fallback(self):
        for route,wanted in [
            ("websites/acme","Original industrial description"),
            ("sections/hero","Original module lesson"),
            ("patterns/method","Original question"),
            ("insights/guide","Original introduction")
        ]:
            with self.subTest(route=route):
                self.assertIn(wanted,seo_routes.seo_document(route).body.decode("utf-8"))

    def test_ignored_external_share_image_does_not_enter_metadata(self):
        self.base["sites"]["acme"]["seo_image"]="https://evil.invalid/share.jpg"
        doc=seo_routes.seo_document("websites/acme").body.decode("utf-8")
        self.assertNotIn("evil.invalid",doc)
        self.assertIn("/screenshots/sites/acme.webp",doc)


if __name__=="__main__":
    unittest.main()
