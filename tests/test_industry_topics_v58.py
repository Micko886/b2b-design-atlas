"""V58: original industry research and crawlable citations, no live writes."""
from __future__ import annotations
import json
import unittest
from pathlib import Path
from urllib.parse import urlparse

from app import cms_routes,seo_routes

STATIC=Path(__file__).resolve().parents[1]/"static"
TOPICS={
    "manufacturing":"industry-manufacturing-web-experience",
    "robotics":"industry-robotics-web-experience",
    "automation":"industry-automation-web-experience",
}
OFFICIAL_HOSTS={
    "www.fictiv.com","www.figure.ai","www.skydio.com",
    "vention.com","www.beckhoff.com",
}

class IndustryStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.articles=json.loads((STATIC/"assets"/"articles.json").read_text(encoding="utf-8"))["articles"]
        cls.by_id={a["id"]:a for a in cls.articles}
        cls.catalog=seo_routes.base_catalog()

    def test_all_three_original_guides_are_distinct_and_readable(self):
        for topic,slug in TOPICS.items():
            with self.subTest(topic=topic):
                a=self.by_id[slug]
                self.assertEqual(a["industry_topic"],topic)
                self.assertEqual(len(a["sections"]),5)
                self.assertGreaterEqual(len(a["takeaways"]),3)
                self.assertGreaterEqual(len(a["tags"]),3)
                self.assertTrue(a["published_at"])
                self.assertGreaterEqual(len(a["seo_description"]),50)
                self.assertLessEqual(len(a["seo_description"]),170)
                self.assertNotEqual(a["seo_description"],a["subtitle"])
                body="".join(b.get("text","") for sec in a["sections"] for b in sec["blocks"])
                self.assertGreaterEqual(len(body),900)
                self.assertIn("可核验事实",body)
                self.assertTrue(any(phrase in body for phrase in ("设计建议","研究判断")))
                self.assertEqual(cms_routes.cleaned("article",slug,a)["id"],slug)

    def test_sources_are_official_and_articles_link_existing_resources(self):
        for topic,slug in TOPICS.items():
            with self.subTest(topic=topic):
                item=self.by_id[slug]
                sources=[b for sec in item["sections"] for b in sec["blocks"] if b.get("type")=="link"]
                self.assertGreaterEqual(len(sources),3)
                for source in sources:
                    self.assertIn(urlparse(source["url"]).hostname,OFFICIAL_HOSTS)
                    self.assertEqual(urlparse(source["url"]).scheme,"https")
                    self.assertLessEqual(len(source["text"]),180)
                self.assertTrue(any(ref[0]=="article" for ref in item["references"]))
                keys={"website":"sites","pattern":"patterns","module":"modules","article":"articles"}
                for kind,ref_id in item["references"]:
                    self.assertIn(kind,keys)
                    self.assertIn(ref_id,self.catalog[keys[kind]],f"{slug} missing {kind}:{ref_id}")

    def test_legacy_catalog_preview_paths_are_restored_only_from_existing_files(self):
        original={"id":"vast","name":"Vast"}
        restored=seo_routes._snapshot_if_present(original,"sites")
        self.assertEqual(restored["screenshot_url"],"/screenshots/sites/vast.webp")
        self.assertNotIn("screenshot_url",original)
        custom={"id":"vast","screenshot_url":"/api/media/12345678-1234-1234-1234-123456789abc"}
        self.assertIs(seo_routes._snapshot_if_present(custom,"sites"),custom)
        missing={"id":"no-image-qa-293810"}
        self.assertIs(seo_routes._snapshot_if_present(missing,"sites"),missing)
        module=seo_routes._snapshot_if_present({"id":"vast-hero"},"modules")
        self.assertEqual(module["screenshot_url"],"/screenshots/modules/vast-hero.webp")
        sources=self.catalog["sites"]
        self.assertGreaterEqual(len(sources),60)
        self.assertTrue(sources["vast"]["screenshot_url"].endswith("/vast.webp"))
        self.assertTrue(sources["fictiv"]["screenshot_url"].endswith("/fictiv.webp"))

    def test_editorial_covers_match_real_bundled_company_screenshots(self):
        root=Path(__file__).resolve().parents[1]
        for article in self.articles:
            with self.subTest(article=article["id"]):
                slug=article["cover_site"]
                screenshot=root/"screenshots"/"sites"/(slug+".webp")
                self.assertTrue(screenshot.is_file(),str(screenshot))
                expected="/screenshots/sites/"+slug+".webp"
                self.assertEqual(
                    seo_routes.content_image("insights",article,self.catalog),expected,
                    "Do not substitute a different company's screenshot."
                )

    def test_public_seo_and_crawler_body_have_unique_search_metadata(self):
        descriptions=set()
        for topic,slug in TOPICS.items():
            with self.subTest(topic=topic):
                record=seo_routes.seo_record("insights/"+slug,self.catalog)
                a=self.by_id[slug]
                self.assertEqual(record["title"],a["seo_title"])
                self.assertEqual(record["description"],a["seo_description"])
                self.assertTrue(record["indexed"])
                self.assertNotIn(record["description"],descriptions)
                descriptions.add(record["description"])
                body=seo_routes.public_prerender("insights/"+slug,record,self.catalog)
                self.assertIn(a["title"],body)
                self.assertIn("官方依据",body)
                self.assertIn("https://",body)
                self.assertIn('href="/insights/',body)
                self.assertIn('href="/patterns/',body)
                self.assertNotIn("javascript:",body.lower())

    def test_topic_navigation_and_article_links_are_in_spa(self):
        js=(STATIC/"assets"/"app.js").read_text(encoding="utf-8")
        css=(STATIC/"assets"/"app.css").read_text(encoding="utf-8")
        self.assertIn("function topicLinks()",js)
        self.assertIn("function researchTopic(topic)",js)
        self.assertIn("researchTopic(params.get('topic'))",js)
        self.assertIn("topic.related.includes(a.id)",js)
        self.assertIn("if(r[0]==='article')",js)
        self.assertIn("function industrySeries(a)",js)
        self.assertIn("$"+"{topicLinks()}",js)
        self.assertIn("insight-topic-grid",css)
        self.assertIn("@media(max-width:600px)",css)
        for topic,slug in TOPICS.items():
            self.assertIn("id:'"+topic+"'",js)
            self.assertIn(slug,js)

if __name__=="__main__":
    unittest.main()
