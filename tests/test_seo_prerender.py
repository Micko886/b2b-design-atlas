"""Search/AI crawler HTML fallback regression checks (no browser required)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import seo_routes


class SeoPrerenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.static = Path(self.tmp.name)
        (self.static / "index.html").write_text(
            '<!doctype html><html lang="zh-CN"><head><title>Atlas</title>'
            '<meta name="description" content="default"></head><body>'
            '<main id="app" tabindex="-1"><div class="shell loading">正在加载设计资源…</div></main>'
            '</body></html>', encoding="utf-8"
        )
        self.collection = {
            "sites": {
                "acme": {"id": "acme", "name": "Acme Manufacturing",
                         "summary": "可验证的工业制造案例",
                         "sector": "Manufacturing",
                         "screenshot_url": "/api/media/12345678-1234-1234-1234-123456789abc",
                         "url": "https://example.org"}
            },
            "modules": {
                "acme-hero": {"id": "acme-hero", "title": "工业首屏",
                              "lesson": "突出真实产品而非抽象概念",
                              "site_id": "acme",
                              "screenshot_url": "/screenshots/modules/acme-hero.webp"}
            },
            "patterns": {
                "trust-first": {"id": "trust-first", "title": "先展示信任依据",
                                "question": "如何建立信任？",
                                "principle": "用可核实的事实替代口号",
                                "modules": ["acme-hero"]}
            },
            "articles": {
                "sample": {
                    "id": "sample", "title": "研究 B2B 企业官网",
                    "subtitle": "从真实网站出发", "author": "B2B Atlas 编辑部",
                    "cover_site": "acme", "published_at": "2026-11-24",
                    "takeaways": ["先讲清产品价值"],
                    "sections": [
                        {"title": "正文第一章", "paragraphs": ["可检索的实质文章内容"],
                         "bullets": ["对照真实案例"]},
                        {"title": "块编辑器章节", "blocks": [
                            {"type": "heading", "text": "关键观察"},
                            {"type": "paragraph", "text": "内容块正文也可抓取"},
                            {"type": "list", "items": ["证据与论点"]}
                        ]}
                    ],
                    "references": [["website", "acme"], ["pattern", "trust-first"]]
                }
            }
        }
        self.static_patch = patch.object(seo_routes, "STATIC", self.static)
        self.catalog_patch = patch.object(seo_routes, "catalog", return_value=self.collection)
        self.static_patch.start()
        self.catalog_patch.start()
        self.addCleanup(self.static_patch.stop)
        self.addCleanup(self.catalog_patch.stop)

    def html(self, route):
        return seo_routes.seo_document(route).body.decode("utf-8")

    def test_home_and_all_four_public_catalogs_are_pre_rendered(self):
        for route, expected in [
            ("", "Acme Manufacturing"), ("websites", "可验证的工业制造案例"),
            ("sections", "工业首屏"), ("patterns", "先展示信任依据"),
            ("insights", "研究 B2B 企业官网")
        ]:
            with self.subTest(route=route):
                body = self.html(route)
                self.assertIn(expected, body)
                self.assertNotIn("正在加载设计资源…", body)
                self.assertIn('application/ld+json', body)
                self.assertIn('name="robots" content="index, follow"', body)

    def test_site_has_actual_cms_cover_and_original_source(self):
        body = self.html("websites/acme")
        self.assertIn("可验证的工业制造案例", body)
        self.assertIn("/api/media/12345678-1234-1234-1234-123456789abc", body)
        self.assertIn('href="https://example.org"', body)
        self.assertIn('href="https://b2b-design-atlas-preview.onrender.com/websites/acme"', body)
        self.assertIn("BreadcrumbList", body)

    def test_section_and_pattern_have_cross_links(self):
        self.assertIn('href="/websites/acme"', self.html("sections/acme-hero"))
        self.assertIn('href="/sections/acme-hero"', self.html("patterns/trust-first"))

    def test_article_has_complete_text_and_structured_metadata(self):
        body = self.html("insights/sample")
        for value in ["可检索的实质文章内容", "内容块正文也可抓取",
                      "先讲清产品价值", "对照真实案例", "证据与论点",
                      'href="/websites/acme"', "BreadcrumbList", '"@type": "Article"']:
            self.assertIn(value, body)
        self.assertIn('"datePublished": "2026-11-24"', body)
        self.assertIn('https://b2b-design-atlas-preview.onrender.com/api/media/12345678-1234-1234-1234-123456789abc', body)

    def test_nonpublic_content_is_never_added_to_main_or_sitemap(self):
        self.collection["articles"]["draft"] = {
            "title": "未审核内容",
            "subtitle": "不允许曝光"}
        # The injected catalog simulates the *published* view; production catalog()
        # is the boundary that excludes draft/review content.
        self.collection["articles"].pop("draft")
        self.assertNotIn("未审核内容", self.html("insights"))
        response = seo_routes.seo_document("insights/draft")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex")
        private = self.html("account")
        self.assertIn('name="robots" content="noindex, follow"', private)
        self.assertNotIn("Acme Manufacturing", private)

    def test_untrusted_fields_are_html_escaped_and_nonlocal_images_ignored(self):
        self.collection["sites"]["acme"]["name"] = '<img src=x onerror=alert(1)>'
        self.collection["sites"]["acme"]["summary"] = '<script>alert("x")</script>'
        self.collection["sites"]["acme"]["screenshot_url"] = 'javascript:alert(1)'
        body = self.html("websites/acme")
        self.assertNotIn('<img src=x onerror=alert(1)>', body)
        self.assertNotIn('<script>alert("x")</script>', body)
        self.assertNotIn('javascript:alert(1)', body)
        self.assertIn('&lt;script&gt;', body)


if __name__ == "__main__":
    unittest.main()
