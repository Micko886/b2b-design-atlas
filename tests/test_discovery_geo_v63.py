"""V63: discovery metadata must be valid, public and evidence-based."""
import json
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from app import seo_routes

class DiscoveryGeoV63(unittest.TestCase):
    def setUp(self):
        self.public={
            "sites":{"factory":{"name":"Factory","summary":"Case study"},
                     "bad?slug":{"name":"Invalid slug"}},
            "modules":{},"patterns":{},
            "articles":{
                "published":{"title":"公开研究","published_at":"2026-11-24","updated_at":"2026-11-26"},
                "bad-date":{"title":"Bad date","published_at":"2026-13-55","updated_at":"tomorrow"},
                "older-edit":{"title":"Older edit","published_at":"2026-11-25","updated_at":"2026-11-20"},
                "bad]link":{"title":"Invalid link"}
            }
        }
        app=FastAPI()
        seo_routes.register_seo_routes(app)
        self.routes={r.path:r.endpoint for r in app.routes if hasattr(r,"path")}

    def test_sitemap_dates_and_url_escaping(self):
        with patch.object(seo_routes,"catalog",return_value=self.public),patch.object(seo_routes,"ORIGIN","https://atlas.example.org"):
            response=self.routes["/sitemap.xml"]()
        root=ET.fromstring(response.body.decode())
        ns={"s":"http://www.sitemaps.org/schemas/sitemap/0.9"}
        entries={}
        for url in root.findall("s:url",ns):
            loc=url.find("s:loc",ns).text
            mod=url.find("s:lastmod",ns)
            entries[loc]=mod.text if mod is not None else None
        self.assertEqual(entries["https://atlas.example.org/insights/published"],"2026-11-26")
        self.assertEqual(entries["https://atlas.example.org/insights/older-edit"],"2026-11-25")
        self.assertIsNone(entries["https://atlas.example.org/insights/bad-date"])
        self.assertNotIn("bad?slug",response.body.decode())
        self.assertNotIn("bad]link",response.body.decode())

    def test_llms_index_uses_only_published_catalog(self):
        with patch.object(seo_routes,"catalog",return_value=self.public),patch.object(seo_routes,"ORIGIN","https://atlas.example.org"):
            response=self.routes["/llms.txt"]()
        body=response.body.decode()
        self.assertIn("# B2B Atlas",body)
        self.assertIn("https://atlas.example.org/insights/published",body)
        self.assertIn("https://atlas.example.org/sitemap.xml",body)
        self.assertNotIn("bad]link",body)
        self.assertNotIn("bad?slug",body)
        self.assertIn("审核中草稿",body)
        self.assertIn("max-age=3600",response.headers["Cache-Control"])

    def test_social_meta_and_no_fabricated_primary_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,"index.html").write_text(
                '<html><head><title>Old</title><meta name="description" content="Old"></head>'
                '<body><div class="shell loading">正在加载设计资源…</div></body></html>',encoding="utf-8")
            with patch.object(seo_routes,"STATIC",Path(tmp)),patch.object(seo_routes,"catalog",return_value=self.public):
                doc=seo_routes.seo_document("websites/factory").body.decode()
        m=re.search(r'<script id="atlas-seo-schema" type="application/ld\+json">(.*?)</script>',doc)
        graph=json.loads(m.group(1))["@graph"]
        page=next(node for node in graph if node["@type"]=="WebPage")
        self.assertNotIn("primaryImageOfPage",page)
        self.assertIn('property="og:locale" content="zh_CN"',doc)
        self.assertIn('name="twitter:description"',doc)
        self.assertIn('property="og:image:alt"',doc)

    def test_invalid_dates_do_not_enter_jsonld(self):
        record={"title":"Research","description":"Example","kind":"article",
                "published":"2026-13-55","path":"/insights/bad-date","indexed":True}
        c={"articles":{"bad-date":{"updated_at":"2026-99-99"}}}
        schema=seo_routes.seo_schema("/insights/bad-date",record,c,seo_routes.ORIGIN+"/insights/bad-date","")
        article=next(node for node in schema["@graph"] if node["@type"]=="Article")
        self.assertNotIn("datePublished",article)
        self.assertNotIn("dateModified",article)

    def test_robots_keep_public_readable(self):
        robots=self.routes["/robots.txt"]().body.decode()
        self.assertIn("Disallow: /api/admin",robots)
        self.assertNotIn("Disallow: /insights",robots)
        self.assertNotIn("Disallow: /api/media",robots)

if __name__=="__main__":unittest.main()
