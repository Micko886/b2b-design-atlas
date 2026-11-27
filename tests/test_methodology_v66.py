"""V66: methodology page is readable, indexable and transparent."""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import seo_routes


class MethodologyV66(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        (root/"index.html").write_text(
            '<html><head><title>Initial</title><meta name="description" content="default">'
            '<script src="/assets/app.js?v=x" defer></script></head>'
            '<body><main><div class="shell loading">正在加载设计资源…</div></main></body></html>',
            encoding="utf-8")
        self.collection={"sites":{},"modules":{},"patterns":{},"articles":{
            "study":{"title":"Independent study","subtitle":"Public methods",
                     "published_at":"2026-11-24","sections":[]}}}
        p1=patch.object(seo_routes,"STATIC",root)
        p2=patch.object(seo_routes,"catalog",return_value=self.collection)
        p1.start();p2.start()
        self.addCleanup(p1.stop);self.addCleanup(p2.stop)

    def test_methods_page_has_canonical_content_and_aboutpage_schema(self):
        response=seo_routes.seo_document("methodology")
        html=response.body.decode()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers["X-Robots-Tag"],"index, follow")
        self.assertIn('<h1>研究方法与引用说明</h1>',html)
        self.assertIn("研究观点不是第三方品牌的官方背书",html)
        self.assertIn("不会仅为了搜索排名虚构更新时间",html)
        self.assertIn('href="/insights"',html)
        self.assertIn('href="/directory"',html)
        self.assertNotIn('src="/assets/app.js',html)
        self.assertNotIn("正在加载设计资源…",html)
        self.assertIn('rel="canonical" href="'+seo_routes.ORIGIN+'/methodology"',html)
        schema=json.loads(re.search(r'<script id="atlas-seo-schema" type="application/ld\+json">(.*?)</script>',html).group(1))
        self.assertEqual(schema["@type"],"AboutPage")

    def test_methodology_in_sitemap_and_ai_index_and_article(self):
        self.assertIn("/methodology",[path for path,_ in seo_routes.sitemap_items(self.collection)])
        self.assertIn(seo_routes.ORIGIN+"/methodology",seo_routes.llms_document(self.collection))
        article=seo_routes.seo_document("insights/study").body.decode()
        self.assertIn('href="/methodology"',article)

    def test_unrelated_private_routes_keep_noindex(self):
        response=seo_routes.seo_document("account")
        self.assertEqual(response.headers["X-Robots-Tag"],"noindex")


if __name__=="__main__":
    unittest.main()
