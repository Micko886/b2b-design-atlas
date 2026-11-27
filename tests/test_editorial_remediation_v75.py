"""V75: real editorial content remediation of ten previously published research guides.

The references are not synthetic: all targets must exist in the same generated
published module catalog as live pages and point to real curated pattern studies.
No CMS draft or published PostgreSQL row is silently modified by this release.
"""
import copy
import html
import unittest
from pathlib import Path
from app import cms_quality,seo_final_audit,seo_routes

RELATED={
 "b2b-homepage-value-proposition":("fictiv-process-stages",),
 "vast-cinematic-engineering":("cfs-energy-hero",),
 "industrial-rfq-journey":("fictiv-process-stages","xometry-rfq-first"),
 "design-palette-beyond-screenshot":("lumafield-hero",),
 "sections-as-research-unit":("retool-hero","lumafield-hero"),
 "technical-spec-content-architecture":("arburg-product-family","tekna-machines-cnc-range"),
 "industrial-photography-and-3d":("intrepid-automation-hero","machina-labs-hero"),
 "b2b-trust-signals":("hexagon-capability","aixtron-deposition-products"),
 "website-to-pattern-workflow":("retool-hero","lumafield-hero"),
 "product-navigation-families":("arburg-product-family","tekna-machines-cnc-range"),
}

class PublishedEditorialV75(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public=seo_routes.base_catalog()
        cls.patterns=cls.public["patterns"]
        cls.articles=cls.public["articles"]
        cls.modules=cls.public["modules"]

    def test_all_new_references_are_curated_real_published_modules(self):
        curated={mid for item in self.patterns.values()
                 for mid in item.get("modules",[]) if isinstance(item,dict)}
        self.assertEqual(sum(map(len,RELATED.values())),17)
        for slug,modules in RELATED.items():
            with self.subTest(article=slug):
                article=self.articles[slug]
                for mid in modules:
                    self.assertIn(mid,curated)
                    self.assertIn(mid,self.modules)
                    item=self.modules[mid]
                    self.assertIn(item.get("site_id"),self.public["sites"])
                    self.assertTrue(seo_routes.source_url(item.get("url")),mid)
                    self.assertEqual(article["references"].count(["module",mid]),1)
                # Editorial notes explain why these examples, not ungrounded stats.
                notes=[txt for section in article["sections"]
                       for txt in section.get("paragraphs",[])
                       if txt.startswith("具体模块对照：")]
                self.assertEqual(len(notes),1)
                self.assertGreaterEqual(len(notes[0]),80)
                self.assertEqual(len(article["sections"]),4)

    def test_real_crawlable_html_links_to_all_added_modules(self):
        for slug,modules in RELATED.items():
            with self.subTest(article=slug):
                path="/insights/"+slug
                article=self.articles[slug]
                record=seo_routes.seo_record(path,self.public)
                self.assertTrue(record["indexed"])
                page=seo_routes.public_prerender(path,record,self.public)
                self.assertIn("具体模块对照：",html.unescape(page))
                for mid in modules:
                    self.assertIn('href="/sections/'+mid+'"',page)
                    target=seo_routes.seo_record("/sections/"+mid,self.public)
                    self.assertTrue(target and target["indexed"])
                    self.assertEqual(target["path"],"/sections/"+mid)

    def test_no_new_invalid_references_or_made_up_sources(self):
        for slug,article in self.articles.items():
            with self.subTest(article=slug):
                row=cms_quality.audit_resource("article",slug,article,self.public)
                errors={i["code"] for i in row["issues"]}
                self.assertNotIn("broken_refs",errors)
                self.assertNotIn("sources",errors)
                self.assertNotIn("invalid_links",errors)
                self.assertNotIn("depth",errors)
                self.assertTrue(any(x[0]=="website" for x in article["references"]))
                self.assertTrue(seo_routes.article_sources(article,self.public))

    def test_graph_gets_real_article_incoming_edges_not_false_crawl_orphan(self):
        maps=seo_final_audit.published_maps(self.public)
        incoming,outgoing,broken=seo_final_audit.editorial_graph(maps)
        for article,modules in RELATED.items():
            for mid in modules:
                with self.subTest(article=article,module=mid):
                    self.assertIn(("module",mid),outgoing[("article",article)])
                    self.assertIn(("article",article),incoming[("module",mid)])
            self.assertFalse(broken.get(("article",article)))

    def test_current_public_read_is_pure_and_draft_free(self):
        copy_of_public=copy.deepcopy(self.public)
        result=seo_final_audit.analyze(self.public,kind_filter="article",limit=12)
        self.assertEqual(self.public,copy_of_public)
        self.assertEqual(result["kind"],"article")
        self.assertGreaterEqual(result["total"],len(self.articles))
        self.assertFalse(any(r["slug"] in ("draft-hidden","review-pending") for r in result["items"]))

    def test_all_sitemap_article_pages_have_real_prerender_and_canonical(self):
        paths=dict(seo_routes.sitemap_items(self.public))
        for slug in RELATED:
            path="/insights/"+slug
            self.assertIn(path,paths)
            self.assertEqual(paths[path],"2026-11-27")
            self.assertEqual(seo_routes.article_lastmod(self.articles[slug]),"2026-11-27")
            schema=seo_routes.seo_schema(path,seo_routes.seo_record(path,self.public),
              self.public,seo_routes.ORIGIN+path,seo_routes.ORIGIN+"/assets/visual-placeholder.svg")
            nodes=schema.get("@graph",[])
            article_node=next(node for node in nodes if node.get("@type")=="Article")
            self.assertEqual(article_node["datePublished"],"2026-11-24")
            self.assertEqual(article_node["dateModified"],"2026-11-27")
            page=seo_routes.public_prerender(path,seo_routes.seo_record(path,self.public),self.public)
            self.assertIn('<h1>',page)
            self.assertIn('<h2>相关研究与参考资料</h2>',page)
            self.assertNotIn('href="javascript:',page)

if __name__=="__main__":unittest.main()
