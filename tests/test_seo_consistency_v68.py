"""V67/68: image size evidence, safe RSS and deploy-time SEO route coherence."""
import re
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from fastapi import FastAPI
from app import seo_routes,seo_feed


class DiscoveryV68(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/"index.html").write_text(
            '<html><head><title>Original</title><meta name="description" content="old">'
            '<script src="/assets/app.js?v=seo-geo-v62-1" defer></script></head><body>'
            '<main><div class="shell loading">正在加载设计资源…</div></main></body></html>',
            encoding="utf-8")
        photo=self.root/"screenshots"/"sites"/"v67-test-cover.png"
        photo.parent.mkdir(parents=True)
        Image.new("RGB",(640,360)).save(photo)
        self.photo="/screenshots/sites/v67-test-cover.png"
        self.c={
            "sites":{"sample":{"name":"Industrial source","summary":"Source for the article",
                               "url":"https://source.example","screenshot_url":self.photo}},
            "modules":{"module":{"title":"Engineering opening","site_id":"sample",
                                 "lesson":"Product and evidence"}},
            "patterns":{"pattern":{"title":"Documentation pattern","question":"Why show detail?",
                                   "modules":["module"]}},
            "articles":{
                "research":{"title":"Robotics R&D <case>","subtitle":"A field guide to reliable source links & references.",
                            "published_at":"2026-11-25","sections":[{"title":"Proof",
                            "blocks":[{"type":"paragraph","text":"Verifiable public research."}]}]},
                "draft-missing-date":{"title":"Date not yet confirmed","subtitle":"Public without a date",
                                      "published_at":"2026-99-99","sections":[]}
            }
        }
        p1=patch.object(seo_routes,"STATIC",self.root)
        p2=patch.object(seo_routes,"BASE",self.root)
        p3=patch.object(seo_routes,"catalog",return_value=self.c)
        for obj in (p1,p2,p3):
            obj.start()
            self.addCleanup(obj.stop)

    def test_real_screenshot_dimensions_are_used_only_when_verified(self):
        self.assertEqual(seo_routes.image_dimensions(self.photo),(640,360))
        body=seo_routes.seo_document("websites/sample").body.decode()
        self.assertIn('property="og:image:width" content="640"',body)
        self.assertIn('property="og:image:height" content="360"',body)
        self.assertIn('property="og:image:type" content="image/png"',body)
        self.assertIn('name="twitter:image:alt"',body)
        other=seo_routes.seo_document("insights/research").body.decode()
        self.assertNotIn('property="og:image:width"',other)
        self.assertIsNone(seo_routes.image_dimensions("/api/media/12345678-1234-1234-1234-123456789abc"))

    def test_rss_xml_is_safe_and_uses_only_published_articles(self):
        app=FastAPI()
        seo_routes.register_seo_routes(app)
        route=next(x.endpoint for x in app.routes if getattr(x,"path","")=="/feed.xml")
        response=route()
        self.assertEqual(response.status_code,200)
        self.assertIn("application/rss+xml",response.headers["content-type"])
        xml=response.body.decode()
        doc=ET.fromstring(xml)
        items=doc.findall("./channel/item")
        self.assertEqual(len(items),2)
        self.assertIn("Robotics R&D <case>",[x.findtext("title") for x in items])
        self.assertIn("A field guide to reliable source links & references.",
                      [x.findtext("description") for x in items])
        self.assertIn("&lt;case&gt;",xml)
        good=next(x for x in items if x.findtext("title")=="Robotics R&D <case>")
        self.assertEqual(good.findtext("pubDate"),"Wed, 25 Nov 2026 00:00:00 GMT")
        invalid=next(x for x in items if x.findtext("title")=="Date not yet confirmed")
        self.assertIsNone(invalid.find("pubDate"))

    def test_all_sitemap_routes_return_indexable_canonical_html(self):
        urls=[path for path,_ in seo_routes.sitemap_items(self.c)]
        self.assertIn("/methodology",urls)
        self.assertIn("/directory/sections/1",urls)
        for path in urls:
            with self.subTest(path=path):
                result=seo_routes.seo_document(path.lstrip("/"))
                self.assertEqual(result.status_code,200)
                self.assertEqual(result.headers["X-Robots-Tag"],"index, follow")
                body=result.body.decode()
                self.assertIn('rel="canonical" href="'+seo_routes.ORIGIN+path+'"',body)
                self.assertIn('id="atlas-seo-schema"',body)

    def test_stale_draft_never_enters_public_feed_or_sitemap(self):
        self.c["articles"].pop("draft-missing-date")
        xml=seo_feed.build(self.c,seo_routes.ORIGIN).decode()
        self.assertNotIn("Date not yet confirmed",xml)
        self.assertNotIn("/insights/draft-missing-date",
                         [path for path,_ in seo_routes.sitemap_items(self.c)])
        self.assertEqual(seo_routes.seo_document("insights/draft-missing-date").status_code,404)


if __name__=="__main__":
    unittest.main()
