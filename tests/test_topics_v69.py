"""V69 industry hubs: never fabricate industries or expose unpublished references."""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import seo_routes,seo_topics


class TopicLandingV69(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        (root/"index.html").write_text(
            '<html><head><title>Old</title><meta name="description" content="old">'
            '<script src="/assets/app.js?v=seo-geo-v62-1" defer></script></head>'
            '<body><main id="app"><div class="shell loading">正在加载设计资源…</div></main></body></html>',
            encoding="utf-8")
        self.catalog={"sites":{
            "fictiv":{"name":"Fictiv","summary":"制造业工程网站","url":"https://www.fictiv.com"},
            "skydio":{"name":"Skydio","summary":"Autonomous flying systems","url":"https://www.skydio.com"},
            "vention":{"name":"Vention","summary":"工业自动化选型","url":"https://vention.com"}
        },"modules":{},
          "patterns":{"proof":{"title":"Evidence first","question":"How to show verification?"}},
          "articles":{}}
        for topic,site in (("manufacturing","fictiv"),("robotics","skydio"),("automation","vention")):
            self.catalog["articles"]["industry-"+topic+"-web-experience"]={
                "title":"Public "+topic+" study",
                "subtitle":"Original case analysis for "+topic,
                "seo_description":"Verified editorial research for "+topic,
                "industry_topic":topic,
                "published_at":"2026-11-24",
                "references":[["website",site],["pattern","proof"]],
                "takeaways":["Only verified public observations, not performance predictions."]
            }
        p1=patch.object(seo_routes,"STATIC",root)
        p2=patch.object(seo_routes,"catalog",return_value=self.catalog)
        for p in (p1,p2):
            p.start()
            self.addCleanup(p.stop)

    def get(self,path):
        r=seo_routes.seo_document(path)
        return r.status_code,r.body.decode("utf-8"),r.headers

    def test_topic_hub_and_all_three_industry_pages_are_real_html(self):
        status,body,headers=self.get("topics")
        self.assertEqual(status,200)
        self.assertEqual(headers["X-Robots-Tag"],"index, follow")
        self.assertNotIn('src="/assets/app.js',body)
        for slug in seo_topics.TOPICS:
            self.assertIn('href="/topics/'+slug+'"',body)
            status,page,headers=self.get("topics/"+slug)
            self.assertEqual(status,200)
            self.assertIn(seo_topics.TOPICS[slug]["title"],page)
            self.assertIn("研究关注的问题",page)
            self.assertIn('href="/insights/industry-'+slug+'-web-experience"',page)
            self.assertIn('href="/patterns/proof"',page)
            self.assertIn('rel="canonical" href="'+seo_routes.ORIGIN+"/topics/"+slug+'"',page)
            self.assertEqual(headers["X-Robots-Tag"],"index, follow")
            self.assertNotIn('src="/assets/app.js',page)
            self.assertNotIn("正在加载设计资源…",page)

    def test_sitemap_ai_reader_and_human_links_align(self):
        paths=[path for path,_ in seo_routes.sitemap_items(self.catalog)]
        self.assertEqual([p for p in paths if p.startswith("/topics")],
            ["/topics","/topics/manufacturing","/topics/robotics","/topics/automation"])
        ai=seo_routes.llms_document(self.catalog)
        self.assertIn(seo_routes.ORIGIN+"/topics",ai)
        self.assertIn(seo_routes.ORIGIN+"/topics/robotics",ai)
        for slug in seo_topics.TOPICS:
            self.assertIn('href="/topics/'+slug+'"',self.get("topics")[1])

    def test_only_flagship_study_and_real_public_refs_create_a_topic(self):
        self.catalog["articles"].pop("industry-manufacturing-web-experience")
        self.catalog["sites"].pop("skydio")
        for slug in ("manufacturing","robotics","missing","../robotics"):
            with self.subTest(slug=slug):
                status,body,headers=self.get("topics/"+slug)
                self.assertEqual(status,404)
                self.assertEqual(headers["X-Robots-Tag"],"noindex")
                self.assertNotIn('rel="canonical"',body)
        active_paths=[path for path,_ in seo_routes.sitemap_items(self.catalog)]
        self.assertNotIn("/topics/manufacturing",active_paths)
        self.assertNotIn("/topics/robotics",active_paths)
        self.assertIn("/topics/automation",active_paths)
        self.assertEqual([x[0] for x in seo_topics.live_topics(self.catalog)],["automation"])
        self.catalog["articles"].pop("industry-automation-web-experience")
        self.assertNotIn("/topics",[path for path,_ in seo_routes.sitemap_items(self.catalog)])
        self.assertEqual(self.get("topics")[0],404)

    def test_unpublished_references_and_duplicate_items_never_leak(self):
        study=self.catalog["articles"]["industry-robotics-web-experience"]
        study["references"]=[["website","skydio"],["website","skydio"],
                             ["pattern","proof"],["website","draft-secret"],
                             ["article","private-study"],["module","nonexistent"]]
        html=self.get("topics/robotics")[1]
        self.assertEqual(html.count('href="/websites/skydio"'),1)
        self.assertNotIn("draft-secret",html)
        self.assertNotIn("private-study",html)
        self.assertNotIn("nonexistent",html)
        schema=json.loads(re.search(
            r'<script id="atlas-seo-schema" type="application/ld\+json">(.*?)</script>',html).group(1))
        urls=[x["url"] for x in schema["mainEntity"]["itemListElement"]]
        self.assertEqual(len(urls),3)
        self.assertEqual(len(set(urls)),3)
        self.assertTrue(all(x.startswith(seo_routes.ORIGIN+"/") for x in urls))

    def test_metadata_escaping_and_readonly_catalog(self):
        initial=copy.deepcopy(self.catalog)
        self.catalog["sites"]["vention"]["name"]='<script>alert("x")</script>'
        body=self.get("topics/automation")[1]
        self.assertNotIn('<script>alert("x")</script>',body)
        self.assertIn('&lt;script&gt;',body)
        self.assertEqual(self.catalog["sites"]["vention"]["name"],'<script>alert("x")</script>')
        self.catalog["sites"]["vention"]["name"]=initial["sites"]["vention"]["name"]
        self.assertEqual(self.catalog,initial)


if __name__=="__main__":
    unittest.main()
