"""V62 · Verify transparent SEO/GEO source attribution and safe crawler output.

Pure tests on public snapshots and a temporary HTML shell; never writes to
Postgres or any CMS data. SEO/GEO claims cannot substitute for search indexing.
"""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import seo_routes

STATIC=Path(__file__).resolve().parents[1]/"static"


class GeoSourcesV62(unittest.TestCase):
    def test_sources_only_use_published_websites_and_explicit_https_research(self):
        sites={
            "factory":{"id":"factory","name":"Factory A","url":"https://example.org/products?a=1&b=2"},
            "invalid":{"id":"invalid","name":"Invalid source","url":"javascript:alert(1)"},
            "removed":{"id":"removed","name":"Has credentials","url":"https://alice:secret@example.org/"}
        }
        article={"references":[["website","factory"],["website","invalid"],
                               ["website","missing"],["website","removed"]],
                 "sections":[{"blocks":[
                     {"type":"link","url":"https://docs.example.org/whitepaper?x=1&y=2","text":"Engineering document"},
                     {"type":"link","url":"javascript:alert(1)","text":"Unsafe"},
                     {"type":"link","url":"https://docs.example.org/whitepaper?x=1&y=2","text":"Duplicated"},
                     {"type":"link","url":"https://example.org/<script>","text":"Injected"}
                 ]}]}
        original=json.loads(json.dumps(article))
        actual=seo_routes.article_sources(article,{"sites":sites})
        self.assertEqual(actual,[
            ("Engineering document","https://docs.example.org/whitepaper?x=1&y=2"),
            ("原始案例网站 · Factory A","https://example.org/products?a=1&b=2")
        ])
        self.assertEqual(original,article)
        self.assertEqual(seo_routes.source_url("https://example.org/ok"),"https://example.org/ok")
        for unsafe in ("javascript:alert(1)","https://foo\\bar","https://user:pass@example.org/path",
                       "https://bad.example/<script>","https://bad.example/\"quoted\""):
            with self.subTest(url=unsafe):self.assertIsNone(seo_routes.source_url(unsafe))

    def test_article_schema_citations_match_visible_links(self):
        article={
            "title":"Evidence-based robotics",
            "subtitle":"Research task and constraints",
            "published_at":"2026-11-24",
            "updated_at":"2026-11-26",
            "author":"Atlas editorial",
            "references":[["website","factory"]],
            "sections":[{"title":"Proof", "blocks":[
                {"type":"paragraph","text":"**Verified statement** based on the source."},
                {"type":"link","url":"https://docs.example.org/manual","text":"User manual"}
            ]}]
        }
        coll={"sites":{"factory":{"name":"Factory","url":"https://factory.example.org/"}},
              "modules":{},"patterns":{},"articles":{"guide":article}}
        with patch.object(seo_routes,"catalog",return_value=coll):
            with tempfile.TemporaryDirectory() as root:
                template=Path(root)/"index.html"
                template.write_text('<html><head><title>Initial</title><meta name="description" content="default"></head><body><main id="app"><div class="shell loading">正在加载设计资源…</div></main></body></html>',encoding="utf-8")
                with patch.object(seo_routes,"STATIC",Path(root)):
                    result=seo_routes.seo_document("insights/guide")
        html=result.body.decode("utf-8")
        self.assertEqual(result.status_code,200)
        schema=json.loads(re.search(r'<script id="atlas-seo-schema" type="application/ld\+json">(.*?)</script>',html).group(1))
        entity=next(x for x in schema["@graph"] if x["@type"]=="Article")
        self.assertEqual(entity["citation"],["https://docs.example.org/manual","https://factory.example.org/"])
        self.assertEqual(entity["datePublished"],"2026-11-24")
        self.assertEqual(entity["dateModified"],"2026-11-26")
        self.assertNotIn("image",entity,"Do not invent an image for a missing research cover")
        self.assertIn('<strong>Verified statement</strong>',html)
        self.assertIn('href="https://docs.example.org/manual"',html)
        self.assertIn('href="https://factory.example.org/"',html)
        self.assertIn('aria-label="研究来源"',html)
        self.assertIn('rel="nofollow noopener noreferrer"',html)

    def test_unverified_modified_date_is_not_fabricated(self):
        c={"sites":{},"modules":{},"patterns":{},"articles":{"a":{"sections":[],"updated_at":"tomorrow"}}}
        r={"title":"Research","description":"Description","kind":"article",
           "published":"2026-11-27","path":"/insights/a","indexed":True}
        schema=seo_routes.seo_schema("/insights/a",r,c,seo_routes.ORIGIN+"/insights/a","")
        article=next(x for x in schema["@graph"] if x["@type"]=="Article")
        self.assertEqual(article["datePublished"],"2026-11-27")
        self.assertNotIn("dateModified",article)
        self.assertNotIn("image",article)
        c["articles"]["a"]["updated_at"]="2026-01-01"
        schema=seo_routes.seo_schema("/insights/a",r,c,seo_routes.ORIGIN+"/insights/a","")
        article=next(x for x in schema["@graph"] if x["@type"]=="Article")
        self.assertNotIn("dateModified",article)

    def test_neutral_social_fallback_and_nonindexable_canonical(self):
        with tempfile.TemporaryDirectory() as root:
            html_file=Path(root)/"index.html"
            html_file.write_text('<html><head><title>Initial</title><meta name="description" content="default"></head><body><main id="app"><div class="shell loading">正在加载设计资源…</div></main></body></html>',encoding="utf-8")
            with patch.object(seo_routes,"STATIC",Path(root)):
                with patch.object(seo_routes,"catalog",return_value={"sites":{},"modules":{},"patterns":{},"articles":{}}):
                    home=seo_routes.seo_document("").body.decode("utf-8")
                    unknown=seo_routes.seo_document("we-are-not-here").body.decode("utf-8")
                    private=seo_routes.seo_document("account").body.decode("utf-8")
        self.assertIn('rel="canonical"',home)
        self.assertIn('/assets/visual-placeholder.svg',home)
        self.assertNotIn('og:image" content="'+seo_routes.ORIGIN+'/screenshots/sites/vast.webp',home)
        self.assertNotIn('rel="canonical"',unknown)
        self.assertNotIn('rel="canonical"',private)
        self.assertIn('name="robots" content="noindex, follow"',unknown)

    def test_all_original_articles_expose_traced_sources(self):
        articles=json.loads((STATIC/"assets"/"articles.json").read_text(encoding="utf-8"))["articles"]
        catalog=seo_routes.base_catalog()
        self.assertEqual(len(articles),13)
        without_sources=[]
        for item in articles:
            with self.subTest(article=item["id"]):
                sources=seo_routes.article_sources(item,catalog)
                if not sources:without_sources.append(item["id"])
                self.assertEqual(len(sources),len(set(u for _,u in sources)))
                self.assertTrue(all(url.startswith(("http://","https://")) for _,url in sources))
        self.assertEqual(without_sources,[],"Original 13 articles must have traceable published sources")

    def test_frontend_source_contract_has_no_unsafe_html_urls(self):
        js=(STATIC/"assets"/"app.js").read_text(encoding="utf-8")
        css=(STATIC/"assets"/"app.css").read_text(encoding="utf-8")
        self.assertIn("function insightSourceLinks(a)",js)
        self.assertIn("insightSourceLinks(a)}",js)
        self.assertIn('rel="nofollow noopener noreferrer"',js)
        self.assertIn("原始案例网站",js)
        self.assertIn("fallbackImage='/assets/visual-placeholder.svg'",js)
        self.assertIn(".insight-source-links a:focus-visible",css)


if __name__=="__main__":unittest.main()
